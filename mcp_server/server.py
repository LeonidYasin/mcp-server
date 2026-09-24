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
# The client sends its requested version in `initialize` params.protocolVersion.
# The server MUST answer with a version it supports. If the client's version is
# unknown we answer with our latest supported one (the client decides whether to
# continue) instead of erroring out.
# See: https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle
SUPPORTED_PROTOCOL_VERSIONS = [
    "2025-11-25",
    "2025-06-18",
    "2025-03-26",
    "2024-11-05",
]
LATEST_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[0]

SERVER_NAME = "mcp-github-server"
SERVER_VERSION = "0.4.0"

app = Flask(__name__)
CORS(app)  # allow requests from the browser extension (incl. preflight OPTIONS)

registry = ToolRegistry()
registry.discover()


def _json_rpc_result(req_id, result):
    return jsonify({"jsonrpc": "2.0", "id": req_id, "result": result})


def _json_rpc_error(req_id, code, message):
    return jsonify({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def _negotiate_protocol_version(client_version):
    """Return the protocol version we will speak.

    Per the spec the server responds with a version it supports. If it does not
    support the requested version it should respond with its latest supported
    version and let the client decide what to do.
    """
    if client_version in SUPPORTED_PROTOCOL_VERSIONS:
        return client_version
    return LATEST_PROTOCOL_VERSION


@app.route("/mcp", methods=["POST", "GET", "OPTIONS"])
def mcp_handler():
    # CORS preflight
    if request.method == "OPTIONS":
        return ("", 204)

    # Streamable HTTP: GET is optional (SSE stream). We do not offer a stream,
    # so advertise POST only.
    if request.method == "GET":
        return ("Method Not Allowed", 405, {"Allow": "POST"})

    data = request.get_json(silent=True) or {}
    method = data.get("method")
    req_id = data.get("id")
    params = data.get("params", {}) or {}

    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:] if auth_header.startswith("Bearer ") else None

    logger.info(
        "Request: method=%s, id=%s, token=%s",
        method,
        req_id,
        "present" if token else "missing",
    )

    # --- Lifecycle ---------------------------------------------------------
    if method == "initialize":
        client_version = params.get("protocolVersion")
        negotiated = _negotiate_protocol_version(client_version)
        logger.info(
            "initialize: client requested %s -> negotiated %s",
            client_version,
            negotiated,
        )
        return _json_rpc_result(
            req_id,
            {
                "protocolVersion": negotiated,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        )

    # Notification (no id): acknowledge with 202 and empty body.
    if method == "notifications/initialized":
        return ("", 202)

    if method == "ping":
        return _json_rpc_result(req_id, {})

    # --- Tools -------------------------------------------------------------
    if method == "tools/list":
        tools = [t.to_mcp_tool_definition() for t in registry.get_all()]
        return _json_rpc_result(req_id, {"tools": tools})

    if method == "tools/call":
        if not token:
            return _json_rpc_error(req_id, -32000, "Missing token")

        tool_name = params.get("name")
        args = params.get("arguments", {}) or {}

        tool = registry.get(tool_name)
        if not tool or not tool.handler:
            return _json_rpc_error(req_id, -32602, f"Tool not found: {tool_name}")

        try:
            client = GitHubClient(token)
            output = tool.handler(client=client, **args)

            # Tools may return either a full MCP result {"content": [...]} or a
            # plain value/string. Normalise without double-wrapping.
            if isinstance(output, dict) and "content" in output:
                result = output
            else:
                result = {"content": [{"type": "text", "text": str(output)}]}

            return _json_rpc_result(req_id, result)
        except Exception as e:  # noqa: BLE001
            logger.exception("Tool %s error", tool_name)
            return _json_rpc_error(req_id, -32000, str(e))

    # Notifications are one-way: never answer with an error for them.
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
            "tools": tools,
        }
    )


def main():
    logger.info("Starting %s v%s on port 3001", SERVER_NAME, SERVER_VERSION)
    app.run(host="0.0.0.0", port=3001, debug=False)


if __name__ == "__main__":
    main()
