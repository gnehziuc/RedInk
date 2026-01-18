"""LangChain 工具包装器 - 将 MCP 工具包装为 LangChain Tool"""
import asyncio
import json
import logging
from typing import Any, Dict, Optional, Type

from langchain_core.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun, AsyncCallbackManagerForToolRun
from pydantic import BaseModel, Field, create_model

from backend.mcp.client import MCPClient, MCPTool, get_mcp_manager

logger = logging.getLogger(__name__)


def _json_schema_to_pydantic_field(name: str, schema: Dict[str, Any], required: bool = False) -> tuple:
    """将 JSON Schema 字段转换为 Pydantic Field"""
    field_type = str  # 默认类型

    json_type = schema.get('type', 'string')
    description = schema.get('description', '')

    if json_type == 'string':
        field_type = str
    elif json_type == 'integer':
        field_type = int
    elif json_type == 'number':
        field_type = float
    elif json_type == 'boolean':
        field_type = bool
    elif json_type == 'array':
        field_type = list
    elif json_type == 'object':
        field_type = dict

    # 可选字段使用 Optional
    if not required:
        field_type = Optional[field_type]

    default = ... if required else None

    return (field_type, Field(default=default, description=description))


def _build_enhanced_description(mcp_tool: MCPTool) -> str:
    """构建增强的工具描述，包含参数说明"""
    base_desc = mcp_tool.description or f"MCP tool: {mcp_tool.name}"

    schema = mcp_tool.input_schema
    if not schema or not schema.get('properties'):
        return base_desc

    properties = schema.get('properties', {})
    required = schema.get('required', [])

    if not properties:
        return base_desc

    # 构建参数说明
    param_lines = ["\n\n参数说明:"]
    for param_name, param_schema in properties.items():
        param_type = param_schema.get('type', 'string')
        param_desc = param_schema.get('description', '')
        is_required = param_name in required
        required_text = "必填" if is_required else "可选"

        param_line = f"- {param_name} ({param_type}, {required_text})"
        if param_desc:
            param_line += f": {param_desc}"

        # 添加默认值信息
        if 'default' in param_schema:
            param_line += f" (默认: {param_schema['default']})"

        # 添加枚举值信息
        if 'enum' in param_schema:
            param_line += f" (可选值: {', '.join(str(v) for v in param_schema['enum'])})"

        param_lines.append(param_line)

    return base_desc + "\n".join(param_lines)


def _create_input_model(tool: MCPTool) -> Type[BaseModel]:
    """根据 MCP 工具的 inputSchema 创建 Pydantic 模型"""
    schema = tool.input_schema
    properties = schema.get('properties', {})
    required = schema.get('required', [])

    fields = {}
    for prop_name, prop_schema in properties.items():
        is_required = prop_name in required
        fields[prop_name] = _json_schema_to_pydantic_field(prop_name, prop_schema, is_required)

    # 如果没有定义任何属性，创建一个空的输入模型
    if not fields:
        fields['_dummy'] = (Optional[str], Field(default=None, description="No input required"))

    model_name = f"{tool.name.replace('-', '_').replace('.', '_')}Input"
    return create_model(model_name, **fields)


class MCPToolWrapper(BaseTool):
    """将 MCP 工具包装为 LangChain Tool"""

    name: str = ""
    description: str = ""
    mcp_server_name: str = ""
    mcp_tool_name: str = ""
    args_schema: Optional[Type[BaseModel]] = None

    class Config:
        arbitrary_types_allowed = True

    def __init__(
        self,
        mcp_tool: MCPTool,
        **kwargs
    ):
        """
        初始化 MCP 工具包装器

        Args:
            mcp_tool: MCP 工具定义
        """
        # 创建输入参数 schema
        input_model = _create_input_model(mcp_tool)

        # 构建工具名称（包含服务器前缀以避免冲突）
        tool_name = f"mcp_{mcp_tool.server_name}_{mcp_tool.name}".replace('-', '_').replace('.', '_')

        # 构建增强的描述，包含参数说明
        enhanced_description = _build_enhanced_description(mcp_tool)

        super().__init__(
            name=tool_name,
            description=enhanced_description,
            mcp_server_name=mcp_tool.server_name,
            mcp_tool_name=mcp_tool.name,
            args_schema=input_model,
            **kwargs
        )

    def _run(
        self,
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **kwargs
    ) -> str:
        """同步调用 MCP 工具"""
        # 移除虚拟参数
        kwargs.pop('_dummy', None)

        try:
            # 尝试获取当前事件循环
            try:
                loop = asyncio.get_running_loop()
                # 如果已经在事件循环中运行，使用线程池
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(self._run_in_new_loop, kwargs)
                    return future.result(timeout=120)
            except RuntimeError:
                # 没有正在运行的事件循环，创建新的
                return self._run_in_new_loop(kwargs)

        except Exception as e:
            logger.error(f"MCP 工具调用失败: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return f"Error: {str(e)}"

    def _run_in_new_loop(self, kwargs: Dict[str, Any]) -> str:
        """在新的事件循环中运行异步调用"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._call_mcp_tool(kwargs))
        finally:
            loop.close()

    async def _arun(
        self,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
        **kwargs
    ) -> str:
        """异步调用 MCP 工具"""
        # 移除虚拟参数
        kwargs.pop('_dummy', None)

        try:
            return await self._call_mcp_tool(kwargs)
        except Exception as e:
            logger.error(f"MCP 工具调用失败: {e}")
            return f"Error: {str(e)}"

    async def _call_mcp_tool(self, arguments: Dict[str, Any]) -> str:
        """实际调用 MCP 工具"""
        manager = get_mcp_manager()

        # 检查工具是否被禁用
        config = manager.get_config()
        server_config = config.get('servers', {}).get(self.mcp_server_name, {})
        tools_config = server_config.get('tools', [])
        tool_config = next((t for t in tools_config if isinstance(t, dict) and t.get('name') == self.mcp_tool_name), None)

        if tool_config and not tool_config.get('enabled', True):
            return f"Error: 工具 '{self.mcp_tool_name}' 已被禁用，无法调用"

        client = manager.get_client(self.mcp_server_name)

        if not client:
            return f"Error: MCP server '{self.mcp_server_name}' not connected"

        if not client.is_healthy():
            return f"Error: MCP server '{self.mcp_server_name}' is not healthy"

        # 过滤掉 None 值的参数，MCP 服务器不接受 None
        filtered_arguments = {k: v for k, v in arguments.items() if v is not None}

        result = await client.call_tool(self.mcp_tool_name, filtered_arguments)

        if result.get('success'):
            return result.get('result', 'Success')
        else:
            # 优先返回 result 字段（如果有内容），否则返回 error
            output = result.get('result') or result.get('error', 'Unknown error')
            return f"Error: {output}"


def create_mcp_tools() -> list[BaseTool]:
    """
    创建所有 MCP 工具的 LangChain 包装器

    Returns:
        list[BaseTool]: LangChain 工具列表（仅包含启用的工具）
    """
    manager = get_mcp_manager()
    mcp_tools = manager.get_all_tools()

    langchain_tools = []
    for mcp_tool in mcp_tools:
        # 跳过禁用的工具
        if not mcp_tool.enabled:
            logger.info(f"跳过禁用的 MCP 工具: {mcp_tool.server_name}/{mcp_tool.name}")
            continue

        try:
            wrapper = MCPToolWrapper(mcp_tool)
            langchain_tools.append(wrapper)
            logger.info(f"创建 MCP 工具包装器: {wrapper.name}")
        except Exception as e:
            logger.error(f"创建工具包装器失败 [{mcp_tool.name}]: {e}")

    return langchain_tools


async def initialize_mcp_tools() -> list[BaseTool]:
    """
    初始化 MCP 系统并创建工具

    Returns:
        list[BaseTool]: LangChain 工具列表
    """
    manager = get_mcp_manager()
    await manager.initialize()
    return create_mcp_tools()
