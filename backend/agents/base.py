"""Agent 基类 - 日志、回调、错误处理、重试机制"""
import logging
import time
from abc import ABC, abstractmethod
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar
from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger(__name__)

T = TypeVar('T')


def retry_on_failure(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Callable:
    """P2-3: 重试装饰器

    Args:
        max_retries: 最大重试次数
        delay: 初始延迟时间（秒）
        backoff: 退避因子
        exceptions: 需要重试的异常类型
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (backoff ** attempt)
                        logger.warning(
                            f"[重试 {attempt + 1}/{max_retries}] {func.__name__} 失败: {e}, "
                            f"{wait_time:.1f}秒后重试"
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(f"{func.__name__} 达到最大重试次数: {e}")
            raise last_error
        return wrapper
    return decorator


async def async_retry_on_failure(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Callable:
    """异步重试装饰器"""
    import asyncio

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_error = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (backoff ** attempt)
                        logger.warning(
                            f"[重试 {attempt + 1}/{max_retries}] {func.__name__} 失败: {e}, "
                            f"{wait_time:.1f}秒后重试"
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"{func.__name__} 达到最大重试次数: {e}")
            raise last_error
        return wrapper
    return decorator


class BaseRedInkAgent(ABC):
    """RedInk Agent 基类"""

    # 默认重试配置
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_DELAY = 1.0
    DEFAULT_RETRY_BACKOFF = 2.0

    def __init__(
        self,
        callbacks: Optional[List[BaseCallbackHandler]] = None,
        verbose: bool = False,
        max_retries: int = None,
        retry_delay: float = None
    ):
        self.callbacks = callbacks or []
        self.verbose = verbose
        self.max_retries = max_retries or self.DEFAULT_MAX_RETRIES
        self.retry_delay = retry_delay or self.DEFAULT_RETRY_DELAY
        self._setup_logging()

    def _setup_logging(self):
        """配置日志"""
        if self.verbose:
            logging.getLogger('langchain').setLevel(logging.DEBUG)

    @abstractmethod
    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行 Agent 任务"""
        pass

    def _handle_error(self, error: Exception, context: str = "") -> Dict[str, Any]:
        """统一错误处理"""
        error_msg = str(error)
        logger.error(f"Agent 错误 [{context}]: {error_msg}")

        # 通过回调发送错误事件
        self._emit_event("progress", {
            "type": "error",
            "error": error_msg,
            "context": context,
            "message": "执行过程中发生错误"
        })

        return {
            "success": False,
            "error": error_msg,
            "context": context
        }

    def _emit_event(self, event_type: str, data: Dict[str, Any]):
        """向所有回调发送事件"""
        logger.debug(f"发送事件: agent:{event_type}, callbacks数量: {len(self.callbacks)}")
        for callback in self.callbacks:
            if hasattr(callback, 'on_custom_event'):
                callback.on_custom_event(event_type, data)
                logger.debug(f"事件已发送: agent:{event_type}")

    def _retry_operation(
        self,
        operation: Callable[[], T],
        operation_name: str = "operation"
    ) -> T:
        """带重试的操作执行

        Args:
            operation: 要执行的操作（无参数的可调用对象）
            operation_name: 操作名称（用于日志）

        Returns:
            操作的返回值

        Raises:
            最后一次失败的异常
        """
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return operation()
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (self.DEFAULT_RETRY_BACKOFF ** attempt)
                    logger.warning(
                        f"[重试 {attempt + 1}/{self.max_retries}] {operation_name} 失败: {e}, "
                        f"{wait_time:.1f}秒后重试"
                    )

                    # 通知前端正在重试
                    self._emit_event("progress", {
                        "type": "retry",
                        "attempt": attempt + 1,
                        "max_retries": self.max_retries,
                        "error": str(e),
                        "message": f"正在重试 ({attempt + 1}/{self.max_retries})..."
                    })

                    time.sleep(wait_time)
                else:
                    logger.error(f"{operation_name} 达到最大重试次数: {e}")

        raise last_error
