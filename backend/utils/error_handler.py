"""统一错误处理机制"""
import logging
from typing import Optional, Dict, Any
from functools import wraps

logger = logging.getLogger(__name__)


class AgentError(Exception):
    """Agent 执行错误基类"""
    def __init__(self, message: str, user_message: Optional[str] = None, details: Optional[Dict] = None):
        self.message = message
        self.user_message = user_message or "任务执行失败，请重试"
        self.details = details or {}
        super().__init__(message)


class LLMError(AgentError):
    """LLM 调用错误"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            user_message="AI 服务调用失败，请检查配置或稍后重试",
            **kwargs
        )


class ToolError(AgentError):
    """工具执行错误"""
    def __init__(self, tool_name: str, message: str, **kwargs):
        super().__init__(
            f"工具 {tool_name} 执行失败: {message}",
            user_message=f"执行 {tool_name} 时出错，请重试",
            **kwargs
        )


class ValidationError(AgentError):
    """数据验证错误"""
    def __init__(self, field: str, message: str, **kwargs):
        super().__init__(
            f"字段 {field} 验证失败: {message}",
            user_message=f"输入数据不正确: {message}",
            **kwargs
        )


def handle_agent_error(e: Exception, task_id: str, context: str = "") -> Dict[str, Any]:
    """统一的错误处理函数"""
    if isinstance(e, AgentError):
        user_msg = e.user_message
        log_msg = e.message
        details = e.details
    else:
        user_msg = "系统错误，请联系管理员"
        log_msg = str(e)
        details = {}

    # 记录日志
    logger.error(f"[{context}] 任务 {task_id} 失败: {log_msg}", exc_info=not isinstance(e, AgentError))

    return {
        "success": False,
        "error": user_msg,
        "details": details if logger.isEnabledFor(logging.DEBUG) else None
    }


def with_error_handling(context: str = ""):
    """错误处理装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                task_id = kwargs.get('task_id', 'unknown')
                return handle_agent_error(e, task_id, context or func.__name__)
        return wrapper
    return decorator
