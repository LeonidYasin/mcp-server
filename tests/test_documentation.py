"""Keep published docs tied to the registry, without calling tool handlers."""
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "check_docs", Path(__file__).resolve().parents[1] / "scripts/check_docs.py"
)
DOCS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DOCS)


def test_documentation_inventory_and_links():
    assert DOCS.check()["result"] == "passed"


def test_documentation_links_detect_missing_file_and_anchor(tmp_path):
    (tmp_path / "README.md").write_text(
        "# Intro\n[missing](absent.md)\n[bad](target.md#absent)\n", encoding="utf-8"
    )
    (tmp_path / "target.md").write_text("# Exists\n", encoding="utf-8")
    checked, errors = DOCS.check_links(tmp_path)
    assert checked == 2
    assert len(errors) == 2


def test_documentation_links_ignore_code_and_validate_unicode_anchor(tmp_path):
    (tmp_path / "README.md").write_text(
        "# Начало\n[ok](#начало)\n````markdown\n[not-a-link](absent.md)\n"
        "```\nexample\n```\n````\n", encoding="utf-8"
    )
    assert DOCS.check_links(tmp_path) == (1, [])


def test_documentation_rejects_unclosed_fence():
    with pytest.raises(ValueError, match="Unclosed"):
        DOCS.without_fences("# Hello\n```python\npass\n")


def test_documented_http_examples_and_boundaries():
    """Fresh registry, real Flask dispatch, zero outbound calls or secrets."""
    import os
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    code = r'''
import hashlib, json, re
from pathlib import Path
from unittest.mock import patch
from mcp_server.server import app, registry
text = Path("docs/http-transport.md").read_text(encoding="utf-8")
requests = [json.loads(s) for s in re.findall(r"```json\n(.*?)\n```", text, re.S)]
assert len(requests) == 4
client = app.test_client()
# Fail if any example unexpectedly attempts network I/O.
with patch("httpx.Client.request", side_effect=AssertionError("Network forbidden")):
    for request in requests:
        if request["method"] == "tools/call":
            params = request["params"]
            tool = registry.get(params["name"])
            assert tool is not None
            assert set(params["arguments"]) <= set(tool.parameters)
            assert set(tool.required) <= set(params["arguments"])
        response = client.post("/mcp", json=request)
        assert response.status_code == 200
        assert "Mcp-Session-Id" not in response.headers
        body = response.get_json()
        assert "error" not in body, body
        assert body["id"] == request["id"]
        if request["id"] == 1:
            assert body["result"]["protocolVersion"] == "2025-11-25"
        if request["id"] == 3:
            expected = "sha256: " + hashlib.sha256(b"hello").hexdigest()
            assert body["result"]["content"][0]["text"] == expected
        if request["id"] == 4:
            schema = json.loads(body["result"]["content"][0]["text"])
            assert schema["name"] == "get_pull_request"
    get = client.get("/mcp")
    assert get.status_code == 405 and get.headers["Allow"] == "POST"
    assert client.options("/mcp").status_code == 204
    assert client.post("/mcp", json={"jsonrpc":"2.0","method":"notifications/initialized"}).status_code == 202
    csv = client.post("/mcp", json={"jsonrpc":"2.0","id":5,"method":"tools/call", "params":{"name":"csv_parse","arguments":{"text":"a\n1"}}}).get_json()
    assert csv["error"]["code"] == -32001
'''
    env = dict(os.environ)
    for flag in ("ENABLE_LOCAL_TOOLS", "ENABLE_LOCAL_SHELL", "ENABLE_SYNAPSE"):
        env[flag] = "0"
    subprocess.run([sys.executable, "-c", code], cwd=root, env=env,
                   capture_output=True, text=True, timeout=30, check=True)


def test_dev_bind_defaults_are_loopback():
    import os
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    env.pop("MCP_HOST", None)
    env.pop("MCP_PORT", None)
    code = '''
from unittest.mock import patch
from mcp_server.server import app, main
with patch.object(app, "run") as run:
    main()
run.assert_called_once_with(host="127.0.0.1", port=3001, debug=False)
'''
    subprocess.run([sys.executable, "-c", code], cwd=root, env=env,
                   capture_output=True, text=True, timeout=30, check=True)
