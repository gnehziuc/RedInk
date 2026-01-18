"""图片生成工具 - 封装 ImageService，支持配置控制"""
import json
import logging
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


def _load_image_config() -> Dict[str, Any]:
    """加载图片生成配置"""
    config_path = Path(__file__).parent.parent.parent.parent / 'image_providers.yaml'
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"加载图片配置失败: {e}")
    return {}


class GenerateImagesInput(BaseModel):
    """图片生成工具输入"""
    pages: List[Dict[str, Any]] = Field(description="页面列表，每个页面包含 index, type, content")
    task_id: Optional[str] = Field(default=None, description="任务ID（可选，用于关联历史记录）")
    full_outline: Optional[str] = Field(default="", description="完整大纲文本")
    user_topic: Optional[str] = Field(default="", description="用户原始输入")


class GenerateImagesTool(BaseTool):
    """图片生成工具"""
    name: str = "generate_images"
    description: str = """根据大纲页面生成小红书配图。
    输入：页面列表（必需）、任务ID（可选）、完整大纲（可选）
    输出：生成的图片URL列表（如果启用图片生成），或图片描述/提示词（如果禁用图片生成）"""
    args_schema: Type[BaseModel] = GenerateImagesInput

    # 存储生成结果的回调
    result_callback: Optional[callable] = None

    def _generate_image_prompts(self, pages: List[Dict[str, Any]], user_topic: str) -> List[Dict[str, Any]]:
        """生成图片描述/提示词（不实际调用图片 API）"""
        prompts = []
        for page in pages:
            page_index = page.get("index", 0)
            page_type = page.get("type", "content")
            page_content = page.get("content", "")

            # 根据页面内容生成简化的图片描述
            if page_type == "cover":
                prompt = f"小红书封面图：{user_topic}\n内容概要：{page_content[:200]}"
            else:
                prompt = f"小红书内容页 {page_index}：{page_content[:300]}"

            prompts.append({
                "index": page_index,
                "type": page_type,
                "prompt": prompt,
                "description": f"页面 {page_index + 1} 的图片描述",
                "url": None  # 未生成实际图片
            })

        return prompts

    def _run(
        self,
        pages: List[Dict[str, Any]],
        task_id: Optional[str] = None,
        full_outline: str = "",
        user_topic: str = ""
    ) -> str:
        """同步执行图片生成，返回 JSON 字符串"""
        try:
            # 加载配置检查是否启用图片生成
            config = _load_image_config()
            generate_enabled = config.get('generate_images_enabled', True)

            logger.info(f"图片生成工具调用: pages={len(pages)}, enabled={generate_enabled}")

            # 如果禁用图片生成，仅返回提示词
            if not generate_enabled:
                logger.info("图片生成已禁用，返回图片描述/提示词")
                prompts = self._generate_image_prompts(pages, user_topic)
                result = {
                    "success": True,
                    "mode": "prompts_only",
                    "message": "图片生成已禁用，仅返回图片描述",
                    "prompts": prompts,
                    "images": prompts,  # 兼容前端
                    "total": len(prompts),
                    "completed": len(prompts),
                    "failed": 0
                }
                return json.dumps(result, ensure_ascii=False)

            # 启用图片生成，调用实际服务
            from backend.services.image import get_image_service
            service = get_image_service()

            # 收集所有生成结果
            results = []
            generated_images = []
            failed_indices = []

            for event in service.generate_images(
                pages=pages,
                task_id=task_id,
                full_outline=full_outline,
                user_topic=user_topic
            ):
                results.append(event)

                # 处理完成事件
                if event.get("event") == "complete":
                    data = event.get("data", {})
                    generated_images.append({
                        "index": data.get("index"),
                        "url": data.get("image_url")
                    })

                # 处理错误事件
                elif event.get("event") == "error":
                    data = event.get("data", {})
                    failed_indices.append(data.get("index"))

                # 调用回调（如果有）
                if self.result_callback:
                    self.result_callback(event)

            # 获取最终结果
            finish_event = next(
                (e for e in results if e.get("event") == "finish"),
                None
            )

            if finish_event:
                data = finish_event.get("data", {})
                result = {
                    "success": data.get("success", False),
                    "mode": "generate",
                    "task_id": data.get("task_id"),
                    "images": generated_images,
                    "total": data.get("total", 0),
                    "completed": data.get("completed", 0),
                    "failed": data.get("failed", 0),
                    "failed_indices": failed_indices
                }
                return json.dumps(result, ensure_ascii=False)

            result = {
                "success": len(generated_images) > 0,
                "mode": "generate",
                "images": generated_images,
                "failed_indices": failed_indices
            }
            return json.dumps(result, ensure_ascii=False)

        except Exception as e:
            logger.error(f"图片生成工具错误: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    async def _arun(
        self,
        pages: List[Dict[str, Any]],
        task_id: Optional[str] = None,
        full_outline: str = "",
        user_topic: str = ""
    ) -> str:
        """异步执行（目前使用同步实现）"""
        return self._run(pages, task_id, full_outline, user_topic)
