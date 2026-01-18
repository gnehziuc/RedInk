"""大纲生成工具 - 封装 OutlineService"""
import json
import logging
import re
from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


# ============ 结构化上下文模型 ============

class StylePreference(BaseModel):
    """写作风格偏好"""
    tone: Optional[str] = Field(
        default=None,
        description="语气风格，如：活泼、专业、温馨、幽默、严肃、轻松"
    )
    language: Optional[str] = Field(
        default=None,
        description="语言特点，如：口语化、书面语、网络流行语、文艺范"
    )
    emotion: Optional[str] = Field(
        default=None,
        description="情感基调，如：积极向上、治愈系、励志、感性、理性"
    )


class TargetAudience(BaseModel):
    """目标受众信息"""
    demographics: Optional[str] = Field(
        default=None,
        description="人口统计特征，如：年轻女性、职场新人、宝妈、学生党"
    )
    interests: Optional[List[str]] = Field(
        default=None,
        description="兴趣标签列表，如：['美妆', '穿搭', '健身']"
    )
    pain_points: Optional[List[str]] = Field(
        default=None,
        description="痛点需求列表，如：['预算有限', '时间紧张', '选择困难']"
    )


class ContentRequirement(BaseModel):
    """内容要求"""
    must_include: Optional[List[str]] = Field(
        default=None,
        description="必须包含的元素，如：['价格信息', '使用步骤', '效果对比']"
    )
    must_avoid: Optional[List[str]] = Field(
        default=None,
        description="必须避免的内容，如：['敏感词', '竞品名称', '夸大宣传']"
    )
    word_count: Optional[str] = Field(
        default=None,
        description="篇幅要求，如：'简短精炼'、'详细完整'、'3-5页'"
    )
    format_hints: Optional[List[str]] = Field(
        default=None,
        description="格式提示，如：['多用emoji', '分点列举', '图文结合']"
    )


class ReferenceInfo(BaseModel):
    """参考信息"""
    similar_content: Optional[str] = Field(
        default=None,
        description="相似内容参考，如：'参考某某博主的风格'"
    )
    keywords: Optional[List[str]] = Field(
        default=None,
        description="关键词列表，用于 SEO 或搜索优化"
    )
    hashtags: Optional[List[str]] = Field(
        default=None,
        description="推荐使用的话题标签"
    )


class ContentMetadata(BaseModel):
    """内容元数据"""
    content_type: Optional[str] = Field(
        default="小红书图文",
        description="内容类型，如：教程、测评、分享、种草、避雷、攻略"
    )
    purpose: Optional[str] = Field(
        default=None,
        description="创作目的，如：品牌推广、知识分享、经验总结、产品种草"
    )
    urgency: Optional[str] = Field(
        default=None,
        description="时效性要求，如：热点追踪、季节性内容、长期常青"
    )
    platform: Optional[str] = Field(
        default="小红书",
        description="目标平台，如：小红书、抖音、微信公众号"
    )


class CreationContext(BaseModel):
    """创作上下文 - 完整的结构化上下文信息"""
    style: Optional[StylePreference] = Field(
        default=None,
        description="写作风格偏好"
    )
    audience: Optional[TargetAudience] = Field(
        default=None,
        description="目标受众信息"
    )
    requirements: Optional[ContentRequirement] = Field(
        default=None,
        description="内容要求和约束"
    )
    references: Optional[ReferenceInfo] = Field(
        default=None,
        description="参考信息"
    )
    metadata: Optional[ContentMetadata] = Field(
        default=None,
        description="内容元数据"
    )
    raw_context: Optional[str] = Field(
        default=None,
        description="原始上下文文本（兜底，用于无法结构化的信息）"
    )


# ============ 工具输入模型 ============

class GenerateOutlineInput(BaseModel):
    """大纲生成工具输入"""
    topic: str = Field(description="创作主题或用户需求描述")
    context: Optional[str] = Field(
        default=None,
        description="创作上下文信息（纯文本字符串）"
    )
    images: Optional[List[bytes]] = Field(default=None, description="参考图片列表（可选）")


class GenerateOutlineTool(BaseTool):
    """大纲生成工具"""
    name: str = "generate_outline"
    description: str = """根据用户提供的主题生成小红书内容大纲。

⚠️ 重要提示：此工具每次对话只能调用一次。如果已经生成过大纲，请勿重复调用。

输入参数：
- topic（必需）：创作主题或用户需求描述
- context（可选）：创作上下文信息（纯文本字符串）
- images（可选）：参考图片列表

输出：包含封面和内容页的结构化大纲

使用示例：
{
  "topic": "分享我的早餐食谱",
  "context": "语气要活泼，面向年轻女性，必须包含食材清单和制作步骤"
}"""
    args_schema: Type[BaseModel] = GenerateOutlineInput

    def _run(
        self,
        topic: str,
        context: Optional[str] = None,
        images: Optional[List[bytes]] = None
    ) -> str:
        """同步执行大纲生成，返回 JSON 字符串"""
        try:
            from backend.services.outline import get_outline_service
            service = get_outline_service()

            # 将结构化上下文信息与主题结合
            enhanced_topic = self._build_enhanced_topic(topic, context)

            result = service.generate_outline(enhanced_topic, images)

            if result.get("success"):
                pages = result.get("pages", [])
                outline_text = result.get("outline", "")

                # 提取标题：优先从封面页提取，否则使用主题
                title = self._extract_title(pages, outline_text, topic)

                # 生成摘要：从大纲内容提取简短描述
                summary = self._extract_summary(pages, outline_text)

                # 格式化页面数据，确保包含 title 字段
                formatted_pages = self._format_pages(pages)

                output_data = {
                    "success": True,
                    "title": title,
                    "summary": summary,
                    "outline": outline_text,
                    "pages": formatted_pages,
                    "page_count": len(formatted_pages)
                }
                return json.dumps(output_data, ensure_ascii=False)
            else:
                error_data = {
                    "success": False,
                    "error": result.get("error", "未知错误")
                }
                return json.dumps(error_data, ensure_ascii=False)
        except Exception as e:
            logger.error(f"大纲生成工具错误: {e}")
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    def _extract_title(self, pages: List[Dict], outline_text: str, fallback: str) -> str:
        """从大纲中提取标题"""
        # 尝试从封面页提取标题
        for page in pages:
            if page.get("type") == "cover":
                content = page.get("content", "")
                # 尝试匹配标题模式
                title_match = re.search(r'标题[：:]\s*(.+?)(?:\n|$)', content)
                if title_match:
                    return title_match.group(1).strip()
                # 尝试匹配第一行非标签内容
                lines = content.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('[') and not line.startswith('#'):
                        # 清理标签标记
                        clean_line = re.sub(r'\[.*?\]', '', line).strip()
                        if clean_line and len(clean_line) > 2:
                            return clean_line[:50]  # 限制长度

        # 尝试从大纲文本提取标题
        title_match = re.search(r'标题[：:]\s*(.+?)(?:\n|$)', outline_text)
        if title_match:
            return title_match.group(1).strip()

        # 使用主题作为回退
        return fallback[:50] if len(fallback) > 50 else fallback

    def _extract_summary(self, pages: List[Dict], outline_text: str) -> str:
        """从大纲中提取摘要"""
        # 尝试从封面页提取摘要/描述
        for page in pages:
            if page.get("type") == "cover":
                content = page.get("content", "")
                # 尝试匹配摘要/描述模式
                summary_match = re.search(r'(?:摘要|描述|简介)[：:]\s*(.+?)(?:\n|$)', content)
                if summary_match:
                    return summary_match.group(1).strip()

        # 尝试从大纲文本提取
        summary_match = re.search(r'(?:摘要|描述|简介)[：:]\s*(.+?)(?:\n|$)', outline_text)
        if summary_match:
            return summary_match.group(1).strip()

        # 使用第一页内容的前100字符作为摘要
        if pages:
            first_content = pages[0].get("content", "")
            # 清理标签
            clean_content = re.sub(r'\[.*?\]', '', first_content).strip()
            if clean_content:
                return clean_content[:100] + ('...' if len(clean_content) > 100 else '')

        return ""

    def _format_pages(self, pages: List[Dict]) -> List[Dict]:
        """格式化页面数据，确保符合前端期望的格式"""
        formatted = []
        for page in pages:
            content = page.get("content", "")
            page_type = page.get("type", "content")

            # 尝试提取页面标题
            page_title = None
            title_match = re.search(r'标题[：:]\s*(.+?)(?:\n|$)', content)
            if title_match:
                page_title = title_match.group(1).strip()
            else:
                # 使用类型作为标题
                type_names = {
                    "cover": "封面",
                    "content": "内容页",
                    "summary": "总结页"
                }
                page_title = type_names.get(page_type, f"第 {page.get('index', 0) + 1} 页")

            formatted.append({
                "index": page.get("index", len(formatted)),
                "title": page_title,
                "content": content,
                "type": page_type
            })
        return formatted

    def _build_enhanced_topic(self, topic: str, context: Optional[str]) -> str:
        """将上下文信息与主题结合"""
        if not context:
            return topic
        return f"{topic}\n\n{context}"


    
    async def _arun(
        self,
        topic: str,
        context: Optional[str] = None,
        images: Optional[List[bytes]] = None
    ) -> str:
        """异步执行（目前使用同步实现）"""
        return self._run(topic, context, images)
