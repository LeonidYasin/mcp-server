"""MCP meta tools: introspection of the tool registry."""

import json

from mcp_server.core.registry import mcp_tool, registry as _global_registry


def _resolve_registry(client=None):
    """Return the live registry instance.

    server.py builds its own ToolRegistry and calls discover(). The module-level
    `registry` in core/registry.py is what those tools live in once imported, so
    prefer that if it has tools; otherwise fall back to the passed-in client's.
    """
    if _global_registry.get_all():
        return _global_registry
    return None


@mcp_tool(
    name="list_my_tools",
    description="Возвращает список всех зарегистрированных MCP-инструментов",
    parameters={},
    required=[],
)
def list_my_tools(client=None) -> str:
    reg = _resolve_registry(client)
    if reg is None:
        # fallback: import the server's registry lazily
        from mcp_server.server import registry as server_registry
        reg = server_registry
    tools = reg.get_all()
    lines = [f"Всего инструментов: {len(tools)}", ""]
    for t in sorted(tools, key=lambda x: x.name):
        lines.append(f"  • {t.name} — {t.description}")
    return "\n".join(lines)


@mcp_tool(
    name="describe_tool",
    description="Возвращает JSON-схему конкретного MCP-инструмента",
    parameters={
        "name": {"type": "string", "description": "Имя инструмента"},
    },
    required=["name"],
)
def describe_tool(client=None, **kwargs) -> str:
    reg = _resolve_registry(client)
    if reg is None:
        from mcp_server.server import registry as server_registry
        reg = server_registry
    tool = reg.get(kwargs["name"])
    if not tool:
        return f"❌ Инструмент '{kwargs['name']}' не найден"
    return json.dumps(tool.to_mcp_tool_definition(), indent=2, ensure_ascii=False)
