"""Agent API 路由 - 新版 Agent 驱动的创作接口"""
import logging
import uuid
import threading
from datetime import datetime
from flask import Blueprint, request, jsonify
from typing import Optional
from pathlib import Path

from backend.task_manager import get_task_manager, TaskStatus
from backend.config import DynamicConfig, get_config_manager

logger = logging.getLogger(__name__)

agent_bp = Blueprint('agent', __name__, url_prefix='/api/agent/v1')


# ============ P3-1: LLM 配置缓存（支持热更新） ============
class LLMProvider:
    """LLM 提供者 - 使用 ConfigManager 实现热更新"""

    _instance: Optional['LLMProvider'] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._llm = None
        self._config_hash: Optional[str] = None
        self._initialized = True

        # 注册配置变更回调
        config_manager = get_config_manager()
        config_manager.register_callback('text_providers', self._on_config_change)

    def _on_config_change(self, config_name: str, new_config: dict):
        """配置变更回调"""
        logger.info("检测到文本服务商配置变更，将在下次使用时重新创建 LLM 实例")
        self.invalidate()

    def get_llm(self):
        """获取 LLM 实例（带配置变更检测）"""
        try:
            # 获取当前配置
            config = DynamicConfig.get_text_provider_config()
            config_hash = str(hash(frozenset(config.items())))

            # 配置未变更且 LLM 已存在，直接返回
            if self._llm is not None and self._config_hash == config_hash:
                return self._llm

            # 重新加载配置
            self._llm = self._create_llm(config)
            self._config_hash = config_hash
            logger.info("LLM 实例已创建/更新")
            return self._llm

        except Exception as e:
            logger.error(f"获取 LLM 失败: {e}")
            raise

    def _create_llm(self, provider_config: dict):
        """创建 LLM 实例"""
        provider_type = provider_config.get('type', 'google_gemini')
        api_key = provider_config.get('api_key')
        model = provider_config.get('model', 'gemini-2.0-flash-exp')

        if not api_key:
            raise ValueError(f"服务商未配置 API Key")

        if provider_type == 'google_gemini':
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=model,
                google_api_key=api_key,
                temperature=provider_config.get('temperature', 0.7)
                # 注意：Google Gemini 的 streaming 模式需要特殊处理，暂不启用
            )
        else:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model,
                api_key=api_key,
                base_url=provider_config.get('base_url'),
                temperature=provider_config.get('temperature', 0.7),
                streaming=True  # OpenAI 兼容 API 支持流式输出
            )

    def invalidate(self):
        """使缓存失效"""
        self._llm = None
        self._config_hash = None


# 全局 LLM 提供者
_llm_provider: Optional[LLMProvider] = None


def get_llm_provider() -> LLMProvider:
    """获取 LLM 提供者单例"""
    global _llm_provider
    if _llm_provider is None:
        _llm_provider = LLMProvider()
    return _llm_provider


def _get_llm():
    """获取 LLM 实例（向后兼容）"""
    return get_llm_provider().get_llm()


# ============ P0-2: 异步执行 Agent 任务 ============
def _load_image_generation_config() -> bool:
    """加载图片生成配置，返回是否启用图片生成（使用动态配置）"""
    return DynamicConfig.is_image_generation_enabled()


def _execute_agent_task(task_id: str, topic: str, images: list):
    """在后台线程中执行 Agent 任务"""
    import asyncio
    task_manager = get_task_manager()

    try:
        # 更新状态为运行中
        task_manager.update_status(
            task_id,
            TaskStatus.RUNNING,
            current_step="初始化 Agent"
        )

        # 读取图片生成配置
        image_generation_enabled = _load_image_generation_config()
        logger.info(f"图片生成配置: enabled={image_generation_enabled}")

        # 根据配置获取工具
        from backend.tools import GenerateOutlineTool, GenerateImagesTool
        tools = [GenerateOutlineTool()]

        # 只有启用图片生成时才添加图片生成工具
        if image_generation_enabled:
            tools.append(GenerateImagesTool())
            logger.info("已注册图片生成工具")
        else:
            logger.info("图片生成已禁用，跳过注册图片生成工具")

        # 初始化 MCP 工具
        try:
            from backend.mcp import get_tool_registry, get_mcp_manager
            from backend.mcp.langchain import create_mcp_tools

            # 创建事件循环并初始化 MCP
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                mcp_manager = get_mcp_manager()
                loop.run_until_complete(mcp_manager.initialize())
                mcp_tools = create_mcp_tools()

                if mcp_tools:
                    tools.extend(mcp_tools)
                    logger.info(f"已加载 {len(mcp_tools)} 个 MCP 工具")
            finally:
                loop.close()

        except Exception as e:
            logger.warning(f"加载 MCP 工具失败: {e}，继续使用内置工具")

        # 获取 LLM
        llm = _get_llm()

        # 创建 Agent
        from backend.agents import CreativeDirectorAgent, WebSocketCallbackHandler
        from backend.socket_manager import get_socketio

        callbacks = []
        socketio = get_socketio()
        if socketio:
            callbacks.append(WebSocketCallbackHandler(socketio, task_id))
            logger.info(f"WebSocket 回调已注册: room={task_id}")

        agent = CreativeDirectorAgent(
            llm=llm,
            tools=tools,
            callbacks=callbacks,
            verbose=True,
            image_generation_enabled=image_generation_enabled
        )

        # 更新进度
        task_manager.update_status(
            task_id,
            TaskStatus.RUNNING,
            progress=10,
            current_step="开始创作"
        )

        # 执行任务
        result = agent.run_sync({
            "topic": topic,
            "images": images
        })

        # 任务完成
        if result.get("success"):
            task_manager.update_status(
                task_id,
                TaskStatus.COMPLETED,
                result=result,
                progress=100,
                current_step="创作完成"
            )
            logger.info(f"任务完成: {task_id}")
        else:
            task_manager.update_status(
                task_id,
                TaskStatus.FAILED,
                error=result.get("error", "未知错误"),
                current_step="创作失败"
            )
            logger.error(f"任务失败: {task_id}, 错误: {result.get('error')}")

    except Exception as e:
        logger.exception(f"任务执行异常: {task_id}")
        task_manager.update_status(
            task_id,
            TaskStatus.FAILED,
            error=str(e),
            current_step="执行异常"
        )

        # 通过 WebSocket 发送错误事件
        from backend.socket_manager import emit_to_task
        emit_to_task(task_id, 'agent:progress', {
            'type': 'error',
            'error': str(e),
            'message': '任务执行失败'
        })


@agent_bp.route('/init', methods=['POST'])
def init_task():
    """初始化任务（仅创建任务，不执行）- P1-3: 解决 taskId 时序问题"""
    try:
        data = request.get_json() or {}
        topic = data.get('topic', '')

        if not topic:
            return jsonify({
                "success": False,
                "error": "请提供创作主题"
            }), 400

        # 后端生成 task_id
        task_id = f"agent_{uuid.uuid4().hex[:8]}"

        # 创建任务记录
        task_manager = get_task_manager()
        task = task_manager.create_task(task_id, {
            "topic": topic,
            "images": data.get('images', [])
        })

        logger.info(f"任务已初始化: {task_id}, 主题: {topic}")

        return jsonify({
            "success": True,
            "task_id": task_id,
            "status": task["status"],
            "message": "任务已创建，请加入 WebSocket 房间后调用 /start 开始执行"
        })

    except Exception as e:
        logger.error(f"初始化任务失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@agent_bp.route('/start/<task_id>', methods=['POST'])
def start_task(task_id: str):
    """启动已初始化的任务（异步执行）"""
    try:
        task_manager = get_task_manager()

        # 使用原子操作：检查并更新状态，防止竞态条件
        with task_manager._task_lock:
            task = task_manager._tasks.get(task_id)

            if not task:
                return jsonify({
                    "success": False,
                    "error": "任务不存在"
                }), 404

            if task["status"] != TaskStatus.PENDING.value:
                logger.warning(f"任务 {task_id} 重复启动被阻止，当前状态: {task['status']}")
                return jsonify({
                    "success": False,
                    "error": f"任务已启动或已完成，当前状态: {task['status']}"
                }), 400

            # 立即更新状态为 RUNNING，防止重复启动
            task["status"] = TaskStatus.RUNNING.value
            task["started_at"] = datetime.now().isoformat()
            task["updated_at"] = datetime.now().isoformat()

            # 获取任务数据（在锁内获取，确保数据一致性）
            topic = task.get("topic", "")
            images = task.get("images", [])

        # 在锁外启动线程，避免阻塞其他请求
        thread = threading.Thread(
            target=_execute_agent_task,
            args=(task_id, topic, images),
            name=f"AgentTask-{task_id}"
        )
        thread.daemon = True
        thread.start()

        logger.info(f"任务已启动: {task_id}, 线程: {thread.name}")

        return jsonify({
            "success": True,
            "task_id": task_id,
            "status": "running",
            "message": "任务已开始执行，请通过 WebSocket 接收实时更新"
        })

    except Exception as e:
        logger.error(f"启动任务失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@agent_bp.route('/create', methods=['POST'])
def create_task():
    """创建并立即执行创作任务（向后兼容，改为异步）"""
    try:
        data = request.get_json() or {}
        topic = data.get('topic', '')
        images = data.get('images', [])
        # 优先使用前端传递的 task_id（向后兼容）
        task_id = data.get('task_id') or f"agent_{uuid.uuid4().hex[:8]}"

        if not topic:
            return jsonify({
                "success": False,
                "error": "请提供创作主题"
            }), 400

        logger.info(f"创建 Agent 任务: {task_id}, 主题: {topic}")

        # 创建任务记录
        task_manager = get_task_manager()
        task_manager.create_task(task_id, {
            "topic": topic,
            "images": images
        })

        # 异步执行任务
        thread = threading.Thread(
            target=_execute_agent_task,
            args=(task_id, topic, images),
            name=f"AgentTask-{task_id}"
        )
        thread.daemon = True
        thread.start()

        return jsonify({
            "success": True,
            "task_id": task_id,
            "status": "running",
            "message": "任务已开始执行，请通过 WebSocket 接收实时更新"
        })

    except Exception as e:
        logger.error(f"创建任务失败: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@agent_bp.route('/status/<task_id>', methods=['GET'])
def get_task_status(task_id: str):
    """获取任务状态"""
    task_manager = get_task_manager()
    task = task_manager.get_task(task_id)

    if not task:
        return jsonify({
            "success": False,
            "error": "任务不存在"
        }), 404

    return jsonify({
        "success": True,
        "task_id": task_id,
        "status": task["status"],
        "progress": task.get("progress", 0),
        "current_step": task.get("current_step"),
        "created_at": task.get("created_at"),
        "started_at": task.get("started_at"),
        "completed_at": task.get("completed_at"),
        "error": task.get("error"),
        "result": task.get("result") if task["status"] == TaskStatus.COMPLETED.value else None
    })


@agent_bp.route('/cancel/<task_id>', methods=['POST'])
def cancel_task(task_id: str):
    """取消任务"""
    task_manager = get_task_manager()
    task = task_manager.get_task(task_id)

    if not task:
        return jsonify({
            "success": False,
            "error": "任务不存在"
        }), 404

    if task["status"] in (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value, TaskStatus.CANCELLED.value):
        return jsonify({
            "success": False,
            "error": f"任务已结束，无法取消: {task['status']}"
        }), 400

    task_manager.update_status(task_id, TaskStatus.CANCELLED)

    # 通知前端
    from backend.socket_manager import emit_to_task
    emit_to_task(task_id, 'agent:progress', {
        'type': 'cancelled',
        'message': '任务已取消'
    })

    return jsonify({
        "success": True,
        "task_id": task_id,
        "status": "cancelled",
        "message": "任务已取消"
    })


@agent_bp.route('/list', methods=['GET'])
def list_tasks():
    """列出任务"""
    status_filter = request.args.get('status')
    limit = int(request.args.get('limit', 50))

    task_manager = get_task_manager()

    status = None
    if status_filter:
        try:
            status = TaskStatus(status_filter)
        except ValueError:
            pass

    tasks = task_manager.list_tasks(status=status, limit=limit)

    return jsonify({
        "success": True,
        "tasks": tasks,
        "count": len(tasks)
    })


@agent_bp.route('/tools', methods=['GET'])
def list_tools():
    """列出可用工具"""
    from backend.mcp import get_tool_registry
    registry = get_tool_registry()

    return jsonify({
        "tools": registry.list_tools()
    })
