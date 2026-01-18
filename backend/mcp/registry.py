"""MCP 工具注册表 - 管理内部工具和外部 MCP 工具"""
import logging
from typing import Any, Dict, List, Optional
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


class MCPToolRegistry:
    """MCP 工具注册表 - 管理内部工具和外部 MCP 工具"""

    def __init__(self):
        self._internal_tools: Dict[str, BaseTool] = {}
        self._mcp_tools: List[BaseTool] = []
        self._initialized = False

    def register_internal_tool(self, tool: BaseTool):
        """注册内部工具"""
        self._internal_tools[tool.name] = tool
        logger.info(f"注册内部工具: {tool.name}")

    def register_tool(self, tool: BaseTool):
        """注册工具（别名，兼容旧 API）"""
        self.register_internal_tool(tool)

    def set_mcp_tools(self, tools: List[BaseTool]):
        """设置 MCP 工具列表"""
        self._mcp_tools = tools
        logger.info(f"设置 MCP 工具: {len(tools)} 个")

    def get_internal_tool(self, name: str) -> Optional[BaseTool]:
        """获取内部工具"""
        return self._internal_tools.get(name)

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """获取工具（内部或 MCP）"""
        # 先查找内部工具
        tool = self._internal_tools.get(name)
        if tool:
            return tool

        # 再查找 MCP 工具
        for mcp_tool in self._mcp_tools:
            if mcp_tool.name == name:
                return mcp_tool

        return None

    def get_internal_tools(self) -> List[BaseTool]:
        """获取所有内部工具"""
        return list(self._internal_tools.values())

    def get_mcp_tools(self) -> List[BaseTool]:
        """获取所有 MCP 工具"""
        return self._mcp_tools

    def get_all_tools(self) -> List[BaseTool]:
        """获取所有工具（内部 + MCP）"""
        return list(self._internal_tools.values()) + self._mcp_tools

    def list_tool_names(self) -> List[str]:
        """列出所有工具名称"""
        internal_names = list(self._internal_tools.keys())
        mcp_names = [t.name for t in self._mcp_tools]
        return internal_names + mcp_names

    def list_tools(self) -> List[str]:
        """列出所有工具名称（别名，兼容旧 API）"""
        return self.list_tool_names()

    async def initialize_mcp_tools(self):
        """初始化 MCP 工具"""
        if self._initialized:
            return

        try:
            from backend.mcp.langchain import initialize_mcp_tools
            mcp_tools = await initialize_mcp_tools()
            self.set_mcp_tools(mcp_tools)
            self._initialized = True
            logger.info(f"MCP 工具初始化完成，共 {len(mcp_tools)} 个工具")
        except Exception as e:
            logger.error(f"MCP 工具初始化失败: {e}")
            self._mcp_tools = []

    async def refresh_mcp_tools(self):
        """刷新 MCP 工具（重新加载）"""
        self._initialized = False
        self._mcp_tools = []
        await self.initialize_mcp_tools()

    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized


# 全局注册表实例
_registry: Optional[MCPToolRegistry] = None


def get_tool_registry() -> MCPToolRegistry:
    """获取全局工具注册表"""
    global _registry
    if _registry is None:
        _registry = MCPToolRegistry()
    return _registry
