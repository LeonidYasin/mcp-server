"""Tool dataclass for MCP tools."""

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Tool:
    """Represents an MCP tool with its metadata and handler."""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    handler: Callable | None = None

    def to_mcp_tool_definition(self) -> dict[str, Any]:
        """Convert to MCP tool definition format."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": {
                "type": "object",
                "properties": self.parameters,
                "required": list(self.parameters.keys()),
            },
        }
