"""Tool registry with automatic discovery."""

import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import Any, Callable

from mcp_server.core.tool import Tool


class ToolRegistry:
    """Registry that discovers and manages MCP tools."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def discover(self) -> None:
        """Auto-discover tools from mcp_server.tools subpackages."""
        import mcp_server.tools as tools_pkg

        tools_path = Path(tools_pkg.__path__[0])

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
                            print(f"  Registered tool: {tool.name}")
            except Exception as e:
                print(f"  Warning: Failed to load {module_name}: {e}")

        print(f"Total tools registered: {len(self._tools)}")

    def register(self, tool: Tool) -> None:
        """Register a tool manually."""
        self._tools[tool.name] = tool

    def get_all(self) -> list[Tool]:
        """Return all registered tools."""
        return list(self._tools.values())

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)


def mcp_tool(name: str, description: str, parameters: dict[str, Any]):
    """Decorator to mark a function as an MCP tool.

    The decorated function should accept **kwargs and return a dict with
    'content' key containing a list of content items.
    """
    def decorator(func: Callable) -> Callable:
        func._mcp_tool = Tool(
            name=name,
            description=description,
            parameters=parameters,
            handler=func,
        )
        return func
    return decorator
