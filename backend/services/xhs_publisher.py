# -*- coding: utf-8 -*-
"""
小红书图文发布服务

使用 Playwright 自动化实现图文内容发布到小红书创作者平台
"""
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.async_api import Playwright, async_playwright, Page

from backend.account_utils.config import COOKIES_DIR, LOCAL_CHROME_HEADLESS, STEALTH_JS_PATH

logger = logging.getLogger(__name__)


async def set_init_script(context):
    """设置浏览器初始化脚本（反检测）"""
    if STEALTH_JS_PATH.exists():
        await context.add_init_script(path=STEALTH_JS_PATH)
    return context


class XiaoHongShuImagePost:
    """小红书图文笔记发布类"""
    
    def __init__(
        self,
        title: str,
        content: str,
        image_paths: list[str],
        tags: list[str],
        account_file: str,
        publish_date: Optional[datetime] = None
    ):
        """
        初始化图文发布任务
        
        Args:
            title: 标题 (最多20字)
            content: 正文内容 (最多1000字)
            image_paths: 图片文件路径列表 (最多18张)
            tags: 话题标签列表
            account_file: Cookie 文件路径
            publish_date: 定时发布时间 (可选, None 表示立即发布)
        """
        self.title = title[:20]  # 限制20字
        self.content = content[:1000]  # 限制1000字
        self.image_paths = image_paths[:18]  # 最多18张图
        self.tags = tags
        self.account_file = account_file
        self.publish_date = publish_date
        self.headless = LOCAL_CHROME_HEADLESS
        self.date_format = '%Y-%m-%d %H:%M'
    
    async def _wait_for_upload_complete(self, page: Page, timeout: int = 120):
        """等待图片上传完成"""
        logger.info("等待图片上传完成...")
        start_time = asyncio.get_event_loop().time()
        
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                raise TimeoutError("图片上传超时")
            
            # 检查是否有上传进度或已完成的指示
            # 小红书图片上传成功后会显示图片预览
            try:
                # 尝试多种选择器来检测已上传的图片
                selectors = [
                    'div.image-item',
                    'div.upload-item',
                    'div[class*="image"] img',
                    'div[class*="upload"] img',
                    'div[class*="preview"] img',
                    '.c-image-item',
                    '[class*="imgItem"]',
                    '.upload-list img'
                ]
                
                for selector in selectors:
                    try:
                        count = await page.locator(selector).count()
                        if count >= len(self.image_paths):
                            logger.info(f"检测到 {count} 张图片已上传 (选择器: {selector})")
                            return
                    except Exception:
                        pass
                
                # 检查是否有上传中的进度条消失
                uploading = await page.locator('[class*="uploading"], [class*="progress"]').count()
                if uploading == 0:
                    # 没有上传进度条了，检查是否有任何图片
                    for selector in selectors:
                        try:
                            if await page.locator(selector).count() > 0:
                                logger.info("上传进度完成，检测到图片元素")
                                return
                        except Exception:
                            pass
                
            except Exception as e:
                logger.debug(f"检测上传状态时出错: {e}")
            
            await asyncio.sleep(1)
    
    async def _fill_title(self, page: Page):
        """填写标题"""
        logger.info(f"填写标题: {self.title}")
        
        # 尝试定位标题输入框
        title_input = page.locator('input.d-text[placeholder*="标题"], input[placeholder*="标题"]')
        if await title_input.count() > 0:
            await title_input.fill(self.title)
        else:
            # 备选方案：使用 contenteditable 元素
            title_container = page.locator('div.title-container input, div[class*="title"] input')
            if await title_container.count() > 0:
                await title_container.first.fill(self.title)
    
    async def _fill_content(self, page: Page):
        """填写正文内容"""
        logger.info("填写正文内容...")
        
        # 定位内容编辑器 (通常是 ProseMirror 或类似的富文本编辑器)
        content_editor = page.locator('.ql-editor, .ProseMirror, div[contenteditable="true"]')
        if await content_editor.count() > 0:
            await content_editor.first.click()
            await page.keyboard.type(self.content)
    
    async def _add_tags(self, page: Page):
        """添加话题标签"""
        if not self.tags:
            return
        
        logger.info(f"添加话题标签: {self.tags}")
        
        # 定位内容编辑器区域添加标签
        content_editor = page.locator('.ql-editor, .ProseMirror, div[contenteditable="true"]')
        if await content_editor.count() > 0:
            await content_editor.first.click()
            
            for tag in self.tags:
                await page.keyboard.type(f" #{tag}")
                await page.keyboard.press("Space")
                await asyncio.sleep(0.5)
    
    async def _set_schedule_time(self, page: Page):
        """设置定时发布时间"""
        if not self.publish_date:
            return
        
        logger.info(f"设置定时发布: {self.publish_date}")
        
        # 点击定时发布选项
        schedule_label = page.locator("label:has-text('定时发布')")
        if await schedule_label.count() > 0:
            await schedule_label.click()
            await asyncio.sleep(1)
            
            # 输入时间
            publish_date_str = self.publish_date.strftime(self.date_format)
            time_input = page.locator('.el-input__inner[placeholder*="选择"], input[placeholder*="时间"]')
            if await time_input.count() > 0:
                await time_input.click()
                await page.keyboard.press("Control+KeyA")
                await page.keyboard.type(publish_date_str)
                await page.keyboard.press("Enter")
                await asyncio.sleep(1)
    
    async def upload(self, playwright: Playwright) -> dict:
        """
        执行发布流程
        
        Returns:
            dict: 发布结果 {"success": bool, "message": str, "note_id": str|None}
        """
        browser = None
        context = None
        
        try:
            # 1. 启动浏览器
            logger.info("启动浏览器...")
            browser = await playwright.chromium.launch(headless=self.headless)
            
            # 2. 加载 Cookie 创建上下文
            context = await browser.new_context(
                viewport={"width": 1600, "height": 900},
                storage_state=self.account_file
            )
            context = await set_init_script(context)
            
            # 3. 创建页面并导航到发布页
            page = await context.new_page()
            logger.info("导航到小红书图文发布页...")
            await page.goto("https://creator.xiaohongshu.com/publish/publish?source=official&from=menu&target=image")
            
            # 等待页面加载
            await page.wait_for_load_state("networkidle", timeout=15000)
            
            # 检查是否需要登录
            if await page.get_by_text('手机号登录').count() or await page.get_by_text('扫码登录').count():
                logger.error("Cookie 已失效，需要重新登录")
                return {"success": False, "message": "Cookie 已失效，请重新登录", "note_id": None}
            
            # 4. 上传图片
            logger.info(f"上传 {len(self.image_paths)} 张图片...")
            upload_input = page.locator("input.upload-input, input[type='file']")
            if await upload_input.count() > 0:
                await upload_input.set_input_files(self.image_paths)
            else:
                logger.error("未找到图片上传输入框")
                return {"success": False, "message": "未找到图片上传区域", "note_id": None}
            
            # 5. 等待上传完成
            await self._wait_for_upload_complete(page)
            await asyncio.sleep(2)
            
            # 6. 填写标题
            await self._fill_title(page)
            
            # 7. 填写内容和标签
            await self._fill_content(page)
            await self._add_tags(page)
            
            # 8. 设置定时发布 (如果需要)
            await self._set_schedule_time(page)
            
            # 9. 点击发布按钮
            logger.info("点击发布按钮...")
            if self.publish_date:
                publish_btn = page.locator('button:has-text("定时发布")')
            else:
                publish_btn = page.locator('button.publishBtn, button:has-text("发布")')
            
            if await publish_btn.count() > 0:
                await publish_btn.first.click()
            else:
                logger.error("未找到发布按钮")
                return {"success": False, "message": "未找到发布按钮", "note_id": None}
            
            # 10. 等待发布成功
            try:
                await page.wait_for_url("**/publish/success**", timeout=30000)
                logger.info("✅ 图文笔记发布成功!")
                
                # 保存更新后的 Cookie
                await context.storage_state(path=self.account_file)
                logger.info("Cookie 已更新")
                
                return {"success": True, "message": "发布成功", "note_id": None}
                
            except Exception as e:
                logger.warning(f"等待发布成功页面超时: {e}")
                # 可能发布成功但页面没有跳转，截图保存
                await page.screenshot(path="publish_result.png")
                return {"success": False, "message": f"发布状态未知: {str(e)}", "note_id": None}
        
        except Exception as e:
            logger.error(f"发布过程出错: {e}")
            return {"success": False, "message": f"发布失败: {str(e)}", "note_id": None}
        
        finally:
            if context:
                await context.close()
            if browser:
                await browser.close()
    
    async def main(self):
        """主入口函数"""
        async with async_playwright() as playwright:
            return await self.upload(playwright)


async def publish_image_post(
    account_id: int,
    title: str,
    content: str,
    image_paths: list[str],
    tags: list[str] = None,
    publish_date: datetime = None
) -> dict:
    """
    发布小红书图文笔记的便捷函数
    
    Args:
        account_id: 账号 ID
        title: 标题
        content: 正文内容
        image_paths: 图片路径列表
        tags: 话题标签列表
        publish_date: 定时发布时间
    
    Returns:
        dict: 发布结果
    """
    import sqlite3
    from backend.account_utils.config import DB_PATH
    
    # 从数据库获取账号的 Cookie 文件路径
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT filePath, type FROM user_info WHERE id = ?', (account_id,))
        result = cursor.fetchone()
    
    if not result:
        return {"success": False, "message": "账号不存在", "note_id": None}
    
    if result['type'] != 1:  # type=1 是小红书
        return {"success": False, "message": "该账号不是小红书账号", "note_id": None}
    
    cookie_file = COOKIES_DIR / result['filePath']
    if not cookie_file.exists():
        return {"success": False, "message": "Cookie 文件不存在", "note_id": None}
    
    # 验证图片文件是否存在
    valid_images = []
    for img_path in image_paths:
        if Path(img_path).exists():
            valid_images.append(img_path)
        else:
            logger.warning(f"图片文件不存在: {img_path}")
    
    if not valid_images:
        return {"success": False, "message": "没有有效的图片文件", "note_id": None}
    
    # 创建发布任务
    post = XiaoHongShuImagePost(
        title=title,
        content=content,
        image_paths=valid_images,
        tags=tags or [],
        account_file=str(cookie_file),
        publish_date=publish_date
    )
    
    return await post.main()
