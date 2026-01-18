"""配置管理模块 - 支持热更新和线程安全"""
import logging
import os
import threading
import time
import yaml
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ConfigFileInfo:
    """配置文件信息"""
    path: Path
    last_modified: float = 0.0
    last_loaded: float = 0.0
    content: Dict[str, Any] = field(default_factory=dict)


class ConfigManager:
    """
    配置管理器 - 单例模式，支持热更新和线程安全

    特性：
    - 线程安全的配置读写
    - 文件变更检测和自动重新加载
    - 配置变更回调通知
    - 懒加载和缓存
    """

    _instance: Optional['ConfigManager'] = None
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

        self._initialized = True
        self._config_lock = threading.RLock()  # 可重入锁
        self._callbacks: Dict[str, List[Callable]] = {}
        self._watcher_thread: Optional[threading.Thread] = None
        self._watching = False
        self._watch_interval = 2.0  # 检测间隔（秒）

        # 项目根目录
        self._root_dir = Path(__file__).parent.parent

        # 配置文件映射
        self._config_files: Dict[str, ConfigFileInfo] = {
            'image_providers': ConfigFileInfo(path=self._root_dir / 'image_providers.yaml'),
            'text_providers': ConfigFileInfo(path=self._root_dir / 'text_providers.yaml'),
            'mcp_config': ConfigFileInfo(path=self._root_dir / 'mcp_config.yaml'),
        }

        logger.info("ConfigManager 初始化完成")

    def get_config(self, config_name: str, force_reload: bool = False) -> Dict[str, Any]:
        """
        获取配置（线程安全）

        Args:
            config_name: 配置名称（image_providers, text_providers, mcp_config）
            force_reload: 是否强制重新加载

        Returns:
            配置字典
        """
        with self._config_lock:
            if config_name not in self._config_files:
                raise ValueError(f"未知的配置类型: {config_name}")

            file_info = self._config_files[config_name]

            # 检查是否需要重新加载
            if force_reload or self._should_reload(file_info):
                self._load_config_file(config_name)

            return file_info.content.copy()  # 返回副本，防止外部修改

    def _should_reload(self, file_info: ConfigFileInfo) -> bool:
        """检查是否需要重新加载配置"""
        # 首次加载
        if file_info.last_loaded == 0:
            return True

        # 检查文件是否存在
        if not file_info.path.exists():
            return False

        # 检查文件修改时间
        try:
            current_mtime = file_info.path.stat().st_mtime
            return current_mtime > file_info.last_modified
        except OSError:
            return False

    def _load_config_file(self, config_name: str) -> None:
        """加载配置文件"""
        file_info = self._config_files[config_name]
        path = file_info.path

        logger.debug(f"加载配置文件: {path}")

        if not path.exists():
            logger.warning(f"配置文件不存在: {path}，使用默认配置")
            file_info.content = self._get_default_config(config_name)
            file_info.last_loaded = time.time()
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = yaml.safe_load(f) or {}

            file_info.content = content
            file_info.last_modified = path.stat().st_mtime
            file_info.last_loaded = time.time()

            logger.info(f"配置文件加载成功: {config_name}")

        except yaml.YAMLError as e:
            logger.error(f"配置文件 YAML 格式错误: {path}, {e}")
            raise ValueError(
                f"配置文件格式错误: {path.name}\n"
                f"YAML 解析错误: {e}\n"
                "解决方案：检查 YAML 缩进和格式"
            )
        except Exception as e:
            logger.error(f"加载配置文件失败: {path}, {e}")
            raise

    def _get_default_config(self, config_name: str) -> Dict[str, Any]:
        """获取默认配置"""
        defaults = {
            'image_providers': {
                'active_provider': 'google_genai',
                'generate_images_enabled': True,
                'providers': {}
            },
            'text_providers': {
                'active_provider': 'google_gemini',
                'providers': {}
            },
            'mcp_config': {
                'enabled': False,
                'servers': {}
            }
        }
        return defaults.get(config_name, {})

    def save_config(self, config_name: str, content: Dict[str, Any]) -> None:
        """
        保存配置（线程安全）

        Args:
            config_name: 配置名称
            content: 配置内容
        """
        with self._config_lock:
            if config_name not in self._config_files:
                raise ValueError(f"未知的配置类型: {config_name}")

            file_info = self._config_files[config_name]
            path = file_info.path

            try:
                with open(path, 'w', encoding='utf-8') as f:
                    yaml.dump(content, f, allow_unicode=True, default_flow_style=False)

                # 更新缓存
                file_info.content = content.copy()
                file_info.last_modified = path.stat().st_mtime
                file_info.last_loaded = time.time()

                logger.info(f"配置文件保存成功: {config_name}")

                # 触发回调
                self._notify_change(config_name, content)

            except Exception as e:
                logger.error(f"保存配置文件失败: {path}, {e}")
                raise

    def reload_config(self, config_name: str = None) -> None:
        """
        强制重新加载配置

        Args:
            config_name: 配置名称，None 表示重新加载所有配置
        """
        with self._config_lock:
            if config_name:
                if config_name in self._config_files:
                    self._load_config_file(config_name)
                    self._notify_change(config_name, self._config_files[config_name].content)
            else:
                for name in self._config_files:
                    self._load_config_file(name)
                    self._notify_change(name, self._config_files[name].content)

    def register_callback(self, config_name: str, callback: Callable[[str, Dict], None]) -> None:
        """
        注册配置变更回调

        Args:
            config_name: 配置名称，'*' 表示所有配置
            callback: 回调函数，签名为 (config_name, new_config) -> None
        """
        with self._config_lock:
            if config_name not in self._callbacks:
                self._callbacks[config_name] = []
            self._callbacks[config_name].append(callback)
            logger.debug(f"注册配置回调: {config_name}")

    def unregister_callback(self, config_name: str, callback: Callable) -> None:
        """取消注册配置变更回调"""
        with self._config_lock:
            if config_name in self._callbacks:
                self._callbacks[config_name] = [
                    cb for cb in self._callbacks[config_name] if cb != callback
                ]

    def _notify_change(self, config_name: str, new_config: Dict) -> None:
        """通知配置变更"""
        # 特定配置的回调
        if config_name in self._callbacks:
            for callback in self._callbacks[config_name]:
                try:
                    callback(config_name, new_config)
                except Exception as e:
                    logger.error(f"配置回调执行失败: {e}")

        # 通配符回调
        if '*' in self._callbacks:
            for callback in self._callbacks['*']:
                try:
                    callback(config_name, new_config)
                except Exception as e:
                    logger.error(f"配置回调执行失败: {e}")

    def start_watching(self, interval: float = 2.0) -> None:
        """
        启动配置文件监控

        Args:
            interval: 检测间隔（秒）
        """
        if self._watching:
            return

        self._watch_interval = interval
        self._watching = True
        self._watcher_thread = threading.Thread(
            target=self._watch_loop,
            daemon=True,
            name="ConfigWatcher"
        )
        self._watcher_thread.start()
        logger.info(f"配置文件监控已启动，检测间隔: {interval}秒")

    def stop_watching(self) -> None:
        """停止配置文件监控"""
        self._watching = False
        if self._watcher_thread:
            self._watcher_thread.join(timeout=5.0)
            self._watcher_thread = None
        logger.info("配置文件监控已停止")

    def _watch_loop(self) -> None:
        """监控循环"""
        while self._watching:
            try:
                with self._config_lock:
                    for config_name, file_info in self._config_files.items():
                        if self._should_reload(file_info):
                            logger.info(f"检测到配置文件变更: {config_name}")
                            old_content = file_info.content.copy()
                            self._load_config_file(config_name)

                            # 只有内容真正变化时才通知
                            if old_content != file_info.content:
                                self._notify_change(config_name, file_info.content)

            except Exception as e:
                logger.error(f"配置监控异常: {e}")

            time.sleep(self._watch_interval)

    def get_file_path(self, config_name: str) -> Path:
        """获取配置文件路径"""
        if config_name in self._config_files:
            return self._config_files[config_name].path
        raise ValueError(f"未知的配置类型: {config_name}")


# 全局配置管理器实例
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """获取全局配置管理器实例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


class Config:
    """
    配置类 - 提供兼容的静态方法接口

    使用 ConfigManager 作为后端，保持向后兼容
    """
    DEBUG = True
    HOST = '0.0.0.0'
    PORT = 12398
    CORS_ORIGINS = ['http://localhost:5173', 'http://localhost:3000']
    OUTPUT_DIR = 'output'

    # 兼容旧代码的缓存变量（实际不再使用）
    _image_providers_config = None
    _text_providers_config = None

    @classmethod
    def load_image_providers_config(cls):
        """加载图片服务商配置"""
        return get_config_manager().get_config('image_providers')

    @classmethod
    def load_text_providers_config(cls):
        """加载文本生成服务商配置"""
        return get_config_manager().get_config('text_providers')

    @classmethod
    def get_active_image_provider(cls):
        """获取激活的图片服务商"""
        config = cls.load_image_providers_config()
        active = config.get('active_provider', 'google_genai')
        logger.debug(f"当前激活的图片服务商: {active}")
        return active

    @classmethod
    def get_image_provider_config(cls, provider_name: str = None):
        """获取图片服务商配置"""
        config = cls.load_image_providers_config()

        if provider_name is None:
            provider_name = cls.get_active_image_provider()

        logger.info(f"获取图片服务商配置: {provider_name}")

        providers = config.get('providers', {})
        if not providers:
            raise ValueError(
                "未找到任何图片生成服务商配置。\n"
                "解决方案：\n"
                "1. 在系统设置页面添加图片生成服务商\n"
                "2. 或手动编辑 image_providers.yaml 文件\n"
                "3. 确保文件中有 providers 字段"
            )

        if provider_name not in providers:
            available = ', '.join(providers.keys()) if providers else '无'
            logger.error(f"图片服务商 [{provider_name}] 不存在，可用服务商: {available}")
            raise ValueError(
                f"未找到图片生成服务商配置: {provider_name}\n"
                f"可用的服务商: {available}\n"
                "解决方案：\n"
                "1. 在系统设置页面添加该服务商\n"
                "2. 或修改 active_provider 为已存在的服务商\n"
                "3. 检查 image_providers.yaml 文件"
            )

        provider_config = providers[provider_name].copy()

        # 验证必要字段
        if not provider_config.get('api_key'):
            logger.error(f"图片服务商 [{provider_name}] 未配置 API Key")
            raise ValueError(
                f"服务商 {provider_name} 未配置 API Key\n"
                "解决方案：\n"
                "1. 在系统设置页面编辑该服务商，填写 API Key\n"
                "2. 或手动在 image_providers.yaml 中添加 api_key 字段"
            )

        provider_type = provider_config.get('type', provider_name)
        if provider_type in ['openai', 'openai_compatible', 'image_api']:
            if not provider_config.get('base_url'):
                logger.error(f"服务商 [{provider_name}] 类型为 {provider_type}，但未配置 base_url")
                raise ValueError(
                    f"服务商 {provider_name} 未配置 Base URL\n"
                    f"服务商类型 {provider_type} 需要配置 base_url\n"
                    "解决方案：在系统设置页面编辑该服务商，填写 Base URL"
                )

        logger.info(f"图片服务商配置验证通过: {provider_name} (type={provider_type})")
        return provider_config

    @classmethod
    def get_active_text_provider(cls):
        """获取激活的文本服务商"""
        config = cls.load_text_providers_config()
        active = config.get('active_provider', 'google_gemini')
        logger.debug(f"当前激活的文本服务商: {active}")
        return active

    @classmethod
    def get_text_provider_config(cls, provider_name: str = None):
        """获取文本服务商配置"""
        config = cls.load_text_providers_config()

        if provider_name is None:
            provider_name = cls.get_active_text_provider()

        providers = config.get('providers', {})
        if provider_name not in providers:
            available = ', '.join(providers.keys()) if providers else '无'
            raise ValueError(f"未找到文本服务商配置: {provider_name}，可用: {available}")

        return providers[provider_name].copy()

    @classmethod
    def is_image_generation_enabled(cls):
        """检查图片生成是否启用"""
        config = cls.load_image_providers_config()
        return config.get('generate_images_enabled', True)

    @classmethod
    def reload_config(cls):
        """重新加载配置（清除缓存）"""
        logger.info("重新加载所有配置...")
        get_config_manager().reload_config()
        # 兼容旧代码
        cls._image_providers_config = None
        cls._text_providers_config = None


class DynamicConfig:
    """
    动态配置获取器 - 用于 agents 模块

    每次访问都获取最新配置，确保配置更新后能够立即生效
    """

    @staticmethod
    def get_text_provider_config() -> Dict[str, Any]:
        """获取当前激活的文本服务商配置"""
        return Config.get_text_provider_config()

    @staticmethod
    def get_image_provider_config() -> Dict[str, Any]:
        """获取当前激活的图片服务商配置"""
        return Config.get_image_provider_config()

    @staticmethod
    def is_image_generation_enabled() -> bool:
        """检查图片生成是否启用"""
        return Config.is_image_generation_enabled()

    @staticmethod
    def get_mcp_config() -> Dict[str, Any]:
        """获取 MCP 配置"""
        return get_config_manager().get_config('mcp_config')

    @staticmethod
    def register_config_change_callback(config_name: str, callback: Callable):
        """注册配置变更回调"""
        get_config_manager().register_callback(config_name, callback)

    @staticmethod
    def unregister_config_change_callback(config_name: str, callback: Callable):
        """取消注册配置变更回调"""
        get_config_manager().unregister_callback(config_name, callback)
