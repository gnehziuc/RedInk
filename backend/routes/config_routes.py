"""
配置管理相关 API 路由

包含功能：
- 获取当前配置
- 更新配置
- 测试服务商连接
"""

import logging
from pathlib import Path
import yaml
from flask import Blueprint, request, jsonify
from .utils import prepare_providers_for_response

logger = logging.getLogger(__name__)

# 配置文件路径
CONFIG_DIR = Path(__file__).parent.parent.parent
IMAGE_CONFIG_PATH = CONFIG_DIR / 'image_providers.yaml'
TEXT_CONFIG_PATH = CONFIG_DIR / 'text_providers.yaml'


def create_config_blueprint():
    """创建配置路由蓝图（工厂函数，支持多次调用）"""
    config_bp = Blueprint('config', __name__)

    # ==================== 配置读写 ====================

    @config_bp.route('/config', methods=['GET'])
    def get_config():
        """
        获取当前配置

        返回：
        - success: 是否成功
        - config: 配置对象
          - text_generation: 文本生成配置
          - image_generation: 图片生成配置
        """
        try:
            # 读取图片生成配置
            image_config = _read_config(IMAGE_CONFIG_PATH, {
                'active_provider': 'google_genai',
                'providers': {}
            })

            # 读取文本生成配置
            text_config = _read_config(TEXT_CONFIG_PATH, {
                'active_provider': 'google_gemini',
                'providers': {}
            })

            return jsonify({
                "success": True,
                "config": {
                    "text_generation": {
                        "active_provider": text_config.get('active_provider', ''),
                        "providers": prepare_providers_for_response(
                            text_config.get('providers', {})
                        )
                    },
                    "image_generation": {
                        "active_provider": image_config.get('active_provider', ''),
                        "providers": prepare_providers_for_response(
                            image_config.get('providers', {})
                        ),
                        "generate_images_enabled": image_config.get('generate_images_enabled', True)
                    }
                }
            })

        except Exception as e:
            return jsonify({
                "success": False,
                "error": f"获取配置失败: {str(e)}"
            }), 500

    @config_bp.route('/config', methods=['POST'])
    def update_config():
        """
        更新配置

        请求体：
        - image_generation: 图片生成配置（可选）
        - text_generation: 文本生成配置（可选）

        返回：
        - success: 是否成功
        - message: 结果消息
        """
        try:
            data = request.get_json()

            # 更新图片生成配置
            if 'image_generation' in data:
                _update_provider_config(
                    IMAGE_CONFIG_PATH,
                    data['image_generation']
                )

            # 更新文本生成配置
            if 'text_generation' in data:
                _update_provider_config(
                    TEXT_CONFIG_PATH,
                    data['text_generation']
                )

            # 清除配置缓存，确保下次使用时读取新配置
            _clear_config_cache()

            return jsonify({
                "success": True,
                "message": "配置已保存"
            })

        except Exception as e:
            return jsonify({
                "success": False,
                "error": f"更新配置失败: {str(e)}"
            }), 500

    # ==================== 连接测试 ====================

    @config_bp.route('/config/test', methods=['POST'])
    def test_connection():
        """
        测试服务商连接

        请求体：
        - type: 服务商类型（google_genai/google_gemini/openai_compatible/image_api）
        - provider_name: 服务商名称（用于从配置读取 API Key）
        - api_key: API Key（可选，若不提供则从配置读取）
        - base_url: Base URL（可选）
        - model: 模型名称（可选）

        返回：
        - success: 是否成功
        - message: 测试结果消息
        """
        try:
            data = request.get_json()
            provider_type = data.get('type')
            provider_name = data.get('provider_name')

            if not provider_type:
                return jsonify({"success": False, "error": "缺少 type 参数"}), 400

            # 构建配置
            config = {
                'api_key': data.get('api_key'),
                'base_url': data.get('base_url'),
                'model': data.get('model')
            }

            # 如果没有提供 api_key，从配置文件读取
            if not config['api_key'] and provider_name:
                config = _load_provider_config(provider_type, provider_name, config)

            if not config['api_key']:
                return jsonify({"success": False, "error": "API Key 未配置"}), 400

            # 根据类型执行测试
            result = _test_provider_connection(provider_type, config)
            return jsonify(result), 200 if result['success'] else 400

        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    return config_bp


# ==================== 辅助函数 ====================

def _read_config(path: Path, default: dict) -> dict:
    """读取配置文件"""
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or default
    return default


def _write_config(path: Path, config: dict):
    """写入配置文件"""
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)


def _update_provider_config(config_path: Path, new_data: dict):
    """
    更新服务商配置

    Args:
        config_path: 配置文件路径
        new_data: 新的配置数据
    """
    logger.info(f"更新配置文件: {config_path}")
    logger.debug(f"收到的配置数据: {new_data}")

    # 读取现有配置
    existing_config = _read_config(config_path, {'providers': {}})

    # 更新 active_provider
    if 'active_provider' in new_data:
        existing_config['active_provider'] = new_data['active_provider']

    # 更新 generate_images_enabled（仅适用于图片配置）
    if 'generate_images_enabled' in new_data:
        existing_config['generate_images_enabled'] = new_data['generate_images_enabled']

    # 更新 providers
    if 'providers' in new_data:
        existing_providers = existing_config.get('providers', {})
        new_providers = new_data['providers']

        for name, new_provider_config in new_providers.items():
            # 如果新配置的 api_key 是空的，保留原有的
            if new_provider_config.get('api_key') in [True, False, '', None]:
                if name in existing_providers and existing_providers[name].get('api_key'):
                    new_provider_config['api_key'] = existing_providers[name]['api_key']
                else:
                    new_provider_config.pop('api_key', None)

            # 移除不需要保存的字段
            new_provider_config.pop('api_key_env', None)
            new_provider_config.pop('api_key_masked', None)

        existing_config['providers'] = new_providers

    # 保存配置
    _write_config(config_path, existing_config)
    logger.info(f"配置已保存到: {config_path}")


def _clear_config_cache():
    """清除配置缓存并通知更新"""
    try:
        from backend.config import get_config_manager
        config_manager = get_config_manager()
        # 强制重新加载所有配置
        config_manager.reload_config()
        logger.info("配置缓存已清除，配置已重新加载")
    except Exception as e:
        logger.warning(f"重新加载配置失败: {e}")

    try:
        from backend.services.image import reset_image_service
        reset_image_service()
    except Exception as e:
        logger.warning(f"重置图片服务失败: {e}")


def _load_provider_config(provider_type: str, provider_name: str, config: dict) -> dict:
    """
    从配置文件加载服务商配置

    Args:
        provider_type: 服务商类型
        provider_name: 服务商名称
        config: 当前配置（会被合并）

    Returns:
        dict: 合并后的配置
    """
    # 确定配置文件路径
    if provider_type in ['openai_compatible', 'google_gemini']:
        config_path = TEXT_CONFIG_PATH
    else:
        config_path = IMAGE_CONFIG_PATH

    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            yaml_config = yaml.safe_load(f) or {}
            providers = yaml_config.get('providers', {})

            if provider_name in providers:
                saved = providers[provider_name]
                config['api_key'] = saved.get('api_key')

                if not config['base_url']:
                    config['base_url'] = saved.get('base_url')
                if not config['model']:
                    config['model'] = saved.get('model')

    return config


def _test_provider_connection(provider_type: str, config: dict) -> dict:
    """
    测试服务商连接

    Args:
        provider_type: 服务商类型
        config: 服务商配置

    Returns:
        dict: 测试结果
    """
    test_prompt = "请回复'你好，红墨'"

    if provider_type == 'google_genai':
        return _test_google_genai(config)

    elif provider_type == 'google_gemini':
        return _test_google_gemini(config, test_prompt)

    elif provider_type == 'openai_compatible':
        return _test_openai_compatible(config, test_prompt)

    elif provider_type == 'image_api':
        return _test_image_api(config)

    else:
        raise ValueError(f"不支持的类型: {provider_type}")


def _test_google_genai(config: dict) -> dict:
    """测试 Google GenAI 图片生成服务"""
    from google import genai

    if config.get('base_url'):
        client = genai.Client(
            api_key=config['api_key'],
            http_options={
                'base_url': config['base_url'],
                'api_version': 'v1beta'
            },
            vertexai=False
        )
        # 测试列出模型
        try:
            list(client.models.list())
            return {
                "success": True,
                "message": "连接成功！仅代表连接稳定，不确定是否可以稳定支持图片生成"
            }
        except Exception as e:
            raise Exception(f"连接测试失败: {str(e)}")
    else:
        return {
            "success": True,
            "message": "Vertex AI 无法通过 API Key 测试连接（需要 OAuth2 认证）。请在实际生成图片时验证配置是否正确。"
        }


def _test_google_gemini(config: dict, test_prompt: str) -> dict:
    """测试 Google Gemini 文本生成服务"""
    from google import genai

    if config.get('base_url'):
        client = genai.Client(
            api_key=config['api_key'],
            http_options={
                'base_url': config['base_url'],
                'api_version': 'v1beta'
            },
            vertexai=False
        )
    else:
        client = genai.Client(
            api_key=config['api_key'],
            vertexai=True
        )

    model = config.get('model') or 'gemini-2.0-flash-exp'
    response = client.models.generate_content(
        model=model,
        contents=test_prompt
    )
    result_text = response.text if hasattr(response, 'text') else str(response)

    return _check_response(result_text)


def _test_openai_compatible(config: dict, test_prompt: str) -> dict:
    """测试 OpenAI 兼容接口"""
    import requests

    base_url = config['base_url'].rstrip('/').rstrip('/v1') if config.get('base_url') else 'https://api.openai.com'
    url = f"{base_url}/v1/chat/completions"

    payload = {
        "model": config.get('model') or 'gpt-3.5-turbo',
        "messages": [{"role": "user", "content": test_prompt}],
        "max_tokens": 50
    }

    response = requests.post(
        url,
        headers={
            'Authorization': f"Bearer {config['api_key']}",
            'Content-Type': 'application/json'
        },
        json=payload,
        timeout=30
    )

    if response.status_code != 200:
        raise Exception(f"HTTP {response.status_code}: {response.text[:200]}")

    result = response.json()
    result_text = result['choices'][0]['message']['content']

    return _check_response(result_text)


def _test_image_api(config: dict) -> dict:
    """测试图片 API 连接"""
    import requests

    base_url = config['base_url'].rstrip('/').rstrip('/v1') if config.get('base_url') else 'https://api.openai.com'
    url = f"{base_url}/v1/models"

    response = requests.get(
        url,
        headers={'Authorization': f"Bearer {config['api_key']}"},
        timeout=30
    )

    if response.status_code == 200:
        return {
            "success": True,
            "message": "连接成功！仅代表连接稳定，不确定是否可以稳定支持图片生成"
        }
    else:
        raise Exception(f"HTTP {response.status_code}: {response.text[:200]}")


def _check_response(result_text: str) -> dict:
    """检查响应是否符合预期"""
    if "你好" in result_text and "红墨" in result_text:
        return {
            "success": True,
            "message": f"连接成功！响应: {result_text[:100]}"
        }
    else:
        return {
            "success": True,
            "message": f"连接成功，但响应内容不符合预期: {result_text[:100]}"
        }


# ==================== MCP 配置路由 ====================

def create_mcp_config_blueprint():
    """创建 MCP 配置路由蓝图"""
    import asyncio
    from backend.mcp.client import get_mcp_manager, _sanitize_for_json

    mcp_bp = Blueprint('mcp_config', __name__)

    @mcp_bp.route('/config/mcp', methods=['GET'])
    def get_mcp_config():
        """
        获取 MCP 配置

        返回：
        - success: 是否成功
        - config: MCP 配置对象
          - enabled: 是否启用
          - servers: 服务器配置
        """
        try:
            manager = get_mcp_manager()
            config = manager.get_config()

            # 脱敏处理：隐藏环境变量中的敏感信息
            safe_config = {
                'enabled': config.get('enabled', False),
                'servers': {}
            }

            for server_name, server_config in config.get('servers', {}).items():
                transport_type = server_config.get('type', 'stdio')

                safe_server = {
                    'type': transport_type,
                    'enabled': server_config.get('enabled', True),
                }

                if transport_type == 'streamableHttp':
                    # HTTP 类型配置
                    safe_server['url'] = server_config.get('url', '')
                    safe_server['headers'] = {}

                    # 对 headers 进行脱敏
                    for key, value in server_config.get('headers', {}).items():
                        if any(sensitive in key.upper() for sensitive in ['AUTHORIZATION', 'TOKEN', 'KEY', 'SECRET']):
                            safe_server['headers'][key] = '***' if value else ''
                            safe_server['headers'][f'_{key}_set'] = bool(value)
                        else:
                            safe_server['headers'][key] = value
                else:
                    # stdio 类型配置
                    safe_server['command'] = server_config.get('command', '')
                    safe_server['args'] = server_config.get('args', [])
                    safe_server['env'] = {}

                    # 对环境变量进行脱敏
                    for key, value in server_config.get('env', {}).items():
                        if any(sensitive in key.upper() for sensitive in ['KEY', 'TOKEN', 'SECRET', 'PASSWORD']):
                            safe_server['env'][key] = '***' if value else ''
                            safe_server['env'][f'_{key}_set'] = bool(value)
                        else:
                            safe_server['env'][key] = value

                # 包含已保存的工具列表
                if 'tools' in server_config:
                    safe_server['tools'] = server_config['tools']

                safe_config['servers'][server_name] = safe_server

            return jsonify({
                "success": True,
                "config": safe_config
            })

        except Exception as e:
            logger.error(f"获取 MCP 配置失败: {e}")
            return jsonify({
                "success": False,
                "error": f"获取配置失败: {str(e)}"
            }), 500

    @mcp_bp.route('/config/mcp', methods=['POST'])
    def update_mcp_config():
        """
        更新 MCP 配置

        请求体：
        - enabled: 是否启用 MCP
        - servers: 服务器配置字典

        返回：
        - success: 是否成功
        - message: 结果消息
        """
        try:
            data = request.get_json()
            manager = get_mcp_manager()

            # 读取现有配置
            existing_config = manager.get_config()

            # 更新 enabled 状态
            if 'enabled' in data:
                existing_config['enabled'] = data['enabled']

            # 更新服务器配置
            if 'servers' in data:
                existing_servers = existing_config.get('servers', {})
                new_servers = data['servers']

                for server_name, new_server_config in new_servers.items():
                    transport_type = new_server_config.get('type', 'stdio')

                    if server_name in existing_servers:
                        if transport_type == 'streamableHttp':
                            # 处理 headers：保留原有的敏感值
                            existing_headers = existing_servers[server_name].get('headers', {})
                            new_headers = new_server_config.get('headers', {})

                            for key, value in list(new_headers.items()):
                                # 如果值是 '***'，保留原有值
                                if value == '***' and key in existing_headers:
                                    new_headers[key] = existing_headers[key]

                            # 移除 _xxx_set 标记
                            new_server_config['headers'] = {k: v for k, v in new_headers.items()
                                                            if not (k.startswith('_') and k.endswith('_set'))}
                        else:
                            # 处理环境变量：保留原有的敏感值
                            existing_env = existing_servers[server_name].get('env', {})
                            new_env = new_server_config.get('env', {})

                            for key, value in list(new_env.items()):
                                # 如果值是 '***'，保留原有值
                                if value == '***' and key in existing_env:
                                    new_env[key] = existing_env[key]

                            # 移除 _xxx_set 标记
                            new_server_config['env'] = {k: v for k, v in new_env.items()
                                                         if not (k.startswith('_') and k.endswith('_set'))}

                existing_config['servers'] = new_servers

            # 保存配置
            manager.save_config(existing_config)

            # 重新初始化 MCP 连接
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(manager.initialize(force=True))
            finally:
                loop.close()

            return jsonify({
                "success": True,
                "message": "MCP 配置已保存并重新初始化"
            })

        except Exception as e:
            logger.error(f"更新 MCP 配置失败: {e}")
            return jsonify({
                "success": False,
                "error": f"更新配置失败: {str(e)}"
            }), 500

    @mcp_bp.route('/config/mcp/test', methods=['POST'])
    def test_mcp_connection():
        """
        测试 MCP 服务器连接

        请求体：
        - server_name: 服务器名称
        - server_config: 服务器配置（可选，若不提供则从现有配置读取）
          - command: 启动命令
          - args: 命令参数
          - env: 环境变量

        返回：
        - success: 是否成功
        - message: 测试结果消息
        - tools: 发现的工具列表（成功时）
        """
        try:
            data = request.get_json()
            server_name = data.get('server_name')

            if not server_name:
                return jsonify({
                    "success": False,
                    "error": "缺少 server_name 参数"
                }), 400

            manager = get_mcp_manager()

            # 获取服务器配置
            if 'server_config' in data:
                server_config = data['server_config']
                transport_type = server_config.get('type', 'stdio')

                # 处理脱敏值
                existing_config = manager.get_config()
                if server_name in existing_config.get('servers', {}):
                    existing_server = existing_config['servers'][server_name]

                    if transport_type == 'streamableHttp':
                        existing_headers = existing_server.get('headers', {})
                        new_headers = server_config.get('headers', {})

                        for key, value in list(new_headers.items()):
                            if value == '***' and key in existing_headers:
                                new_headers[key] = existing_headers[key]

                        server_config['headers'] = {k: v for k, v in new_headers.items()
                                                    if not (k.startswith('_') and k.endswith('_set'))}
                    else:
                        existing_env = existing_server.get('env', {})
                        new_env = server_config.get('env', {})

                        for key, value in list(new_env.items()):
                            if value == '***' and key in existing_env:
                                new_env[key] = existing_env[key]

                        server_config['env'] = {k: v for k, v in new_env.items()
                                                if not (k.startswith('_') and k.endswith('_set'))}
            else:
                config = manager.get_config()
                servers = config.get('servers', {})

                if server_name not in servers:
                    return jsonify({
                        "success": False,
                        "error": f"服务器 '{server_name}' 未配置"
                    }), 400

                server_config = servers[server_name]

            # 测试连接
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    manager.test_server(server_name, server_config)
                )

                # 如果测试成功，保存工具列表到配置
                if result.get('success') and result.get('tools'):
                    config = manager.get_config()
                    if server_name in config.get('servers', {}):
                        config['servers'][server_name]['tools'] = result['tools']
                        manager.save_config(config)
                        logger.info(f"[{server_name}] 工具列表已保存到配置")

            finally:
                loop.close()

            return jsonify(result), 200 if result['success'] else 400

        except Exception as e:
            logger.error(f"测试 MCP 连接失败: {e}")
            return jsonify({
                "success": False,
                "error": f"测试失败: {str(e)}"
            }), 500

    @mcp_bp.route('/config/mcp/tools', methods=['GET'])
    def get_mcp_tools():
        """
        获取所有已连接 MCP 服务器的工具列表

        返回：
        - success: 是否成功
        - tools: 工具列表
          - server: 所属服务器
          - name: 工具名称
          - description: 工具描述
        """
        try:
            manager = get_mcp_manager()
            tools = manager.get_all_tools()

            tool_list = [
                {
                    'server': t.server_name,
                    'name': t.name,
                    'description': t.description,
                    'input_schema': _sanitize_for_json(t.input_schema)
                }
                for t in tools
            ]

            return jsonify({
                "success": True,
                "tools": tool_list
            })

        except Exception as e:
            logger.error(f"获取 MCP 工具列表失败: {e}")
            return jsonify({
                "success": False,
                "error": f"获取工具列表失败: {str(e)}"
            }), 500

    @mcp_bp.route('/config/mcp/status', methods=['GET'])
    def get_mcp_status():
        """
        获取 MCP 系统状态

        返回：
        - success: 是否成功
        - status: 状态信息
          - initialized: 是否已初始化
          - servers: 各服务器状态
        """
        try:
            manager = get_mcp_manager()

            servers_status = {}
            for name, client in manager.get_all_clients().items():
                servers_status[name] = {
                    'connected': client.connected,
                    'healthy': client.is_healthy(),
                    'tool_count': len(client.tools)
                }

            return jsonify({
                "success": True,
                "status": {
                    "initialized": manager.is_initialized(),
                    "servers": servers_status
                }
            })

        except Exception as e:
            logger.error(f"获取 MCP 状态失败: {e}")
            return jsonify({
                "success": False,
                "error": f"获取状态失败: {str(e)}"
            }), 500

    return mcp_bp
