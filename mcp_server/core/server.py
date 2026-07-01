"""MCP stdio server implementation."""

import json
import sys
from typing import Any

from mcp_server.core.registry import ToolRegistry
from mcp_server.tools.github.client import GitHubClient


class MCPServer:
    """MCP server using stdio transport."""

    def __init__(self, token: str, registry: ToolRegistry):
        self.client = GitHubClient(token)
        self.registry = registry

    async def run(self) -> None:
        """Run the server, reading JSON-RPC messages from stdin."""
        print("MCP GitHub Server starting...", file=sys.stderr)
        print(f"Tools available: {[t.name for t in self.registry.get_all()]}", file=sys.stderr)

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                request = json.loads(line)
                response = await self._handle_request(request)
                if response is not None:
                    print(json.dumps(response), flush=True)
            except json.JSONDecodeError as e:
                print(f"Invalid JSON: {e}", file=sys.stderr)
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)

    async def _handle_request(self, request: dict) -> dict | None:
        """Handle a JSON-RPC request."""
        method = request.get("method")
        req_id = request.get("id")

        if method == "initialize":
            return self._make_response(req_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "mcp-github-server",
                    "version": "0.1.0",
                },
            })

        if method == "notifications/initialized":
            return None

        if method == "tools/list":
            tools = [t.to_mcp_tool_definition() for t in self.registry.get_all()]
            return self._make_response(req_id, {"tools": tools})

        if method == "tools/call":
            tool_name = request["params"]["name"]
            arguments = request["params"].get("arguments", {})
            return await self._call_tool(req_id, tool_name, arguments)

        return self._make_error(req_id, -32601, f"Method not found: {method}")

    async def _call_tool(self, req_id: Any, name: str, args: dict) -> dict:
        """Call a tool and return the result."""
        tool = self.registry.get(name)
        if not tool:
            return self._make_error(req_id, -32602, f"Tool not found: {name}")

        if not tool.handler:
            return self._make_error(req_id, -32603, f"Tool has no handler: {name}")

        try:
            result = await tool.handler(client=self.client, **args)
            return self._make_response(req_id, result)
        except Exception as e:
            return self._make_error(req_id, -32603, str(e))

    def _make_response(self, req_id: Any, result: Any) -> dict:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def _make_error(self, req_id: Any, code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}
