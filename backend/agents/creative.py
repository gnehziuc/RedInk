"""创作总监 Agent - 负责任务规划、工具选择和结果评估"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent

from backend.agents.base import BaseRedInkAgent

logger = logging.getLogger(__name__)


class ToolCallGuard:
    """工具调用守卫 - 防止同一工具被重复调用

    改进点：
    - 添加 reset() 方法支持重置状态
    - 添加 reset_tool() 方法支持重置单个工具
    """
    def __init__(self):
        self.called_tools: set = set()
        self.tool_results: Dict[str, Any] = {}

    def reset(self):
        """重置所有工具调用状态"""
        self.called_tools.clear()
        self.tool_results.clear()
        logger.info("[ToolGuard] 所有工具状态已重置")

    def reset_tool(self, tool_name: str):
        """重置单个工具的调用状态"""
        self.called_tools.discard(tool_name)
        self.tool_results.pop(tool_name, None)
        logger.info(f"[ToolGuard] 工具 {tool_name} 状态已重置")

    def is_called(self, tool_name: str) -> bool:
        """检查工具是否已被调用"""
        return tool_name in self.called_tools

    def wrap_tool(self, tool: BaseTool) -> BaseTool:
        """包装工具，添加调用守卫

        注意：如果工具已被包装过，使用保存的原始方法，避免链式调用问题
        """
        # 获取真正的原始方法（防止多次包装导致的链式调用）
        if hasattr(tool, '_original_run'):
            original_run = tool._original_run
            original_arun = tool._original_arun
        else:
            original_run = tool._run
            original_arun = tool._arun
            # 保存原始方法引用
            tool._original_run = original_run
            tool._original_arun = original_arun

        guard = self

        def guarded_run(*args, **kwargs):
            tool_name = tool.name
            logger.info(f"[ToolGuard] 工具请求: {tool_name}, 已调用: {guard.called_tools}")

            if tool_name in guard.called_tools:
                logger.warning(f"[ToolGuard] 阻止重复调用: {tool_name}")
                if tool_name in guard.tool_results:
                    logger.info(f"[ToolGuard] 返回缓存结果: {tool_name}")
                    return guard.tool_results[tool_name]
                return json.dumps({
                    "success": False,
                    "error": f"工具 {tool_name} 已调用，重复调用被阻止",
                    "hint": "如需重新生成，请开始新的对话"
                }, ensure_ascii=False)

            logger.info(f"[ToolGuard] 允许首次调用: {tool_name}")
            guard.called_tools.add(tool_name)
            result = original_run(*args, **kwargs)
            guard.tool_results[tool_name] = result
            logger.info(f"[ToolGuard] 工具完成: {tool_name}")
            return result

        async def guarded_arun(*args, **kwargs):
            tool_name = tool.name
            logger.info(f"[ToolGuard] 异步工具请求: {tool_name}, 已调用: {guard.called_tools}")

            if tool_name in guard.called_tools:
                logger.warning(f"[ToolGuard] 阻止重复调用: {tool_name}")
                if tool_name in guard.tool_results:
                    logger.info(f"[ToolGuard] 返回缓存结果: {tool_name}")
                    return guard.tool_results[tool_name]
                return json.dumps({
                    "success": False,
                    "error": f"工具 {tool_name} 已调用，重复调用被阻止",
                    "hint": "如需重新生成，请开始新的对话"
                }, ensure_ascii=False)

            logger.info(f"[ToolGuard] 允许首次调用: {tool_name}")
            guard.called_tools.add(tool_name)
            result = await original_arun(*args, **kwargs)
            guard.tool_results[tool_name] = result
            logger.info(f"[ToolGuard] 异步工具完成: {tool_name}")
            return result

        tool._run = guarded_run
        tool._arun = guarded_arun
        return tool


# 优化后的系统提示词：删除冗长的 JSON 示例，简化为实用指导
CREATIVE_DIRECTOR_SYSTEM_PROMPT = """你是红墨AI创作助手，专注于小红书内容创作。当前时间: {current_time}

## 可用工具
{available_tools}

## 核心原则
1. **理解用户意图**：仔细分析用户请求，理解真正需求
2. **智能工具选择**：根据需求选择合适的工具，不要盲目调用
3. **严格防重**：每个工具在一次对话中只能调用一次
4. **灵活应对**：如果请求与现有工具不匹配，直接用知识回答

## 工具使用指南

### generate_outline（生成小红书大纲）
当用户想创作小红书内容时使用。

参数：
- `topic`（必需）：创作主题
- `context`（可选）：补充信息，如风格、受众、特殊要求等

从用户输入中提取关键信息作为 context，例如：
- 风格语气：活泼/专业/温馨/幽默
- 目标人群：年轻女性/职场新人/学生党
- 特殊要求：必须包含xxx、字数要求、格式要求

示例：
用户说"帮我写一篇关于咖啡的小红书，要活泼一点，面向年轻女性"
调用：generate_outline(topic="关于咖啡的小红书", context="风格：活泼；目标人群：年轻女性")

### generate_images（生成配图）
在大纲生成成功后使用，将大纲的 pages 数组传入。

### 其他情况
- 用户只是聊天或问问题：直接回答，不调用工具
- 用户请求与工具不匹配：用知识回答

## 输出格式
用中文交流，清晰说明操作和结果。
"""


def _build_tools_description(tools: List, image_generation_enabled: bool) -> str:
    """根据可用工具生成描述"""
    descriptions = []
    for tool in tools:
        tool_name = getattr(tool, 'name', str(tool))
        tool_desc = getattr(tool, 'description', '无描述')

        if tool_name == "generate_outline":
            descriptions.append(f"- {tool_name}: 根据主题生成小红书内容大纲和文案")
        elif tool_name == "generate_images":
            if image_generation_enabled:
                descriptions.append(f"- {tool_name}: 根据大纲内容生成配图")
        else:
            short_desc = tool_desc[:100] + "..." if len(tool_desc) > 100 else tool_desc
            descriptions.append(f"- {tool_name}: {short_desc}")

    if not descriptions:
        descriptions.append("- 当前没有可用工具，请直接与用户对话")

    return "\n".join(descriptions)


class CreativeDirectorAgent(BaseRedInkAgent):
    """创作总监 Agent

    改进点：
    - 删除未使用的 run() 方法，统一使用 run_sync()
    - 添加重试机制
    - 实现 memory_window 功能
    - 优化事件循环管理
    - 删除冗余的双重工具调用检查
    """

    def __init__(
        self,
        llm,
        tools: List,
        callbacks: Optional[List[BaseCallbackHandler]] = None,
        verbose: bool = False,
        memory_window: int = 5,
        image_generation_enabled: bool = True,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        super().__init__(callbacks, verbose, max_retries, retry_delay)
        self.llm = llm
        self.memory_window = memory_window
        self.image_generation_enabled = image_generation_enabled

        # 消息历史（实现 memory_window）
        self.message_history: List[Any] = []

        # 直接使用工具，不再包装（移除重复调用限制）
        self.tools = tools

        self.agent = self._create_agent()

    def _create_agent(self):
        """创建 LangGraph ReAct Agent"""
        tools_description = _build_tools_description(self.tools, self.image_generation_enabled)
        prompt = CREATIVE_DIRECTOR_SYSTEM_PROMPT.format(
            available_tools=tools_description,
            current_time=datetime.now().strftime("%Y-%m-%d %H:%M")
        )

        if self.image_generation_enabled:
            prompt += (
                "\n\n## 【重要工作流程】\n"
                "当用户请求创作小红书内容时，按以下顺序执行：\n"
                "1. 调用 `generate_outline` 生成大纲和文案\n"
                "2. 大纲成功后，立即调用 `generate_images` 生成配图\n"
                "   - 将大纲的 pages 数组传给 generate_images\n"
                "   - 传入 user_topic（用户原始输入）\n"
                "\n注意：必须同时调用这两个工具，不要只生成大纲而跳过图片。\n"
            )
        else:
            prompt += "\n\n【提示】图片生成已禁用，仅生成大纲和文案。"

        return create_react_agent(
            self.llm,
            self.tools,
            prompt=prompt
        )

    def _trim_message_history(self):
        """裁剪消息历史，保持在 memory_window 范围内"""
        if len(self.message_history) > self.memory_window * 2:
            # 保留最近的 memory_window 轮对话（每轮包含用户消息和AI回复）
            self.message_history = self.message_history[-(self.memory_window * 2):]
            logger.info(f"[Memory] 消息历史已裁剪，当前长度: {len(self.message_history)}")

    def reset(self):
        """重置 Agent 状态（用于新对话）"""
        self.tool_guard.reset()
        self.message_history.clear()
        logger.info("[Agent] 状态已重置")

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """异步执行 Agent 任务（实现基类抽象方法）"""
        return await self._run_with_streaming(input_data)

    def run_sync(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """同步执行 Agent 任务（带重试机制）"""
        # 在重试循环外发送 start 事件，避免重复发送
        user_input = input_data.get("topic", "")
        images = input_data.get("images", [])
        self._emit_event("progress", {
            "type": "start",
            "topic": user_input,
            "has_images": len(images) > 0,
            "message": "开始创作"
        })

        def _execute():
            # 尝试获取现有事件循环，如果没有则创建新的
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    raise RuntimeError("Event loop is closed")
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            try:
                return loop.run_until_complete(self._run_with_streaming(input_data, emit_start=False))
            finally:
                # 不关闭事件循环，允许复用
                pass

        # 使用基类的重试机制
        try:
            return self._retry_operation(_execute, "agent_run")
        except Exception as e:
            return self._handle_error(e, "creative_director_run_sync")

    async def _run_with_streaming(self, input_data: Dict[str, Any], emit_start: bool = True) -> Dict[str, Any]:
        """带流式输出的异步执行

        Args:
            input_data: 输入数据
            emit_start: 是否发送 start 事件（run_sync 会在外部发送，避免重试时重复）
        """
        try:
            user_input = input_data.get("topic", "")
            images = input_data.get("images", [])

            message_content = user_input
            if images:
                message_content += f"\n\n[用户提供了 {len(images)} 张参考图片]"

            # 发送开始事件（如果需要）
            if emit_start:
                self._emit_event("progress", {
                    "type": "start",
                    "topic": user_input,
                    "has_images": len(images) > 0,
                    "message": "开始创作"
                })

            # 构建消息（包含历史）
            messages = list(self.message_history)  # 复制历史
            messages.append(HumanMessage(content=message_content))

            current_response = ""
            final_output = ""
            processed_tool_results = set()

            async for event in self.agent.astream_events(
                {"messages": messages},
                version="v2"
            ):
                event_type = event.get("event")
                event_data = event.get("data", {})

                if event_type == "on_chat_model_stream":
                    chunk = event_data.get("chunk")
                    if chunk and hasattr(chunk, 'content') and chunk.content:
                        token = chunk.content
                        current_response += token
                        self._emit_event("response", {
                            "type": "token",
                            "token": token,
                            "content": current_response
                        })

                elif event_type == "on_chat_model_end":
                    if current_response:
                        final_output = current_response
                        self._emit_event("response", {
                            "type": "end",
                            "content": current_response
                        })
                        current_response = ""

                elif event_type == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    tool_input = event_data.get("input", {})

                    logger.info(f"[EventHandler] 工具调用: {tool_name}")

                    self._emit_event("tool_call", {
                        "type": "start",
                        "tool": tool_name,
                        "input": json.dumps(tool_input, ensure_ascii=False) if isinstance(tool_input, dict) else str(tool_input)
                    })

                elif event_type == "on_tool_end":
                    run_id = event.get("run_id", "")
                    if run_id in processed_tool_results:
                        continue
                    processed_tool_results.add(run_id)

                    output = event_data.get("output", "")
                    parsed_data, content = self._parse_tool_output(output)

                    logger.info(f"[ToolEnd] 输出类型: {type(output).__name__}, 解析成功: {parsed_data is not None}")

                    self._emit_event("tool_result", {
                        "type": "end",
                        "output": content,
                        "data": parsed_data
                    })

            # 更新消息历史
            self.message_history.append(HumanMessage(content=message_content))
            if final_output:
                self.message_history.append(AIMessage(content=final_output))
            self._trim_message_history()

            # 发送完成事件
            self._emit_event("progress", {
                "type": "complete",
                "success": True,
                "output": final_output,
                "message": "创作完成"
            })

            return {
                "success": True,
                "output": final_output
            }

        except Exception as e:
            logger.error(f"[Agent] 执行错误: {e}")
            # 不在这里发送 error 事件，让重试机制处理
            # 重试时 base._retry_operation 会发送 retry 事件
            # 最终失败时 _handle_error 会发送 error 事件
            raise

    def _parse_tool_output(self, output: Any) -> tuple:
        """解析工具输出，返回 (parsed_data, content_string)"""
        parsed_data = None
        content = ""

        if isinstance(output, dict):
            parsed_data = output
            content = json.dumps(output, ensure_ascii=False)
        elif isinstance(output, list):
            parsed_data = output
            content = json.dumps(output, ensure_ascii=False)
        elif isinstance(output, str):
            content = output
            try:
                parsed_data = json.loads(output)
            except (json.JSONDecodeError, TypeError):
                pass
        elif hasattr(output, 'content'):
            # LangGraph ToolMessage 对象
            content = str(output.content) if output.content else ""
            try:
                parsed_data = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                pass
        else:
            content = str(output) if output else ""
            try:
                parsed_data = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                pass

        return parsed_data, content
