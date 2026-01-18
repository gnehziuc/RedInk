"""MCP 客户端 - 连接外部 MCP Server

支持两种传输方式：
- stdio: 通过 subprocess 启动本地 MCP 服务器
- streamableHttp: 通过 HTTP 连接远程 MCP 服务器
"""
import asyncio
import json
import logging
import re
import subprocess
import sys
import os
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

logger = logging.getLogger(__name__)


def _sanitize_for_json(obj: Any) -> Any:
    """递归清理对象，确保可以被 JSON 序列化"""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    elif isinstance(obj, re.Pattern):
        # 将正则表达式 Pattern 转换为字符串
        return obj.pattern
    elif isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(item) for item in obj]
    else:
        # 其他类型转换为字符串
        return str(obj)


@dataclass
class MCPTool:
    """MCP 工具定义"""
    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)
    server_name: str = ""
    enabled: bool = True  # 工具级别的启用状态


class BaseMCPClient(ABC):
    """MCP 客户端基类"""

    def __init__(self, server_name: str, server_config: Dict[str, Any]):
        self.server_name = server_name
        self.server_config = server_config
        self.connected = False
        self.tools: List[MCPTool] = []
        self._request_id = 0
        self._lock = asyncio.Lock()

    def _get_next_id(self) -> Union[int, str]:
        """获取下一个请求 ID"""
        self._request_id += 1
        return self._request_id

    @abstractmethod
    async def connect(self) -> bool:
        """连接到 MCP 服务器"""
        pass

    @abstractmethod
    async def disconnect(self):
        """断开连接"""
        pass

    @abstractmethod
    async def _send_request(self, method: str, params: Dict[str, Any]) -> Optional[Any]:
        """发送 JSON-RPC 请求"""
        pass

    async def _fetch_tools(self, tools_config: Optional[List[Dict[str, Any]]] = None):
        """获取服务器提供的工具列表

        Args:
            tools_config: 可选的工具配置列表，用于同步 enabled 状态
        """
        try:
            result = await self._send_request('tools/list', {})

            if result and 'tools' in result:
                # 构建工具配置映射（如果提供了配置）
                enabled_map = {}
                if tools_config:
                    for tc in tools_config:
                        if isinstance(tc, dict) and 'name' in tc:
                            enabled_map[tc['name']] = tc.get('enabled', True)

                self.tools = []
                for tool_data in result['tools']:
                    tool_name = tool_data.get('name', '')
                    # 从配置中获取 enabled 状态，默认为 True
                    enabled = enabled_map.get(tool_name, True)
                    tool = MCPTool(
                        name=tool_name,
                        description=tool_data.get('description', ''),
                        input_schema=tool_data.get('inputSchema', {}),
                        server_name=self.server_name,
                        enabled=enabled
                    )
                    self.tools.append(tool)

                logger.info(f"[{self.server_name}] 发现 {len(self.tools)} 个工具")
            else:
                logger.warning(f"[{self.server_name}] 未获取到工具列表")

        except Exception as e:
            logger.error(f"[{self.server_name}] 获取工具列表失败: {e}")

    async def list_tools(self) -> List[MCPTool]:
        """获取可用工具列表"""
        return self.tools

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """调用 MCP 工具"""
        if not self.connected:
            return {"error": "未连接到 MCP Server", "success": False}

        try:
            logger.info(f"[{self.server_name}] 调用工具: {tool_name}")

            result = await self._send_request('tools/call', {
                'name': tool_name,
                'arguments': arguments
            })

            if result is None:
                return {"error": "工具调用失败", "success": False}

            logger.debug(f"[{self.server_name}] 工具调用原始结果: {result}")

            # 解析工具结果
            content = result.get('content', [])
            is_error = result.get('isError', False)

            # 提取文本内容
            text_parts = []
            for item in content:
                if item.get('type') == 'text':
                    text_parts.append(item.get('text', ''))
                elif item.get('type') == 'resource':
                    # 处理资源类型的返回
                    resource = item.get('resource', {})
                    if resource.get('text'):
                        text_parts.append(resource.get('text'))
                    elif resource.get('blob'):
                        text_parts.append(f"[Binary data: {len(resource.get('blob', ''))} bytes]")

            output = '\n'.join(text_parts) if text_parts else ''

            # 如果没有提取到文本内容，尝试使用整个 result
            if not output and result:
                # 尝试从 result 中获取其他可能的数据
                if isinstance(result, dict):
                    # 可能是直接返回的数据
                    output = str(result)
                else:
                    output = str(result)

            logger.info(f"[{self.server_name}] 工具调用结果: success={not is_error}, output_length={len(output)}")

            if is_error:
                return {
                    "success": False,
                    "error": output or "工具执行出错",
                    "result": output,
                    "raw": result
                }

            return {
                "success": True,
                "result": output or "Success",
                "raw": result
            }

        except Exception as e:
            logger.error(f"[{self.server_name}] 工具调用异常: {e}")
            return {"error": str(e), "success": False}

    @abstractmethod
    def is_healthy(self) -> bool:
        """检查连接是否健康"""
        pass


class StdioMCPClient(BaseMCPClient):
    """stdio 传输的 MCP 客户端 - 通过 subprocess 管理本地 MCP 服务器"""

    def __init__(self, server_name: str, server_config: Dict[str, Any]):
        super().__init__(server_name, server_config)
        self.process: Optional[subprocess.Popen] = None

    async def connect(self) -> bool:
        """启动 MCP 服务器进程并初始化连接"""
        try:
            command = self.server_config.get('command')
            args = self.server_config.get('args', [])
            env_vars = self.server_config.get('env', {})

            if not command:
                logger.error(f"[{self.server_name}] 缺少 command 配置")
                return False

            # 构建完整命令
            cmd = [command] + args

            # 合并环境变量
            env = os.environ.copy()
            env.update(env_vars)

            # Windows 特殊处理
            if sys.platform == 'win32':
                if command in ['npx', 'uvx']:
                    cmd = ['cmd', '/c'] + cmd
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
            else:
                startupinfo = None

            logger.info(f"[{self.server_name}] 启动 MCP 服务器: {' '.join(cmd)}")

            # 启动子进程
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                startupinfo=startupinfo,
                bufsize=0
            )

            # 等待进程启动
            await asyncio.sleep(0.5)

            # 检查进程是否正常运行
            if self.process.poll() is not None:
                stderr = self.process.stderr.read().decode() if self.process.stderr else ""
                logger.error(f"[{self.server_name}] 进程启动失败: {stderr}")
                return False

            # 发送初始化请求
            init_result = await self._send_request('initialize', {
                'protocolVersion': '2024-11-05',
                'capabilities': {},
                'clientInfo': {
                    'name': 'RedInk',
                    'version': '1.0.0'
                }
            })

            if init_result is None:
                logger.error(f"[{self.server_name}] 初始化请求失败")
                await self.disconnect()
                return False

            # 发送 initialized 通知
            await self._send_notification('notifications/initialized', {})

            self.connected = True
            logger.info(f"[{self.server_name}] MCP 服务器连接成功")

            # 获取工具列表
            await self._fetch_tools()

            return True

        except Exception as e:
            logger.error(f"[{self.server_name}] MCP 连接失败: {e}")
            await self.disconnect()
            return False

    async def disconnect(self):
        """断开连接并关闭进程"""
        self.connected = False
        self.tools = []

        if self.process:
            try:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            except Exception as e:
                logger.warning(f"[{self.server_name}] 关闭进程时出错: {e}")
            finally:
                self.process = None

        logger.info(f"[{self.server_name}] MCP 连接已断开")

    async def _send_request(self, method: str, params: Dict[str, Any]) -> Optional[Any]:
        """发送 JSON-RPC 请求并等待响应"""
        if not self.process or self.process.poll() is not None:
            logger.error(f"[{self.server_name}] 进程未运行")
            return None

        async with self._lock:
            try:
                request_id = self._get_next_id()
                request = {
                    'jsonrpc': '2.0',
                    'id': request_id,
                    'method': method,
                    'params': params
                }

                request_line = json.dumps(request) + '\n'
                self.process.stdin.write(request_line.encode())
                self.process.stdin.flush()

                # 读取响应（带超时）
                response_line = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, self.process.stdout.readline
                    ),
                    timeout=30.0
                )

                if not response_line:
                    logger.error(f"[{self.server_name}] 未收到响应")
                    return None

                response = json.loads(response_line.decode())

                if 'error' in response:
                    error = response['error']
                    logger.error(f"[{self.server_name}] RPC 错误: {error}")
                    return None

                return response.get('result')

            except asyncio.TimeoutError:
                logger.error(f"[{self.server_name}] 请求超时: {method}")
                return None
            except Exception as e:
                logger.error(f"[{self.server_name}] 发送请求失败: {e}")
                return None

    async def _send_notification(self, method: str, params: Dict[str, Any]):
        """发送 JSON-RPC 通知（无响应）"""
        if not self.process or self.process.poll() is not None:
            return

        try:
            notification = {
                'jsonrpc': '2.0',
                'method': method,
                'params': params
            }

            notification_line = json.dumps(notification) + '\n'
            self.process.stdin.write(notification_line.encode())
            self.process.stdin.flush()

        except Exception as e:
            logger.warning(f"[{self.server_name}] 发送通知失败: {e}")

    def is_healthy(self) -> bool:
        """检查进程是否健康"""
        return self.process is not None and self.process.poll() is None and self.connected


class StreamableHttpMCPClient(BaseMCPClient):
    """Streamable HTTP 传输的 MCP 客户端 - 通过 HTTP 连接远程 MCP 服务器"""

    def __init__(self, server_name: str, server_config: Dict[str, Any]):
        super().__init__(server_name, server_config)
        # URL 直接使用，不追加路径
        self.endpoint_url = server_config.get('url', '').rstrip('/')
        self.custom_headers = server_config.get('headers', {})
        self.session_id: Optional[str] = None
        self._http_client = None

    async def connect(self) -> bool:
        """连接到远程 MCP 服务器"""
        try:
            import httpx

            if not self.endpoint_url:
                logger.error(f"[{self.server_name}] 缺少 url 配置")
                return False

            # 创建 HTTP 客户端，不设置 base_url，直接使用完整 URL
            self._http_client = httpx.AsyncClient(
                timeout=60.0,
                follow_redirects=True
            )

            logger.info(f"[{self.server_name}] 连接到 MCP 服务器: {self.endpoint_url}")

            # 发送初始化请求
            init_result = await self._send_request('initialize', {
                'protocolVersion': '2024-11-05',
                'capabilities': {},
                'clientInfo': {
                    'name': 'RedInk',
                    'version': '1.0.0'
                }
            })

            if init_result is None:
                logger.error(f"[{self.server_name}] 初始化请求失败")
                await self.disconnect()
                return False

            # 发送 initialized 通知
            await self._send_notification('notifications/initialized', {})

            self.connected = True
            logger.info(f"[{self.server_name}] MCP 服务器连接成功")

            # 获取工具列表
            await self._fetch_tools()

            return True

        except ImportError:
            logger.error(f"[{self.server_name}] 需要安装 httpx 库: pip install httpx")
            return False
        except Exception as e:
            logger.error(f"[{self.server_name}] MCP 连接失败: {e}")
            await self.disconnect()
            return False

    async def disconnect(self):
        """断开连接"""
        self.connected = False
        self.tools = []
        self.session_id = None

        if self._http_client:
            try:
                await self._http_client.aclose()
            except Exception as e:
                logger.warning(f"[{self.server_name}] 关闭 HTTP 客户端时出错: {e}")
            finally:
                self._http_client = None

        logger.info(f"[{self.server_name}] MCP 连接已断开")

    async def _send_request(self, method: str, params: Dict[str, Any]) -> Optional[Any]:
        """发送 JSON-RPC 请求"""
        if not self._http_client:
            logger.error(f"[{self.server_name}] HTTP 客户端未初始化")
            return None

        async with self._lock:
            try:
                request_id = str(uuid.uuid4())
                request = {
                    'jsonrpc': '2.0',
                    'id': request_id,
                    'method': method,
                    'params': params
                }

                # 构建请求头 - MCP Streamable HTTP 协议要求
                headers = {
                    'Content-Type': 'application/json',
                    'Accept': 'text/event-stream, application/json',
                    **self.custom_headers
                }
                if self.session_id:
                    headers['Mcp-Session-Id'] = self.session_id

                logger.debug(f"[{self.server_name}] 发送请求: {method} 到 {self.endpoint_url}")

                # 发送 POST 请求到完整 URL
                response = await self._http_client.post(
                    self.endpoint_url,
                    json=request,
                    headers=headers
                )

                logger.debug(f"[{self.server_name}] 响应状态: {response.status_code}, Content-Type: {response.headers.get('content-type')}")

                # 检查是否返回了 session ID
                if 'Mcp-Session-Id' in response.headers:
                    self.session_id = response.headers['Mcp-Session-Id']

                # 根据 Content-Type 处理响应
                content_type = response.headers.get('content-type', '')

                if response.status_code >= 400:
                    error_text = response.text
                    logger.error(f"[{self.server_name}] HTTP 错误 {response.status_code}: {error_text[:500]}")
                    return None

                if 'text/event-stream' in content_type:
                    # SSE 流式响应
                    return await self._parse_sse_response(response.text, request_id)
                elif 'application/json' in content_type:
                    # 直接 JSON 响应
                    result = response.json()
                    if 'error' in result:
                        error = result['error']
                        logger.error(f"[{self.server_name}] RPC 错误: {error}")
                        return None
                    return result.get('result')
                else:
                    # 尝试作为 JSON 解析
                    try:
                        result = response.json()
                        if 'error' in result:
                            logger.error(f"[{self.server_name}] RPC 错误: {result['error']}")
                            return None
                        return result.get('result')
                    except Exception:
                        logger.error(f"[{self.server_name}] 未知响应格式: {content_type}")
                        return None

            except Exception as e:
                logger.error(f"[{self.server_name}] 发送请求失败: {e}")
                import traceback
                logger.debug(traceback.format_exc())
                return None

    async def _parse_sse_response(self, sse_text: str, request_id: str) -> Optional[Any]:
        """解析 SSE 响应文本"""
        try:
            for line in sse_text.split('\n'):
                line = line.strip()
                if line.startswith('data:'):
                    data = line[5:].strip()
                    if data:
                        try:
                            event = json.loads(data)
                            # 检查是否是我们期望的响应
                            if event.get('id') == request_id or 'result' in event:
                                if 'error' in event:
                                    logger.error(f"[{self.server_name}] RPC 错误: {event['error']}")
                                    return None
                                return event.get('result')
                        except json.JSONDecodeError:
                            continue
            return None
        except Exception as e:
            logger.error(f"[{self.server_name}] 解析 SSE 响应失败: {e}")
            return None

    async def _send_notification(self, method: str, params: Dict[str, Any]):
        """发送 JSON-RPC 通知"""
        if not self._http_client:
            return

        try:
            notification = {
                'jsonrpc': '2.0',
                'method': method,
                'params': params
            }

            headers = {
                'Content-Type': 'application/json',
                'Accept': 'text/event-stream, application/json',
                **self.custom_headers
            }
            if self.session_id:
                headers['Mcp-Session-Id'] = self.session_id

            await self._http_client.post(
                self.endpoint_url,
                json=notification,
                headers=headers
            )

        except Exception as e:
            logger.warning(f"[{self.server_name}] 发送通知失败: {e}")

    def is_healthy(self) -> bool:
        """检查连接是否健康"""
        return self._http_client is not None and self.connected


# 兼容旧代码的别名
MCPClient = StdioMCPClient


def create_mcp_client(server_name: str, server_config: Dict[str, Any]) -> BaseMCPClient:
    """根据配置创建对应类型的 MCP 客户端"""
    transport_type = server_config.get('type', 'stdio')

    if transport_type == 'streamableHttp':
        return StreamableHttpMCPClient(server_name, server_config)
    else:
        # 默认使用 stdio
        return StdioMCPClient(server_name, server_config)


class MCPClientManager:
    """MCP 客户端管理器 - 管理多个 MCP 服务器连接"""

    def __init__(self):
        self._clients: Dict[str, BaseMCPClient] = {}
        self._initialized = False
        self._config_path = Path(__file__).parent.parent.parent / 'mcp_config.yaml'

    def _load_config(self) -> Dict[str, Any]:
        """加载 MCP 配置"""
        import yaml

        if not self._config_path.exists():
            return {'enabled': False, 'servers': {}}

        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
                return config
        except Exception as e:
            logger.error(f"加载 MCP 配置失败: {e}")
            return {'enabled': False, 'servers': {}}

    def save_config(self, config: Dict[str, Any]):
        """保存 MCP 配置"""
        import yaml

        try:
            with open(self._config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
            logger.info("MCP 配置已保存")
        except Exception as e:
            logger.error(f"保存 MCP 配置失败: {e}")
            raise

    def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return self._load_config()

    async def initialize(self, force: bool = False):
        """初始化所有已启用的 MCP 服务器"""
        if self._initialized and not force:
            return

        # 先断开所有现有连接
        await self.shutdown()

        config = self._load_config()

        if not config.get('enabled', False):
            logger.info("MCP 工具集成已禁用")
            self._initialized = True
            return

        servers = config.get('servers', {})

        for server_name, server_config in servers.items():
            if not server_config.get('enabled', True):
                logger.info(f"[{server_name}] 服务器已禁用，跳过")
                continue

            # 根据类型创建对应的客户端
            client = create_mcp_client(server_name, server_config)
            success = await client.connect()

            if success:
                # 获取配置中保存的工具列表（包含 enabled 状态）
                tools_config = server_config.get('tools', [])
                # 重新获取工具并同步 enabled 状态
                await client._fetch_tools(tools_config)
                self._clients[server_name] = client
            else:
                logger.warning(f"[{server_name}] 连接失败，跳过")

        self._initialized = True
        logger.info(f"MCP 初始化完成，已连接 {len(self._clients)} 个服务器")

    async def shutdown(self):
        """关闭所有连接"""
        for client in self._clients.values():
            await client.disconnect()
        self._clients.clear()
        self._initialized = False

    async def test_server(self, server_name: str, server_config: Dict[str, Any]) -> Dict[str, Any]:
        """测试单个 MCP 服务器连接"""
        client = create_mcp_client(server_name, server_config)

        try:
            success = await client.connect()

            if success:
                tools = await client.list_tools()
                tool_list = [
                    {
                        'name': t.name,
                        'description': t.description,
                        'server': server_name,
                        'input_schema': _sanitize_for_json(t.input_schema),
                        'enabled': t.enabled  # 包含启用状态
                    }
                    for t in tools
                ]

                await client.disconnect()

                return {
                    'success': True,
                    'message': f'连接成功！发现 {len(tools)} 个工具',
                    'tools': tool_list
                }
            else:
                return {
                    'success': False,
                    'message': '连接失败，请检查配置'
                }

        except Exception as e:
            await client.disconnect()
            return {
                'success': False,
                'message': f'连接错误: {str(e)}'
            }

    def get_client(self, server_name: str) -> Optional[BaseMCPClient]:
        """获取指定服务器的客户端"""
        return self._clients.get(server_name)

    def get_all_clients(self) -> Dict[str, BaseMCPClient]:
        """获取所有客户端"""
        return self._clients

    def get_all_tools(self) -> List[MCPTool]:
        """获取所有服务器的工具列表"""
        tools = []
        for client in self._clients.values():
            tools.extend(client.tools)
        return tools

    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized

    def update_tool_enabled(self, server_name: str, tool_name: Optional[str], enabled: bool) -> Dict[str, Any]:
        """更新工具的启用状态

        Args:
            server_name: 服务器名称
            tool_name: 工具名称，为 None 时批量更新该服务器下所有工具
            enabled: 启用状态

        Returns:
            操作结果字典
        """
        config = self._load_config()
        servers = config.get('servers', {})

        if server_name not in servers:
            return {'success': False, 'error': f'服务器 "{server_name}" 不存在'}

        server_config = servers[server_name]
        tools = server_config.get('tools', [])

        if not tools:
            return {'success': False, 'error': f'服务器 "{server_name}" 没有工具列表'}

        updated_count = 0
        if tool_name:
            # 更新单个工具
            for tool in tools:
                if isinstance(tool, dict) and tool.get('name') == tool_name:
                    tool['enabled'] = enabled
                    updated_count = 1
                    break

            if updated_count == 0:
                return {'success': False, 'error': f'工具 "{tool_name}" 不存在'}
        else:
            # 批量更新所有工具
            for tool in tools:
                if isinstance(tool, dict):
                    tool['enabled'] = enabled
                    updated_count += 1

        # 保存配置
        server_config['tools'] = tools
        servers[server_name] = server_config
        config['servers'] = servers
        self.save_config(config)

        # 同步内存中客户端的工具状态
        client = self._clients.get(server_name)
        if client:
            if tool_name:
                for t in client.tools:
                    if t.name == tool_name:
                        t.enabled = enabled
                        break
            else:
                for t in client.tools:
                    t.enabled = enabled

        action = f'工具 "{tool_name}"' if tool_name else f'{updated_count} 个工具'
        status = '已启用' if enabled else '已禁用'
        return {'success': True, 'message': f'{action} {status}'}


# 全局单例
_manager: Optional[MCPClientManager] = None


def get_mcp_manager() -> MCPClientManager:
    """获取全局 MCP 客户端管理器"""
    global _manager
    if _manager is None:
        _manager = MCPClientManager()
    return _manager
