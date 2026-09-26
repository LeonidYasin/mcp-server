"""MCP HTTP Server for GitHub API - Modular version with auto-discovered tools.

Token is passed via Authorization: Bearer <token> header.
Implements the MCP Streamable HTTP transport (JSON-RPC 2.0 over POST /mcp).
"""

import logging
from flask import Flask, request, jsonify
from flask_cors import CORS

from mcp_server import __version__
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
# Version is defined once, in mcp_server/__init__.py (__version__).
SERVER_VERSION = __version__


def _build_info() -> dict:
    """Return runtime build info: version, git commit, date, branch.

    Commit/date/branch come from local git if available; otherwise fall back to
    CI-provided env vars (GIT_COMMIT / GIT_BUILD_DATE) or 'unknown'. This lets
    a running server always report exactly which revision it was started from.
    """
    import os
    import subprocess

    info = {
        "version": SERVER_VERSION,
        "commit": os.environ.get("GIT_COMMIT", "unknown"),
        "commit_date": os.environ.get("GIT_BUILD_DATE", "unknown"),
        "branch": os.environ.get("GIT_BRANCH", "unknown"),
    }

    def _git(args):
        try:
            return subprocess.check_output(
                ["git", *args], stderr=subprocess.DEVNULL, text=True
            ).strip()
        except Exception:
            return None

    commit = _git(["rev-parse", "--short", "HEAD"])
    if commit:
        info["commit"] = commit
    date = _git(["log", "-1", "--format=%cd", "--date=iso"])
    if date:
        info["commit_date"] = date
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    if branch:
        info["branch"] = branch

    return info


def _build_banner() -> str:
    """One-line human-readable banner printed at startup."""
    b = _build_info()
    return (
        f"mcp-server v{b['version']} - commit {b['commit']} "
        f"({b['branch']}) - {b['commit_date']}"
    )


# Tools that don't need a GitHub token (pure functions / meta / web)
TOKENLESS_PREFIXES = ("base64_", "hash_", "json_", "uuid_", "timestamp_", "date_", "regex_", "text_")
TOKENLESS_NAMES = {"list_my_tools", "describe_tool", "web_fetch", "web_search"}


def _tool_needs_token(tool_name: str) -> bool:
    if tool_name in TOKENLESS_NAMES:
        return False
    return not tool_name.startswith(TOKENLESS_PREFIXES)


def _normalize_content(output):
    """Coerce any tool return value into a strict MCP `content` payload.

    MCP clients persist the tool result and validate its shape. A tool that
    returns e.g. {"content": "plain string"} or {"content": {"foo": 1}}
    produces a record the client cannot persist, which surfaces as
    `tool_post_effect_persistence_failed: Invalid tool history record`.

    We guarantee: content is a non-empty list of blocks, each block is a dict
    with a string `type`. Text blocks always carry a string `text`.
    """
    # Already a well-formed content list? Pass through (but still validate blocks).
    raw = None
    if isinstance(output, dict) and "content" in output:
        raw = output["content"]

    if raw is None:
        blocks = [{"type": "text", "text": str(output)}]
    elif isinstance(raw, list):
        blocks = raw
    else:
        # content present but not a list (str/dict/int/None) -> wrap as text
        blocks = [{"type": "text", "text": str(raw)}]

    normalized = []
    for block in blocks:
        if isinstance(block, dict):
            b = dict(block)
            btype = b.get("type")
            if not isinstance(btype, str) or not btype:
                b["type"] = "text"
                btype = "text"
            if btype == "text" and not isinstance(b.get("text"), str):
                b["text"] = str(b.get("text", ""))
            normalized.append(b)
        else:
            normalized.append({"type": "text", "text": str(block)})

    if not normalized:
        normalized = [{"type": "text", "text": "(empty result)"}]

    return {"content": normalized}


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
        _b = _build_info()
        server_info = {
            "name": SERVER_NAME,
            "version": SERVER_VERSION,
            "commit": _b["commit"],
            "commit_date": _b["commit_date"],
            "branch": _b["branch"],
        }
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
            result = _normalize_content(output)
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
    _b = _build_info()
    return jsonify(
        {
            "status": "ok",
            "server": SERVER_NAME,
            "version": SERVER_VERSION,
            "build": _b,
            "commit": _b["commit"],
            "commit_date": _b["commit_date"],
            "branch": _b["branch"],
            "protocol_versions": SUPPORTED_PROTOCOL_VERSIONS,
            "last_request": _last_request,
            "tool_count": len(tools),
            "tools": tools,
            "hint": "Header must be: Authorization: Bearer <github_token>",
        }
    )


def main():
    logger.info("Starting %s on port 3001", _build_banner())
    logger.info("Expected header: Authorization: Bearer <github_token>")
    app.run(host="0.0.0.0", port=3001, debug=False)


if __name__ == "__main__":
    main()
