"""MCP HTTP Server for GitHub API - Modular version with auto-discovered tools.

Token is passed via Authorization: Bearer <token> header.
Implements the MCP Streamable HTTP transport (JSON-RPC 2.0 over POST /mcp).
"""

import logging
from flask import Flask, request, jsonify
from flask_cors import CORS

from mcp_server.core.registry import ToolRegistry
from mcp_server.tools.github.client import GitHubClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- MCP protocol versions -------------------------------------------------
SUPPORTED_PROTOCOL_VERSIONS = [
    "2025-11-25",
    "2025-06-18",
    "2025-03-26",
    "2024-11-05",
]
LATEST_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[0]

SERVER_NAME = "mcp-github-server"
SERVER_VERSION = "0.4.1"

# Tools that don't need a GitHub token (pure functions / meta / web)
TOKENLESS_PREFIXES = ("base64_", "hash_", "json_", "uuid_", "timestamp_", "date_", "regex_", "text_")
TOKENLESS_NAMES = {"list_my_tools", "describe_tool", "web_fetch", "web_search"}


def _tool_needs_token(tool_name: str) -> bool:
    if tool_name in TOKENLESS_NAMES:
        return False
    return not tool_name.startswith(TOKENLESS_PREFIXES)


app = Flask(__name__)
CORS(app)

registry = ToolRegistry()
registry.discover()

# Diagnostics for the last request (surfaced via /health)
_last_request = {"token": "none", "auth_header_present": False}


def _json_rpc_result(req_id, result):
    return jsonify({"jsonrpc": "2.0", "id": req_id, "result": result})


def _json_rpc_error(req_id, code, message):
    return jsonify({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def _negotiate_protocol_version(client_version):
    if client_version in SUPPORTED_PROTOCOL_VERSIONS:
        return client_version
    return LATEST_PROTOCOL_VERSION


def _extract_token(auth_header: str):
    """Return (token, note). note explains a malformed header, if any."""
    if not auth_header:
        return None, "no Authorization header"
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        if not token:
            return None, "'Bearer ' present but token is empty"
        return token, None
    # Header present but not in Bearer form — most common mistake
    return None, "Authorization header present but missing 'Bearer ' prefix"


@app.route("/mcp", methods=["POST", "GET", "OPTIONS"])
def mcp_handler():
    if request.method == "OPTIONS":
        return ("", 204)
    if request.method == "GET":
        return ("Method Not Allowed", 405, {"Allow": "POST"})

    data = request.get_json(silent=True) or {}
    method = data.get("method")
    req_id = data.get("id")
    params = data.get("params", {}) or {}

    auth_header = request.headers.get("Authorization", "")
    token, note = _extract_token(auth_header)

    global _last_request
    _last_request = {
        "token": "present" if token else "missing",
        "auth_header_present": bool(auth_header),
        "note": note or "ok",
    }

    logger.info(
        "Request: method=%s, id=%s, token=%s%s",
        method,
        req_id,
        "present" if token else "missing",
        f" ({note})" if note else "",
    )

    # --- Lifecycle ---------------------------------------------------------
    if method == "initialize":
        client_version = params.get("protocolVersion")
        negotiated = _negotiate_protocol_version(client_version)
        logger.info(
            "initialize: client requested %s -> negotiated %s", client_version, negotiated
        )
        server_info = {"name": SERVER_NAME, "version": SERVER_VERSION}
        if not token:
            server_info["warning"] = (
                "No GitHub token received. Send header 'Authorization: Bearer <token>'. "
                "Token-less tools (utils, meta, web) still work; GitHub tools will fail."
            )
        return _json_rpc_result(
            req_id,
            {
                "protocolVersion": negotiated,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": server_info,
            },
        )

    if method == "notifications/initialized":
        return ("", 202)

    if method == "ping":
        return _json_rpc_result(req_id, {})

    # --- Tools -------------------------------------------------------------
    if method == "tools/list":
        tools = [t.to_mcp_tool_definition() for t in registry.get_all()]
        return _json_rpc_result(req_id, {"tools": tools})

    if method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {}) or {}

        tool = registry.get(tool_name)
        if not tool or not tool.handler:
            return _json_rpc_error(req_id, -32602, f"Tool not found: {tool_name}")

        needs_token = _tool_needs_token(tool_name)
        if needs_token and not token:
            hint = (
                "Add header 'Authorization: Bearer <github_token>' to the MCP server config. "
                "(No square brackets, keep the word 'Bearer' and one space before the token.)"
            )
            if note:
                hint = f"{note}. {hint}"
            logger.warning("tools/call '%s' without token: %s", tool_name, hint)
            return _json_rpc_error(req_id, -32001, f"Missing GitHub token. {hint}")

        try:
            client = GitHubClient(token) if token else None
            output = tool.handler(client=client, **args)
            if isinstance(output, dict) and "content" in output:
                result = output
            else:
                result = {"content": [{"type": "text", "text": str(output)}]}
            return _json_rpc_result(req_id, result)
        except Exception as e:  # noqa: BLE001
            logger.exception("Tool %s error", tool_name)
            return _json_rpc_error(req_id, -32000, str(e))

    if isinstance(method, str) and method.startswith("notifications/"):
        return ("", 202)

    return _json_rpc_error(req_id, -32601, "Method not found")


@app.route("/health")
def health():
    tools = [t.name for t in registry.get_all()]
    return jsonify(
        {
            "status": "ok",
            "server": SERVER_NAME,
            "version": SERVER_VERSION,
            "protocol_versions": SUPPORTED_PROTOCOL_VERSIONS,
            "last_request": _last_request,
            "tool_count": len(tools),
            "tools": tools,
            "hint": "Header must be: Authorization: Bearer <github_token>",
        }
    )


def main():
    logger.info("Starting %s v%s on port 3001", SERVER_NAME, SERVER_VERSION)
    logger.info("Expected header: Authorization: Bearer <github_token>")
    app.run(host="0.0.0.0", port=3001, debug=False)


if __name__ == "__main__":
    main()
