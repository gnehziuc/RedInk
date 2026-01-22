"""
Cookie 验证模块

各平台 Cookie 有效性检查
"""
import asyncio
import logging
from pathlib import Path
from playwright.async_api import async_playwright

from .config import COOKIES_DIR, LOCAL_CHROME_HEADLESS, STEALTH_JS_PATH

logger = logging.getLogger(__name__)


async def set_init_script(context):
    """设置浏览器初始化脚本（反检测）"""
    if STEALTH_JS_PATH.exists():
        await context.add_init_script(path=STEALTH_JS_PATH)
    return context


async def cookie_auth_douyin(account_file):
    """验证抖音 Cookie 有效性"""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=LOCAL_CHROME_HEADLESS)
        context = await browser.new_context(storage_state=account_file)
        context = await set_init_script(context)
        page = await context.new_page()
        await page.goto("https://creator.douyin.com/creator-micro/content/upload")
        try:
            await page.wait_for_url("https://creator.douyin.com/creator-micro/content/upload", timeout=5000)
            try:
                await page.get_by_text("扫码登录").wait_for(timeout=5000)
                logger.warning("[+] 抖音 cookie 失效，需要扫码登录")
                return False
            except:
                logger.info("[+] 抖音 cookie 有效")
                return True
        except:
            logger.warning("[+] 抖音等待5秒 cookie 失效")
            await context.close()
            await browser.close()
            return False


async def cookie_auth_tencent(account_file):
    """验证视频号 Cookie 有效性"""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=LOCAL_CHROME_HEADLESS)
        context = await browser.new_context(storage_state=account_file)
        context = await set_init_script(context)
        page = await context.new_page()
        await page.goto("https://channels.weixin.qq.com/platform/post/create")
        try:
            await page.wait_for_selector('div.title-name:has-text("微信小店")', timeout=5000)
            logger.warning("[+] 视频号 cookie 失效")
            return False
        except:
            logger.info("[+] 视频号 cookie 有效")
            return True


async def cookie_auth_ks(account_file):
    """验证快手 Cookie 有效性"""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=LOCAL_CHROME_HEADLESS)
        context = await browser.new_context(storage_state=account_file)
        context = await set_init_script(context)
        page = await context.new_page()
        await page.goto("https://cp.kuaishou.com/article/publish/video")
        try:
            await page.wait_for_selector("div.names div.container div.name:text('机构服务')", timeout=5000)
            logger.warning("[+] 快手 cookie 失效")
            return False
        except:
            logger.info("[+] 快手 cookie 有效")
            return True


async def cookie_auth_xhs(account_file):
    """验证小红书 Cookie 有效性"""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=LOCAL_CHROME_HEADLESS)
        context = await browser.new_context(storage_state=account_file)
        context = await set_init_script(context)
        page = await context.new_page()
        await page.goto("https://creator.xiaohongshu.com/creator-micro/content/upload")
        try:
            await page.wait_for_url("https://creator.xiaohongshu.com/creator-micro/content/upload", timeout=5000)
        except:
            logger.warning("[+] 小红书等待5秒 cookie 失效")
            await context.close()
            await browser.close()
            return False
        if await page.get_by_text('手机号登录').count() or await page.get_by_text('扫码登录').count():
            logger.warning("[+] 小红书 cookie 失效")
            return False
        else:
            logger.info("[+] 小红书 cookie 有效")
            return True


async def check_cookie(type: int, file_path: str) -> bool:
    """
    检查账号 Cookie 有效性
    
    Args:
        type: 平台类型 (1=小红书, 2=视频号, 3=抖音, 4=快手)
        file_path: Cookie 文件名
    
    Returns:
        bool: Cookie 是否有效
    """
    cookie_path = COOKIES_DIR / file_path
    if not cookie_path.exists():
        logger.error(f"Cookie 文件不存在: {cookie_path}")
        return False
    
    match type:
        case 1:  # 小红书
            return await cookie_auth_xhs(str(cookie_path))
        case 2:  # 视频号
            return await cookie_auth_tencent(str(cookie_path))
        case 3:  # 抖音
            return await cookie_auth_douyin(str(cookie_path))
        case 4:  # 快手
            return await cookie_auth_ks(str(cookie_path))
        case _:
            return False
