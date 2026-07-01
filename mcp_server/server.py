"""MCP HTTP Server for GitHub API - Modular version with auto-discovered tools.

Token is passed via Authorization: Bearer <token> header.
"""

import logging
from flask import Flask, request, jsonify
from flask_cors import CORS  # ДОБАВИТЬ ЭТУ СТРОКУ

from mcp_server.core.registry import ToolRegistry
from mcp_server.tools.github.client import GitHubClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # ДОБАВИТЬ ЭТУ СТРОКУ - разрешает все CORS-запросы

# ИЛИ более строгий вариант (только для вашего расширения):
# CORS(app, origins=["chrome-extension://bikejlmkiafpkoppifjmelhpfencmpka"])

registry = ToolRegistry()
registry.discover()

@app.route("/mcp", methods=["POST"])
def mcp_handler():
    data = request.get_json()
    method = data.get("method")
    req_id = data.get("id")

    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]

    logger.info(f"Request: method={method}, id={req_id}, token={'present' if token else 'missing'}")

    if method == "initialize":
        return jsonify({
            "jsonrpc": "2.0",
            "result": {
                "protocolVersion": "0.1.0",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "mcp-github-server", "version": "0.3.0"},
            },
            "id": req_id,
        })

    if method == "tools/list":
        tools = [t.to_mcp_tool_definition() for t in registry.get_all()]
        return jsonify({"jsonrpc": "2.0", "result": {"tools": tools}, "id": req_id})

    if method == "tools/call":
        if not token:
            return jsonify({"jsonrpc": "2.0", "error": {"code": -32000, "message": "Missing token"}, "id": req_id})

        params = data.get("params", {})
        tool_name = params.get("name")
        args = params.get("arguments", {})

        tool = registry.get(tool_name)
        if not tool or not tool.handler:
            return jsonify({"jsonrpc": "2.0", "error": {"code": -32602, "message": f"Tool not found: {tool_name}"}, "id": req_id})

        try:
            client = GitHubClient(token)
            output = tool.handler(client=client, **args)
            return jsonify({"jsonrpc": "2.0", "result": {"content": [{"type": "text", "text": output}]}, "id": req_id})
        except Exception as e:
            logger.error(f"Tool {tool_name} error: {e}")
            return jsonify({"jsonrpc": "2.0", "error": {"code": -32000, "message": str(e)}, "id": req_id})

    return jsonify({"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": req_id})

@app.route("/health")
def health():
    tools = [t.name for t in registry.get_all()]
    return jsonify({"status": "ok", "tools": tools})

def main():
    logger.info(f"Starting MCP GitHub Server v0.3.0 on port 3001")
    app.run(host="0.0.0.0", port=3001, debug=False)

if __name__ == "__main__":
    main()
