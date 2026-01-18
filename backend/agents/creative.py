"""创作总监 Agent - 负责任务规划、工具选择和结果评估"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent

from backend.agents.base import BaseRedInkAgent

logger = logging.getLogger(__name__)


class ToolCallGuard:
    """工具调用守卫 - 防止同一工具被重复调用"""
    def __init__(self):
        self.called_tools = set()
        self.tool_results = {}

    def wrap_tool(self, tool: BaseTool) -> BaseTool:
        original_run = tool._run
        original_arun = tool._arun
        guard = self

        def guarded_run(*args, **kwargs):
            tool_name = tool.name
            logger.info(
                f"[ToolGuard] tool request: {tool_name}, called: {guard.called_tools}"
            )

            if tool_name in guard.called_tools:
                logger.warning(f"[ToolGuard] duplicate tool call blocked: {tool_name}")
                if tool_name in guard.tool_results:
                    logger.info(f"[ToolGuard] returning cached result: {tool_name}")
                    return guard.tool_results[tool_name]
                return json.dumps({
                    "success": False,
                    "error": f"tool {tool_name} already called, duplicate call blocked"
                }, ensure_ascii=False)

            logger.info(f"[ToolGuard] allow first call: {tool_name}")
            guard.called_tools.add(tool_name)
            result = original_run(*args, **kwargs)
            guard.tool_results[tool_name] = result
            logger.info(f"[ToolGuard] tool finished: {tool_name}")
            return result

        async def guarded_arun(*args, **kwargs):
            tool_name = tool.name
            logger.info(
                f"[ToolGuard] async tool request: {tool_name}, called: {guard.called_tools}"
            )

            if tool_name in guard.called_tools:
                logger.warning(f"[ToolGuard] duplicate tool call blocked: {tool_name}")
                if tool_name in guard.tool_results:
                    logger.info(f"[ToolGuard] returning cached result: {tool_name}")
                    return guard.tool_results[tool_name]
                return json.dumps({
                    "success": False,
                    "error": f"tool {tool_name} already called, duplicate call blocked"
                }, ensure_ascii=False)

            logger.info(f"[ToolGuard] allow first call: {tool_name}")
            guard.called_tools.add(tool_name)
            result = await original_arun(*args, **kwargs)
            guard.tool_results[tool_name] = result
            logger.info(f"[ToolGuard] async tool finished: {tool_name}")
            return result

        tool._run = guarded_run
        tool._arun = guarded_arun
        return tool


CREATIVE_DIRECTOR_SYSTEM_PROMPT = """你是红墨AI创作助手，一个智能的多功能助手，当前时间: {current_time}。

## 你的核心能力
你可以根据用户的实际需求，智能选择和调用合适的工具来完成任务。

## 可用工具
{available_tools}

## 重要原则
1. **理解用户意图**：仔细分析用户的请求，理解他们真正想要什么
2. **智能工具选择**：根据用户需求选择最合适的工具，不要盲目调用任何工具
3. **按需调用**：只在用户需要时才调用相应的工具
4. **严格防重**：每一个工具在一次对话中只能调用一次，已调用的工具不得再次调用
5. **灵活应对**：如果用户请求与现有工具不匹配，直接用你的知识回答

## 工具使用指南

### generate_outline 工具（创作小红书内容）
当用户想创作小红书内容时，使用此工具。请从对话中提取结构化的上下文信息：

**参数说明：**
- `topic`（必需）：用户的创作主题
- `context`（可选）：结构化的创作上下文，包含以下字段：

```json
{{
  "style": {{
    "tone": "语气风格（活泼/专业/温馨/幽默/严谨/轻松）",
    "language": "语言特点（口语化/书面语/网络流行语/文艺范）",
    "emotion": "情感基调（积极向上/治愈系/励志/感性/理性）"
  }},
  "audience": {{
    "demographics": "目标人群（年轻女性/职场新人/宝妈/学生党等）",
    "interests": ["兴趣标签1", "兴趣标签2"],
    "pain_points": ["痛点1", "痛点2"]
  }},
  "requirements": {{
    "must_include": ["必须包含的元素"],
    "must_avoid": ["需要避免的内容"],
    "word_count": "篇幅要求",
    "format_hints": ["格式提示"]
  }},
  "references": {{
    "similar_content": "参考风格描述",
    "keywords": ["关键词"],
    "hashtags": ["话题标签"]
  }},
  "metadata": {{
    "content_type": "内容类型（教程/测评/分享/种草/避雷/攻略）",
    "purpose": "创作目的（品牌推广/知识分享/经验总结/产品种草）",
    "platform": "目标平台"
  }},
  "raw_context": "无法结构化的其他信息"
}}
```

**上下文提取示例：**

用户说："帮我写一篇关于咖啡的小红书，要活泼一点，面向年轻女性，最好能种草一个。"

提取结果：
```json
{{
  "topic": "关于咖啡的小红书",
  "context": {{
    "style": {{"tone": "活泼"}},
    "audience": {{"demographics": "年轻女性"}},
    "metadata": {{"content_type": "种草", "purpose": "产品种草"}}
  }}
}}
```

用户说："写个减肥食谱教程，要详细点，适合新手，记得加上食材清单。"

提取结果：
```json
{{
  "topic": "减肥食谱教程",
  "context": {{
    "audience": {{"demographics": "新手"}},
    "requirements": {{
      "must_include": ["食材清单"],
      "word_count": "详细完整"
    }},
    "metadata": {{"content_type": "教程"}}
  }}
}}
```

### 其他工具
- 如果用户想生成图片，可以使用 generate_images 工具（需要先有大纲）
- 如果用户的请求与其他 MCP 工具相关，请选择合适的 MCP 工具
- 如果用户只是想聊天或问问题，直接回答即可，不需要调用工具

## 输出格式
用中文与用户交流，清晰说明你的操作和结果。
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
    """创作总监 Agent"""

    def __init__(
        self,
        llm,
        tools: List,
        callbacks: Optional[List[BaseCallbackHandler]] = None,
        verbose: bool = False,
        memory_window: int = 5,
        image_generation_enabled: bool = True
    ):
        super().__init__(callbacks, verbose)
        self.llm = llm
        self.chat_history = []
        self.memory_window = memory_window
        self.image_generation_enabled = image_generation_enabled

        self.tool_guard = ToolCallGuard()
        self.tools = tools

        self.agent = self._create_agent()

    def _create_agent(self):
        tools_description = _build_tools_description(self.tools, self.image_generation_enabled)
        prompt = CREATIVE_DIRECTOR_SYSTEM_PROMPT.format(
            available_tools=tools_description,
            current_time=datetime.now()
        )

        if self.image_generation_enabled:
            prompt += (
                "\n\n## 【重要工作流程】\n"
                "当用户请求创作小红书内容时，你必须按以下顺序执行：\n"
                "1. **第一步**：调用 `generate_outline` 工具生成大纲和文案\n"
                "2. **第二步**：在大纲生成成功后，**必须**立即调用 `generate_images` 工具生成配图\n"
                "   - 将大纲中的 pages 数组传给 generate_images\n"
                "   - 同时传入 user_topic（用户原始输入）\n"
                "   - 可选传入 full_outline（完整大纲文本）\n"
                "\n"
                "⚠️ 注意：如果用户请求创作内容，你必须同时调用这两个工具。不要只生成大纲而跳过图片生成。\n"
            )
        else:
            prompt += (
                "\n\n【指引】\n"
                "图片生成已禁用。如需图片，仅返回提示词/元数据，不调用外部图片API。"
            )

        return create_react_agent(
            self.llm,
            self.tools,
            prompt=prompt
        )

    def _handle_parsing_error(self, error: Exception) -> str:
        logger.warning(f"Agent parsing error: {error}")
        return f"Parsing error. Please revise response. Details: {str(error)[:100]}"

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            user_input = input_data.get("topic", "")
            images = input_data.get("images", [])

            message_content = user_input
            if images:
                message_content += f"\n\n[User provided {len(images)} reference images]"

            self._emit_event("progress", {
                "type": "start",
                "topic": user_input,
                "has_images": len(images) > 0,
                "message": "start"
            })

            result = await self.agent.ainvoke(
                {"messages": [HumanMessage(content=message_content)]},
                config={"callbacks": self.callbacks}
            )

            output = ""
            if result.get("messages"):
                last_message = result["messages"][-1]
                output = last_message.content if hasattr(last_message, 'content') else str(last_message)

            self._emit_event("progress", {
                "type": "complete",
                "success": True,
                "output": output,
                "message": "complete"
            })

            return {
                "success": True,
                "output": output,
                "messages": result.get("messages", [])
            }

        except Exception as e:
            return self._handle_error(e, "creative_director_run")

    def run_sync(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._run_with_streaming(input_data))
        finally:
            loop.close()

    async def _run_with_streaming(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            user_input = input_data.get("topic", "")
            images = input_data.get("images", [])

            message_content = user_input
            if images:
                message_content += f"\n\n[User provided {len(images)} reference images]"

            self._emit_event("progress", {
                "type": "start",
                "topic": user_input,
                "has_images": len(images) > 0,
                "message": "start"
            })

            current_response = ""
            final_output = ""
            processed_tool_results = set()

            async for event in self.agent.astream_events(
                {"messages": [HumanMessage(content=message_content)]},
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

                    if tool_name in self.tool_guard.called_tools:
                        logger.warning(f"[EventHandler] duplicate tool call: {tool_name}")
                        self._emit_event("tool_call", {
                            "type": "duplicate",
                            "tool": tool_name,
                            "message": f"duplicate tool call: {tool_name}"
                        })
                    else:
                        logger.info(f"[EventHandler] tool call: {tool_name}")

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

                    # P5-1: 改进工具输出解析逻辑
                    parsed_data = None
                    content = ""

                    if isinstance(output, dict):
                        # 输出已经是字典对象
                        parsed_data = output
                        content = json.dumps(output, ensure_ascii=False)
                    elif isinstance(output, list):
                        # 输出是列表
                        parsed_data = output
                        content = json.dumps(output, ensure_ascii=False)
                    elif isinstance(output, str):
                        content = output
                        # 尝试解析 JSON 字符串
                        try:
                            parsed_data = json.loads(output)
                        except (json.JSONDecodeError, TypeError):
                            # 不是 JSON，保持为纯文本
                            parsed_data = None
                    elif hasattr(output, 'content'):
                        # LangGraph ToolMessage 对象
                        content = str(output.content) if output.content else ""
                        try:
                            parsed_data = json.loads(content)
                        except (json.JSONDecodeError, TypeError):
                            parsed_data = None
                    else:
                        # 其他类型，转换为字符串
                        content = str(output) if output else ""
                        try:
                            parsed_data = json.loads(content)
                        except (json.JSONDecodeError, TypeError):
                            parsed_data = None

                    logger.info(f"[ToolEnd] 工具输出类型: {type(output).__name__}, 解析成功: {parsed_data is not None}")

                    self._emit_event("tool_result", {
                        "type": "end",
                        "output": content,
                        "data": parsed_data
                    })


            self._emit_event("progress", {
                "type": "complete",
                "success": True,
                "output": final_output,
                "message": "complete"
            })

            return {
                "success": True,
                "output": final_output
            }

        except Exception as e:
            return self._handle_error(e, "creative_director_run_sync")
