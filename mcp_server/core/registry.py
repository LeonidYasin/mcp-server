"""Tool registry with automatic discovery."""

import importlib
import pkgutil
from pathlib import Path
from typing import Any, Callable

from mcp_server.core.tool import Tool


class ToolRegistry:
    """Registry that discovers and manages MCP tools."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._discovered = False

    def discover(self) -> None:
        """Auto-discover tools from mcp_server.tools subpackages."""
        if self._discovered:
            return
        import mcp_server.tools as tools_pkg
        tools_path = Path(tools_pkg.__path__[0])
        print(f"[Registry] Discovering tools in: {tools_path}")
        for finder, name, ispkg in pkgutil.iter_modules([str(tools_path)]):
            if not ispkg:
                continue
            module_name = f"mcp_server.tools.{name}"
            try:
                module = importlib.import_module(module_name)
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if callable(attr) and hasattr(attr, "_mcp_tool"):
                        tool: Tool = attr._mcp_tool
                        if isinstance(tool, Tool):
                            self._tools[tool.name] = tool
                            print(f"[Registry]   + {tool.name}")
            except Exception as e:
                print(f"[Registry]   Warning: {module_name}: {e}")
        self._discovered = True
        print(f"[Registry] Total: {len(self._tools)}")

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get_all(self) -> list[Tool]:
        return list(self._tools.values())

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)


def mcp_tool(name: str, description: str, parameters: dict[str, Any], required: list[str] | None = None):
    """Decorator to mark a function as an MCP tool."""
    def decorator(func: Callable) -> Callable:
        func._mcp_tool = Tool(
            name=name, description=description, parameters=parameters,
            required=required or [], handler=func,
        )
        return func
    return decorator
