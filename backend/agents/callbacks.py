"""WebSocket 流式回调处理器"""
import logging
import json
from typing import Any, Dict, List, Optional, Union
from uuid import UUID
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from langchain_core.agents import AgentAction, AgentFinish

logger = logging.getLogger(__name__)


class WebSocketCallbackHandler(BaseCallbackHandler):
    """WebSocket 实时推送回调处理器"""

    # 显示输出的最大长度
    DISPLAY_MAX_LENGTH = 500

    def __init__(self, socketio, room: str):
        self.socketio = socketio
        self.room = room
        self.run_id: Optional[str] = None
        # 流式输出：当前响应内容
        self.current_response: str = ""
        self.is_streaming_response: bool = False

    def _emit(self, event: str, data: Dict[str, Any]):
        """发送 WebSocket 事件"""
        if self.socketio:
            self.socketio.emit(event, data, room=self.room)
            logger.debug(f"WebSocket emit: {event} -> {self.room}")

    def _truncate_for_display(self, text: str) -> str:
        """截断用于显示的文本"""
        if len(text) > self.DISPLAY_MAX_LENGTH:
            return text[:self.DISPLAY_MAX_LENGTH] + '...'
        return text

    def _parse_json_safe(self, text: str) -> Optional[Dict]:
        """安全解析 JSON"""
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return None

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        **kwargs
    ):
        """LLM 开始推理"""
        self.run_id = str(run_id)
        self.current_response = ""
        self.is_streaming_response = False
        self._emit('agent:thought', {
            'type': 'start',
            'run_id': self.run_id,
            'message': '正在思考...'
        })

    def on_llm_new_token(self, token: str, **kwargs):
        """LLM 流式输出 token - 实现打字机效果"""
        self.current_response += token
        self.is_streaming_response = True

        # 发送流式 token 事件
        self._emit('agent:response', {
            'type': 'token',
            'run_id': self.run_id,
            'token': token,
            'content': self.current_response  # 累积内容
        })

        # 同时更新思考状态
        self._emit('agent:thought', {
            'type': 'token',
            'run_id': self.run_id,
            'token': token
        })

    def on_llm_end(self, response: LLMResult, **kwargs):
        """LLM 推理结束"""
        # 发送完成事件
        self._emit('agent:thought', {
            'type': 'end',
            'run_id': self.run_id,
            'content': self.current_response if self.is_streaming_response else None
        })

        # 如果有流式内容，发送最终响应
        if self.is_streaming_response and self.current_response:
            self._emit('agent:response', {
                'type': 'end',
                'run_id': self.run_id,
                'content': self.current_response
            })

        # 重置状态
        self.current_response = ""
        self.is_streaming_response = False

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        **kwargs
    ):
        """工具调用开始"""
        tool_name = serialized.get('name', 'unknown')
        self._emit('agent:tool_call', {
            'type': 'start',
            'tool': tool_name,
            'input': self._truncate_for_display(input_str),
            'run_id': str(run_id)
        })

    def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs):
        """工具调用结束"""
        # P5-1: 改进工具输出处理
        content = ""
        parsed_data = None

        if isinstance(output, dict):
            parsed_data = output
            content = json.dumps(output, ensure_ascii=False)
        elif isinstance(output, list):
            parsed_data = output
            content = json.dumps(output, ensure_ascii=False)
        elif isinstance(output, str):
            content = output
            parsed_data = self._parse_json_safe(output)
        else:
            content = str(output) if output else ""
            parsed_data = self._parse_json_safe(content)

        # 显示用的截断输出
        display_output = self._truncate_for_display(content)

        self._emit('agent:tool_result', {
            'type': 'end',
            'output': display_output,
            'data': parsed_data,  # 完整的结构化数据供前端使用
            'run_id': str(run_id)
        })

    def on_tool_error(self, error: BaseException, *, run_id: UUID, **kwargs):
        """工具调用错误"""
        self._emit('agent:tool_result', {
            'type': 'error',
            'error': str(error),
            'run_id': str(run_id)
        })

    def on_agent_action(self, action: AgentAction, **kwargs):
        """Agent 执行动作"""
        self._emit('agent:progress', {
            'type': 'action',
            'tool': action.tool,
            'input': self._truncate_for_display(str(action.tool_input))
        })

    def on_agent_finish(self, finish: AgentFinish, **kwargs):
        """Agent 完成"""
        self._emit('agent:progress', {
            'type': 'finish',
            'output': self._truncate_for_display(str(finish.return_values))
        })

    def on_custom_event(self, event_type: str, data: Dict[str, Any]):
        """自定义事件"""
        self._emit(f'agent:{event_type}', data)
