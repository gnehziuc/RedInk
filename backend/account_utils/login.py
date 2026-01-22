"""
账号登录模块

各平台扫码登录实现
"""
import asyncio
import sqlite3
import uuid
import logging
from pathlib import Path
from playwright.async_api import async_playwright

from .config import DB_PATH, COOKIES_DIR, LOCAL_CHROME_HEADLESS, STEALTH_JS_PATH
from .auth import check_cookie

logger = logging.getLogger(__name__)


async def set_init_script(context):
    """设置浏览器初始化脚本（反检测）"""
    if STEALTH_JS_PATH.exists():
        await context.add_init_script(path=STEALTH_JS_PATH)
    return context


def init_database():
    """初始化数据库表"""
    # 确保数据库目录存在
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    COOKIES_DIR.mkdir(parents=True, exist_ok=True)
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type INTEGER NOT NULL,
            filePath TEXT NOT NULL,
            userName TEXT NOT NULL,
            status INTEGER DEFAULT 0
        )
        ''')
        conn.commit()
        logger.info("✅ 账号数据库初始化完成")


async def douyin_cookie_gen(id, status_queue):
    """抖音扫码登录"""
    url_changed_event = asyncio.Event()
    page = None
    original_url = None
    
    async def on_url_change():
        if page and page.url != original_url:
            url_changed_event.set()
    
    async with async_playwright() as playwright:
        options = {'headless': LOCAL_CHROME_HEADLESS}
        browser = await playwright.chromium.launch(**options)
        context = await browser.new_context()
        context = await set_init_script(context)
        page = await context.new_page()
        await page.goto("https://creator.douyin.com/")
        original_url = page.url
        
        img_locator = page.get_by_role("img", name="二维码")
        src = await img_locator.get_attribute("src")
        logger.info(f"✅ 抖音二维码地址: {src[:50]}...")
        status_queue.put(src)
        
        page.on('framenavigated',
                lambda frame: asyncio.create_task(on_url_change()) if frame == page.main_frame else None)
        
        try:
            await asyncio.wait_for(url_changed_event.wait(), timeout=200)
            logger.info("登录页面跳转成功")
        except asyncio.TimeoutError:
            logger.warning("登录超时")
            await page.close()
            await context.close()
            await browser.close()
            status_queue.put("500")
            return None
        
        uuid_v1 = uuid.uuid1()
        COOKIES_DIR.mkdir(exist_ok=True)
        await context.storage_state(path=COOKIES_DIR / f"{uuid_v1}.json")
        
        result = await check_cookie(3, f"{uuid_v1}.json")
        if not result:
            status_queue.put("500")
            await page.close()
            await context.close()
            await browser.close()
            return None
        
        await page.close()
        await context.close()
        await browser.close()
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_info (type, filePath, userName, status)
                VALUES (?, ?, ?, ?)
            ''', (3, f"{uuid_v1}.json", id, 1))
            conn.commit()
            logger.info("✅ 抖音账号已记录")
        
        status_queue.put("200")


async def get_tencent_cookie(id, status_queue):
    """视频号扫码登录"""
    url_changed_event = asyncio.Event()
    page = None
    original_url = None
    
    async def on_url_change():
        if page and page.url != original_url:
            url_changed_event.set()
    
    async with async_playwright() as playwright:
        options = {
            'args': ['--lang en-GB'],
            'headless': LOCAL_CHROME_HEADLESS
        }
        browser = await playwright.chromium.launch(**options)
        context = await browser.new_context()
        context = await set_init_script(context)
        page = await context.new_page()
        await page.goto("https://channels.weixin.qq.com")
        original_url = page.url
        
        page.on('framenavigated',
                lambda frame: asyncio.create_task(on_url_change()) if frame == page.main_frame else None)
        
        iframe_locator = page.frame_locator("iframe").first
        img_locator = iframe_locator.get_by_role("img").first
        src = await img_locator.get_attribute("src")
        logger.info(f"✅ 视频号二维码地址: {src[:50]}...")
        status_queue.put(src)
        
        try:
            await asyncio.wait_for(url_changed_event.wait(), timeout=200)
            logger.info("登录页面跳转成功")
        except asyncio.TimeoutError:
            status_queue.put("500")
            logger.warning("登录超时")
            await page.close()
            await context.close()
            await browser.close()
            return None
        
        uuid_v1 = uuid.uuid1()
        COOKIES_DIR.mkdir(exist_ok=True)
        await context.storage_state(path=COOKIES_DIR / f"{uuid_v1}.json")
        
        result = await check_cookie(2, f"{uuid_v1}.json")
        if not result:
            status_queue.put("500")
            await page.close()
            await context.close()
            await browser.close()
            return None
        
        await page.close()
        await context.close()
        await browser.close()
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_info (type, filePath, userName, status)
                VALUES (?, ?, ?, ?)
            ''', (2, f"{uuid_v1}.json", id, 1))
            conn.commit()
            logger.info("✅ 视频号账号已记录")
        
        status_queue.put("200")


async def get_ks_cookie(id, status_queue):
    """快手扫码登录"""
    url_changed_event = asyncio.Event()
    page = None
    original_url = None
    
    async def on_url_change():
        if page and page.url != original_url:
            url_changed_event.set()
    
    async with async_playwright() as playwright:
        options = {
            'args': ['--lang en-GB'],
            'headless': LOCAL_CHROME_HEADLESS
        }
        browser = await playwright.chromium.launch(**options)
        context = await browser.new_context()
        context = await set_init_script(context)
        page = await context.new_page()
        await page.goto("https://cp.kuaishou.com")
        
        await page.get_by_role("link", name="立即登录").click()
        await page.get_by_text("扫码登录").click()
        img_locator = page.get_by_role("img", name="qrcode")
        src = await img_locator.get_attribute("src")
        original_url = page.url
        logger.info(f"✅ 快手二维码地址: {src[:50]}...")
        status_queue.put(src)
        
        page.on('framenavigated',
                lambda frame: asyncio.create_task(on_url_change()) if frame == page.main_frame else None)
        
        try:
            await asyncio.wait_for(url_changed_event.wait(), timeout=200)
            logger.info("登录页面跳转成功")
        except asyncio.TimeoutError:
            status_queue.put("500")
            logger.warning("登录超时")
            await page.close()
            await context.close()
            await browser.close()
            return None
        
        uuid_v1 = uuid.uuid1()
        COOKIES_DIR.mkdir(exist_ok=True)
        await context.storage_state(path=COOKIES_DIR / f"{uuid_v1}.json")
        
        result = await check_cookie(4, f"{uuid_v1}.json")
        if not result:
            status_queue.put("500")
            await page.close()
            await context.close()
            await browser.close()
            return None
        
        await page.close()
        await context.close()
        await browser.close()
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_info (type, filePath, userName, status)
                VALUES (?, ?, ?, ?)
            ''', (4, f"{uuid_v1}.json", id, 1))
            conn.commit()
            logger.info("✅ 快手账号已记录")
        
        status_queue.put("200")


async def xiaohongshu_cookie_gen(id, status_queue):
    """小红书扫码登录"""
    url_changed_event = asyncio.Event()
    page = None
    original_url = None
    
    async def on_url_change():
        if page and page.url != original_url:
            url_changed_event.set()
    
    async with async_playwright() as playwright:
        options = {
            'args': ['--lang en-GB'],
            'headless': LOCAL_CHROME_HEADLESS
        }
        browser = await playwright.chromium.launch(**options)
        context = await browser.new_context()
        context = await set_init_script(context)
        page = await context.new_page()
        await page.goto("https://creator.xiaohongshu.com/")
        await page.locator('img.css-wemwzq').click()
        
        img_locator = page.get_by_role("img").nth(2)
        src = await img_locator.get_attribute("src")
        original_url = page.url
        logger.info(f"✅ 小红书二维码地址: {src[:50]}...")
        status_queue.put(src)
        
        page.on('framenavigated',
                lambda frame: asyncio.create_task(on_url_change()) if frame == page.main_frame else None)
        
        try:
            await asyncio.wait_for(url_changed_event.wait(), timeout=200)
            logger.info("登录页面跳转成功")
        except asyncio.TimeoutError:
            status_queue.put("500")
            logger.warning("登录超时")
            await page.close()
            await context.close()
            await browser.close()
            return None
        
        uuid_v1 = uuid.uuid1()
        COOKIES_DIR.mkdir(exist_ok=True)
        await context.storage_state(path=COOKIES_DIR / f"{uuid_v1}.json")
        
        result = await check_cookie(1, f"{uuid_v1}.json")
        if not result:
            status_queue.put("500")
            await page.close()
            await context.close()
            await browser.close()
            return None
        
        await page.close()
        await context.close()
        await browser.close()
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_info (type, filePath, userName, status)
                VALUES (?, ?, ?, ?)
            ''', (1, f"{uuid_v1}.json", id, 1))
            conn.commit()
            logger.info("✅ 小红书账号已记录")
        
        status_queue.put("200")
