"""任务状态管理器 - 管理 Agent 任务的生命周期和状态"""
import logging
import threading
from typing import Any, Dict, Optional, List
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"       # 待处理
    RUNNING = "running"       # 执行中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 失败
    CANCELLED = "cancelled"   # 已取消


class TaskManager:
    """任务状态管理器 - 线程安全的任务状态存储"""

    _instance: Optional['TaskManager'] = None
    _lock = threading.Lock()

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._task_lock = threading.Lock()
        self._initialized = True
        logger.info("TaskManager 初始化完成")

    def create_task(self, task_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建新任务"""
        with self._task_lock:
            now = datetime.now().isoformat()
            task = {
                "task_id": task_id,
                "status": TaskStatus.PENDING.value,
                "created_at": now,
                "updated_at": now,
                "started_at": None,
                "completed_at": None,
                "result": None,
                "error": None,
                "progress": 0,
                "current_step": None,
                **data
            }
            self._tasks[task_id] = task
            logger.info(f"任务已创建: {task_id}")
            return task.copy()

    def update_status(
        self,
        task_id: str,
        status: TaskStatus,
        result: Any = None,
        error: str = None,
        progress: int = None,
        current_step: str = None
    ) -> Optional[Dict[str, Any]]:
        """更新任务状态"""
        with self._task_lock:
            if task_id not in self._tasks:
                logger.warning(f"任务不存在: {task_id}")
                return None

            task = self._tasks[task_id]
            now = datetime.now().isoformat()

            task["status"] = status.value
            task["updated_at"] = now

            if status == TaskStatus.RUNNING and task["started_at"] is None:
                task["started_at"] = now

            if status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                task["completed_at"] = now

            if result is not None:
                task["result"] = result

            if error is not None:
                task["error"] = error

            if progress is not None:
                task["progress"] = min(100, max(0, progress))

            if current_step is not None:
                task["current_step"] = current_step

            logger.debug(f"任务状态更新: {task_id} -> {status.value}")
            return task.copy()

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务信息"""
        with self._task_lock:
            task = self._tasks.get(task_id)
            return task.copy() if task else None

    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """列出任务"""
        with self._task_lock:
            tasks = list(self._tasks.values())

            if status:
                tasks = [t for t in tasks if t["status"] == status.value]

            # 按创建时间倒序排序
            tasks.sort(key=lambda x: x["created_at"], reverse=True)

            return [t.copy() for t in tasks[:limit]]

    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        with self._task_lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                logger.info(f"任务已删除: {task_id}")
                return True
            return False

    def cleanup_old_tasks(self, max_age_hours: int = 24) -> int:
        """清理过期任务"""
        with self._task_lock:
            now = datetime.now()
            to_delete = []

            for task_id, task in self._tasks.items():
                created_at = datetime.fromisoformat(task["created_at"])
                age = (now - created_at).total_seconds() / 3600

                if age > max_age_hours:
                    to_delete.append(task_id)

            for task_id in to_delete:
                del self._tasks[task_id]

            if to_delete:
                logger.info(f"清理了 {len(to_delete)} 个过期任务")

            return len(to_delete)


# 全局单例
_task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """获取任务管理器单例"""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager
