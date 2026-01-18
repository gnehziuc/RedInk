"""线程池管理器 - 替代 daemon 线程，防止资源泄露"""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, Callable, Any, Optional

logger = logging.getLogger(__name__)


class AgentThreadPool:
    """Agent 任务线程池管理器"""

    _instance: Optional['AgentThreadPool'] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, max_workers: int = 4):
        if self._initialized:
            return

        self.executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="AgentTask"
        )
        self.futures: Dict[str, Future] = {}
        self._initialized = True
        logger.info(f"线程池已初始化，最大工作线程数: {max_workers}")

    def submit_task(
        self,
        task_id: str,
        func: Callable,
        *args,
        **kwargs
    ) -> Future:
        """提交任务到线程池"""
        if task_id in self.futures:
            logger.warning(f"任务 {task_id} 已存在，将被覆盖")

        future = self.executor.submit(func, *args, **kwargs)
        self.futures[task_id] = future

        # 添加完成回调
        future.add_done_callback(lambda f: self._on_task_complete(task_id, f))

        logger.info(f"任务已提交到线程池: {task_id}")
        return future

    def _on_task_complete(self, task_id: str, future: Future):
        """任务完成回调"""
        try:
            if future.exception():
                logger.error(f"任务 {task_id} 执行异常: {future.exception()}")
            else:
                logger.info(f"任务 {task_id} 执行完成")
        finally:
            # 清理已完成的任务
            self.futures.pop(task_id, None)

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        future = self.futures.get(task_id)
        if future:
            cancelled = future.cancel()
            if cancelled:
                self.futures.pop(task_id, None)
                logger.info(f"任务已取消: {task_id}")
            return cancelled
        return False

    def get_task_status(self, task_id: str) -> Optional[str]:
        """获取任务状态"""
        future = self.futures.get(task_id)
        if not future:
            return None

        if future.done():
            if future.exception():
                return "failed"
            return "completed"
        elif future.cancelled():
            return "cancelled"
        else:
            return "running"

    def shutdown(self, wait: bool = True):
        """关闭线程池"""
        logger.info("正在关闭线程池...")
        self.executor.shutdown(wait=wait)
        self.futures.clear()


# 全局单例
_thread_pool: Optional[AgentThreadPool] = None


def get_thread_pool() -> AgentThreadPool:
    """获取线程池单例"""
    global _thread_pool
    if _thread_pool is None:
        _thread_pool = AgentThreadPool()
    return _thread_pool
