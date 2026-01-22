"""
账号工具模块配置

提供账号管理所需的配置常量和路径
"""
from pathlib import Path

# 基础目录 - RedInk 项目根目录
BASE_DIR = Path(__file__).parent.parent.parent.resolve()

# 数据库路径
DB_PATH = BASE_DIR / "db" / "accounts.db"

# Cookie 文件存储目录
COOKIES_DIR = BASE_DIR / "cookiesFile"

# 是否使用无头浏览器模式
LOCAL_CHROME_HEADLESS = False

# stealth.js 路径 (用于绕过检测)
STEALTH_JS_PATH = Path(__file__).parent / "stealth.min.js"
