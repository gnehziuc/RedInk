"""WebSocket 管理器 - 处理实时通信"""
import logging
from typing import Dict, Optional, Callable, Any
from flask_socketio import SocketIO, emit, join_room, leave_room

logger = logging.getLogger(__name__)

# 全局 SocketIO 实例
socketio: Optional[SocketIO] = None

# P2-2: 追加指令处理器注册表
_instruction_handlers: Dict[str, Callable[[str, str], Any]] = {}


def register_instruction_handler(task_id: str, handler: Callable[[str, str], Any]):
    """注册追加指令处理器"""
    _instruction_handlers[task_id] = handler
    logger.debug(f"注册追加指令处理器: {task_id}")


def unregister_instruction_handler(task_id: str):
    """注销追加指令处理器"""
    if task_id in _instruction_handlers:
        del _instruction_handlers[task_id]
        logger.debug(f"注销追加指令处理器: {task_id}")


def init_socketio(app) -> SocketIO:
    """初始化 SocketIO"""
    global socketio
    socketio = SocketIO(
        app,
        cors_allowed_origins="*",
        async_mode='threading',
        logger=False,  # 关闭 socketio 日志
        engineio_logger=False  # 关闭 engineio 日志（避免打印 AI 回复的 token）
    )

    # 注册事件处理器
    @socketio.on('connect')
    def handle_connect():
        logger.info(f"WebSocket 客户端连接")
        emit('connected', {'status': 'ok'})

    @socketio.on('disconnect')
    def handle_disconnect():
        logger.info(f"WebSocket 客户端断开")

    @socketio.on('join_task')
    def handle_join_task(data):
        """加入任务房间，接收该任务的实时更新"""
        task_id = data.get('task_id')
        if task_id:
            join_room(task_id)
            logger.info(f"客户端加入任务房间: {task_id}")
            emit('joined', {'task_id': task_id, 'status': 'ok'})

    @socketio.on('leave_task')
    def handle_leave_task(data):
        """离开任务房间"""
        task_id = data.get('task_id')
        if task_id:
            leave_room(task_id)
            logger.info(f"客户端离开任务房间: {task_id}")
            emit('left', {'task_id': task_id, 'status': 'ok'})

    # P2-2: 追加指令处理
    @socketio.on('send_instruction')
    def handle_send_instruction(data):
        """接收追加指令"""
        task_id = data.get('task_id')
        instruction = data.get('instruction', '')

        if not task_id or not instruction:
            emit('instruction_error', {
                'error': '缺少任务 ID 或指令内容',
                'task_id': task_id
            })
            return

        logger.info(f"收到追加指令: task={task_id}, instruction={instruction[:50]}...")

        # 查找处理器
        handler = _instruction_handlers.get(task_id)
        if handler:
            try:
                result = handler(task_id, instruction)
                emit('instruction_received', {
                    'task_id': task_id,
                    'status': 'ok',
                    'result': result
                })
            except Exception as e:
                logger.error(f"处理追加指令失败: {e}")
                emit('instruction_error', {
                    'task_id': task_id,
                    'error': str(e)
                })
        else:
            # 没有处理器，可能任务已完成或不支持追加指令
            emit('instruction_error', {
                'task_id': task_id,
                'error': '任务不存在或不支持追加指令'
            })

    # P1-3: 确认房间加入的事件
    @socketio.on('confirm_room')
    def handle_confirm_room(data):
        """确认客户端已加入房间（用于解决时序问题）"""
        task_id = data.get('task_id')
        if task_id:
            emit('room_confirmed', {
                'task_id': task_id,
                'status': 'ready'
            }, room=task_id)
            logger.debug(f"房间确认: {task_id}")

    logger.info("WebSocket 初始化完成")
    return socketio


def get_socketio() -> Optional[SocketIO]:
    """获取 SocketIO 实例"""
    return socketio


def emit_to_task(task_id: str, event: str, data: Dict):
    """向特定任务房间发送事件"""
    if socketio:
        socketio.emit(event, data, room=task_id)


def emit_error_to_task(task_id: str, error: str, context: str = ""):
    """向特定任务发送错误事件"""
    if socketio:
        socketio.emit('agent:progress', {
            'type': 'error',
            'error': error,
            'context': context,
            'message': '任务执行失败'
        }, room=task_id)
