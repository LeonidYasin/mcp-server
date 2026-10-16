"""Synthetic binary staging gates: no tokens, external calls or private fixtures."""
import base64
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys
from types import SimpleNamespace
import zipfile

import httpx
import pytest

from mcp_server.core.uploads import CHUNK_BYTES, MAX_CHUNKS, Limits, UploadError, UploadStore, decode_chunk
from mcp_server.tools.uploads import api


def digest(data):
    return hashlib.sha256(data).hexdigest()


@pytest.fixture(autouse=True)
def upload_allowlist(monkeypatch):
    monkeypatch.setenv("FILE_UPLOAD_ALLOWED_USERS", "123")


@pytest.fixture
def store(tmp_path):
    root = tmp_path / "private-staging"
    root.mkdir(mode=0o700)
    return UploadStore(root)


def begin(store, data=b"abc", owner="github:1", name="synthetic.bin", key=None):
    return store.begin(owner, name, len(data), digest(data), key or secrets.token_hex(32))


def append(store, uid, data=b"abc", offset=0, owner="github:1"):
    return store.append(owner, uid, offset, base64.b64encode(data).decode(), digest(data))


def archive(xlsx=False):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        if xlsx:
            z.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
            z.writestr("_rels/.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
            z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Synthetic" sheetId="1" r:id="rId1"/></sheets></workbook>')
            z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>synthetic only</t></is></c><c r="B1"><v>42</v></c></row></sheetData></worksheet>')
        else:
            z.writestr("synthetic.bin", bytes(range(256)) * 128)
    return out.getvalue()


@pytest.mark.parametrize("data,name", [(b"", "empty.bin"), (bytes(range(256)) * 300, "nonutf8.bin"),
                                          (archive(), "synthetic.zip"), (archive(True), "synthetic.xlsx")])
def test_round_trip_arbitrary_binary_zip_xlsx(store, data, name):
    created = begin(store, data, name=name)
    assert "file_id" not in created
    uid = created["upload_id"]
    for offset in range(0, len(data), CHUNK_BYTES):
        chunk = data[offset:offset + CHUNK_BYTES]
        first = append(store, uid, chunk, offset)
        assert append(store, uid, chunk, offset) == first
    final = store.finish("github:1", uid)
    assert final["size"] == len(data) and final["sha256"] == digest(data)
    assert store.finish("github:1", uid) == final
    with store.verified_chunks("github:1", final["file_id"]) as parts:
        assert b"".join(parts) == data
    if name.endswith(("zip", "xlsx")):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            assert z.testzip() is None
            assert z.read("xl/worksheets/sheet1.xml") if name.endswith("xlsx") else z.read("synthetic.bin")


def test_restart_and_begin_idempotency(store):
    data, key = b"abc", secrets.token_hex(32)
    first = begin(store, data, key=key)
    reopened = UploadStore(store.root)
    assert begin(reopened, data, key=key) == first
    append(reopened, first["upload_id"])
    finalized = reopened.finish("github:1", first["upload_id"])
    assert begin(UploadStore(store.root), data, key=key)["file_id"] == finalized["file_id"]
    with pytest.raises(UploadError, match="request_key_conflict"):
        begin(store, b"xyz", key=key)


@pytest.mark.parametrize("name", ["", ".", "..", "../x", "x/y", "x\\y", "x:y", ".env", " a", "a ", "a\n", "a\x00", "a" * 129, "e\u0301"])
def test_reject_unsafe_name(store, name):
    with pytest.raises(UploadError, match="invalid_name"):
        begin(store, name=name)


@pytest.mark.parametrize("field,value,error", [
    ("size", -1, "integer"), ("size", True, "integer"), ("size", 1.0, "integer"),
    ("size", 67108865, "size_limit"), ("sha256", "A" * 64, "sha256"),
    ("sha256", "../x", "sha256"), ("request_key", "x", "invalid_id"),
])
def test_begin_bounds(store, field, value, error):
    kwargs = dict(name="safe.bin", size=3, sha256=digest(b"abc"), request_key=secrets.token_hex(32));kwargs[field] = value
    with pytest.raises(UploadError, match=error):
        store.begin("github:1", **kwargs)


@pytest.mark.parametrize("data,error", [("", "size_limit"), ("!@#$", "base64"), ("/w==\n", "base64"),
                                       ("/x==", "base64"), ("a" * (65536 + 1), "size_limit"), (None, "size_limit")])
def test_bad_base64_and_encoded_bounds(data, error):
    with pytest.raises(UploadError, match=error):
        decode_chunk(data, digest(b"a"))


def test_chunk_integrity_gap_overlap_and_size(store):
    uid = begin(store, b"abcdef")["upload_id"]
    with pytest.raises(UploadError, match="chunk_hash_mismatch"):
        store.append("github:1", uid, 0, "YWJj", digest(b"other"))
    with pytest.raises(UploadError, match="offset_conflict"):
        append(store, uid, b"abc", 1)
    append(store, uid, b"abc")
    with pytest.raises(UploadError, match="chunk_conflict"):
        append(store, uid, b"xyz")
    with pytest.raises(UploadError, match="offset_conflict"):
        append(store, uid, b"bcd", 1)
    with pytest.raises(UploadError, match="size_mismatch"):
        append(store, uid, b"defg", 3)
    with pytest.raises(UploadError, match="integer"):
        append(store, uid, b"def", True)
    assert store.status("github:1", uid)["received"] == 3
    append(store, uid, b"def", 3)
    final = store.finish("github:1", uid)
    assert append(store, uid, b"def", 3) == final
    with pytest.raises(UploadError, match="already_finalized"):
        append(store, uid, b"a", 6)


def test_incomplete_and_final_digest_fail_closed(store):
    uid = begin(store)["upload_id"]
    with pytest.raises(UploadError, match="incomplete"):
        store.finish("github:1", uid)
    append(store, uid, b"xyz")
    with pytest.raises(UploadError, match="file_hash_mismatch"):
        store.finish("github:1", uid)
    assert "file_id" not in store.status("github:1", uid)
    with pytest.raises(UploadError, match="not_found"):
        with store.verified_chunks("github:1", "file_" + uid):
            pass


def test_scoped_owner_all_operations(store):
    uid = begin(store)["upload_id"]
    for operation in [lambda: store.status("github:2", uid), lambda: append(store, uid, owner="github:2"),
                      lambda: store.finish("github:2", uid), lambda: store.cancel("github:2", uid)]:
        with pytest.raises(UploadError, match="not_found"):
            operation()
    append(store, uid)
    fid = store.finish("github:1", uid)["file_id"]
    with pytest.raises(UploadError, match="not_found"):
        with store.verified_chunks("github:2", fid): pass
    assert store.status("github:1", uid)["received"] == 3


@pytest.mark.parametrize("limits", [Limits(owner_bytes=5), Limits(total_bytes=5), Limits(owner_uploads=1), Limits(total_uploads=1)])
def test_quota_reserves_expected_not_received_bytes(store, limits):
    s = UploadStore(store.root, limits=limits)
    uid = begin(s)["upload_id"]
    with pytest.raises(UploadError, match="quota"):
        begin(s)
    s.cancel("github:1", uid)
    assert begin(s)["received"] == 0


def test_other_owner_quotas_and_finalized_counts(store):
    s = UploadStore(store.root, limits=Limits(owner_uploads=1, total_uploads=2))
    a = begin(s)["upload_id"];append(s, a);s.finish("github:1", a)
    begin(s, owner="github:2")
    with pytest.raises(UploadError, match="quota"):
        begin(s, owner="github:3")
    with pytest.raises(UploadError, match="quota"):
        begin(s)


def test_ttl_reclaims_chunks_and_releases_quota(store):
    now = [1000.0]
    s = UploadStore(store.root, limits=Limits(total_uploads=1, ttl_seconds=5), clock=lambda: now[0])
    uid = begin(s)["upload_id"];append(s, uid);fid = s.finish("github:1", uid)["file_id"]
    now[0] += 5
    with pytest.raises(UploadError, match="expired"):
        s.status("github:1", uid)
    # Cleanup commits even on error, and does not disclose other owners' counts.
    with sqlite3.connect(s.root / "staging.sqlite3") as db:
        assert db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 0
    assert s.cleanup("github:2") == {"cleanup": "completed"}
    with pytest.raises(UploadError, match="expired"):
        with s.verified_chunks("github:1", fid): pass
    assert begin(s)["received"] == 0


def test_cancel_finalized_invalidates_file_id(store):
    uid = begin(store)["upload_id"];append(store, uid);fid = store.finish("github:1", uid)["file_id"]
    assert store.cancel("github:1", uid) == {"deleted": True}
    with pytest.raises(UploadError, match="not_found"):
        with store.verified_chunks("github:1", fid): pass
    with pytest.raises(UploadError, match="not_found"):
        store.cancel("github:1", uid)


@pytest.mark.parametrize("kind", ["root_symlink", "db_symlink", "db_hardlink", "journal_symlink", "public_root", "public_db"])
def test_refuse_unsafe_filesystem(store, tmp_path, kind):
    target = tmp_path / "outside";target.write_bytes(b"private sentinel")
    db = store.root / "staging.sqlite3"
    if kind == "root_symlink":
        link = tmp_path / "link";link.symlink_to(store.root, target_is_directory=True);store = UploadStore(link)
    elif kind == "db_symlink": db.symlink_to(target)
    elif kind == "db_hardlink": os.link(target, db)
    elif kind == "journal_symlink": (store.root / "staging.sqlite3-journal").symlink_to(target)
    elif kind == "public_root": store.root.chmod(0o755)
    elif kind == "public_db": db.write_bytes(b"");db.chmod(0o644)
    with pytest.raises(UploadError, match="unsafe_staging"):
        begin(store)
    assert target.read_bytes() == b"private sentinel"


def test_path_and_file_ids_never_become_paths(store):
    for uid in ["../etc/passwd", "/tmp/foo", "x" * 64, "A" * 64, None]:
        with pytest.raises(UploadError, match="invalid_id"):
            store.status("github:1", uid)
    with pytest.raises(UploadError, match="unsafe_staging_root"):
        begin(UploadStore("relative"))


def test_cross_connection_parallel_retry_and_quota(store):
    # Each worker opens its own connection, as separate Gunicorn workers do.
    key = secrets.token_hex(32)
    with ThreadPoolExecutor(8) as pool:
        rows = list(pool.map(lambda _: begin(UploadStore(store.root), key=key), range(8)))
    assert len({r["upload_id"] for r in rows}) == 1
    uid = rows[0]["upload_id"]
    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(lambda _: append(UploadStore(store.root), uid), range(8)))
    assert all(r["received"] == 3 for r in results)
    with ThreadPoolExecutor(8) as pool:
        ids = list(pool.map(lambda _: UploadStore(store.root).finish("github:1", uid)["file_id"], range(8)))
    assert len(set(ids)) == 1


def test_database_tampering_never_returns_verified_file(store):
    uid = begin(store)["upload_id"];append(store, uid);fid = store.finish("github:1", uid)["file_id"]
    with sqlite3.connect(store.root / "staging.sqlite3") as db:
        db.execute("UPDATE chunks SET data=? WHERE upload_id=?", (b"xyz", uid))
    with pytest.raises(UploadError, match="file_hash_mismatch"):
        with store.verified_chunks("github:1", fid): pass


def fake_client(status=200, body=None, fail=False):
    def request(req):
        assert str(req.url) == "https://api.github.com/user"
        assert req.headers["Authorization"] == "Bearer synthetic-test-token"
        if fail: raise httpx.ConnectError("synthetic-test-token must not leak")
        return httpx.Response(status, json=body if body is not None else {"id": 123})
    return SimpleNamespace(_client=httpx.Client(transport=httpx.MockTransport(request)),
                           _headers={"Authorization": "Bearer synthetic-test-token"})


@pytest.mark.parametrize("status,body,error", [(401, {}, "authentication_failed"), (302, {}, "authentication_failed"),
                                             (403, {}, "authentication_failed"), (200, {"id": True}, "authentication_failed"),
                                             (200, {"id": -1}, "authentication_failed"), (200, {}, "authentication_failed")])
def test_owner_must_be_verified(status, body, error):
    c = fake_client(status, body)
    try:
        with pytest.raises(UploadError, match=error): api.authenticate_owner(c)
    finally: c._client.close()


def test_owner_uses_verified_numeric_id_and_no_redirects():
    c = fake_client()
    try: assert api.authenticate_owner(c) == "github:123"
    finally: c._client.close()
    c = fake_client(fail=True)
    try:
        with pytest.raises(UploadError, match="authentication_unavailable"): api.authenticate_owner(c)
    finally: c._client.close()


def unpack(value):
    return json.loads(value["content"][0]["text"])


def test_disabled_fails_before_auth_and_has_no_side_effect(monkeypatch, store):
    monkeypatch.delenv("ENABLE_FILE_UPLOADS", raising=False)
    monkeypatch.setattr(api, "authenticate_owner", lambda c: pytest.fail("Must not authenticate disabled tools"))
    assert unpack(api.cleanup_file_uploads(None)) == {"ok": False, "error": "uploads_disabled"}
    assert not list(store.root.iterdir())


def test_api_failure_redaction_and_missing_config(monkeypatch, caplog):
    monkeypatch.setenv("ENABLE_FILE_UPLOADS", "1")
    monkeypatch.setattr(api, "authenticate_owner", lambda c: "github:123")
    monkeypatch.delenv("FILE_UPLOAD_ROOT", raising=False)
    assert unpack(api.cleanup_file_uploads(None))["error"] == "staging_not_configured"
    monkeypatch.setenv("FILE_UPLOAD_ROOT", "/not/a/real/private/root")
    result = api.cleanup_file_uploads(None)
    assert unpack(result)["error"] == "staging_unavailable"
    assert '/not/a/real' not in str(result) + caplog.text


def test_actual_http_dispatch_schema_and_mcp_normalization(monkeypatch, store, caplog):
    from mcp_server import server
    monkeypatch.setenv("ENABLE_FILE_UPLOADS", "1")
    monkeypatch.setenv("FILE_UPLOAD_ROOT", str(store.root))
    tools = [getattr(api, n)._mcp_tool for n in ("begin_file_upload", "append_file_chunk", "finish_file_upload",
              "get_file_upload_status", "cancel_file_upload", "cleanup_file_uploads")]
    from mcp_server.core.registry import ToolRegistry
    reg = ToolRegistry()
    for t in tools: reg.register(t)
    monkeypatch.setattr(server, "registry", reg)
    monkeypatch.setattr(server, "GitHubClient", lambda token: fake_client())
    http = server.app.test_client()
    def call(name, args, auth=True):
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}}
        return http.post("/mcp", json=body, headers={"Authorization": "Bearer synthetic-test-token"} if auth else {}).get_json()
    assert call("cleanup_file_uploads", {}, False)["error"]["code"] == -32001
    listed = http.post("/mcp", json={"jsonrpc":"2.0", "id":2,"method":"tools/list"}).get_json()["result"]["tools"]
    assert len(listed) == 6 and all(server._tool_needs_token(t["name"]) for t in listed)
    raw = bytes(range(256)) * 4
    uid = unpack(call("begin_file_upload", {"name":"safe.bin", "size":len(raw), "sha256":digest(raw), "request_key":secrets.token_hex(32)})["result"])["upload_id"]
    encoded = base64.b64encode(raw).decode()
    res = call("append_file_chunk", {"upload_id":uid, "offset":0, "data":encoded, "chunk_sha256":digest(raw)})
    assert unpack(res["result"])["received"] == len(raw)
    final = unpack(call("finish_file_upload", {"upload_id":uid})["result"])
    with store.verified_chunks("github:123", final["file_id"]) as parts:
        assert b"".join(parts) == raw
    assert encoded not in str(res) + caplog.text and "synthetic-test-token" not in caplog.text
    bad = call("append_file_chunk", {"unexpected":encoded})
    assert bad["error"]["message"] == "Upload request failed"
    assert encoded not in str(bad) + caplog.text


@pytest.mark.parametrize("flag,count", [("0",113), ("1",119)])
def test_fresh_discovery_default_and_upload_only(flag, count):
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, ENABLE_LOCAL_TOOLS="0", ENABLE_LOCAL_SHELL="0", ENABLE_SYNAPSE="0", ENABLE_FILE_UPLOADS=flag)
    code = f'''from mcp_server.server import registry
assert len(registry.get_all()) == {count}
assert bool(registry.get("begin_file_upload")) == {flag == "1"}
assert registry.get("run_command") is None
'''
    subprocess.run([sys.executable, "-c", code], cwd=root, env=env, capture_output=True, text=True, timeout=30, check=True)


@pytest.mark.parametrize("allowlist,error", [("", "allowlist_not_configured"), ("*", "allowlist_not_configured"),
                                            ("123,", "allowlist_not_configured"), ("-1", "allowlist_not_configured"),
                                            ("999", "owner_not_allowed")])
def test_allowlist_fail_closed_without_storage(monkeypatch, store, allowlist, error):
    monkeypatch.setenv("ENABLE_FILE_UPLOADS", "1")
    monkeypatch.setenv("FILE_UPLOAD_ROOT", str(store.root))
    monkeypatch.setenv("FILE_UPLOAD_ALLOWED_USERS", allowlist)
    monkeypatch.setattr(api, "authenticate_owner", lambda c: "github:123")
    assert error in unpack(api.cleanup_file_uploads(None))["error"]
    assert not list(store.root.iterdir())


def test_chunk_count_bounds_and_oversized_decode(store, monkeypatch):
    import mcp_server.core.uploads as module
    uid = begin(store, b"abc")["upload_id"]
    monkeypatch.setattr(module, "MAX_CHUNKS", 2)
    append(store, uid, b"a", 0);append(store, uid, b"b", 1)
    with pytest.raises(UploadError, match="chunk_count_limit"):
        append(store, uid, b"c", 2)
    with pytest.raises(UploadError, match="chunk_size_limit"):
        decode_chunk(base64.b64encode(b"x" * (CHUNK_BYTES+1)).decode(), digest(b"x" * (CHUNK_BYTES+1)))


def test_concurrent_global_quota_not_oversubscribed(store):
    def worker(index):
        try:
            begin(UploadStore(store.root, limits=Limits(total_bytes=6)), owner=f"github:{index+1}")
            return True
        except UploadError as exc:
            assert str(exc) == "quota_exceeded"
            return False
    with ThreadPoolExecutor(8) as pool:
        assert sum(pool.map(worker, range(8))) == 2


def test_transaction_failure_does_not_publish_chunk(store):
    uid = begin(store)["upload_id"]
    # Deterministic SQLite failure after the append insert, before progress update.
    with sqlite3.connect(store.root / "staging.sqlite3") as db:
        db.execute("CREATE TRIGGER fail_update BEFORE UPDATE ON uploads BEGIN SELECT RAISE(ABORT,'synthetic'); END")
    with pytest.raises(sqlite3.DatabaseError):
        append(store, uid)
    with sqlite3.connect(store.root / "staging.sqlite3") as db:
        assert db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 0
        assert db.execute("SELECT received FROM uploads").fetchone()[0] == 0


def test_all_three_forms_through_real_flask_dispatch(monkeypatch, store):
    # Real registration/HTTP/normalization, synthetic authentication transport.
    from mcp_server import server
    from mcp_server.core.registry import ToolRegistry
    reg = ToolRegistry()
    for name in ["begin_file_upload", "append_file_chunk", "finish_file_upload"]:
        reg.register(getattr(api, name)._mcp_tool)
    monkeypatch.setattr(server, "registry", reg)
    monkeypatch.setattr(server, "GitHubClient", lambda token: fake_client())
    monkeypatch.setenv("ENABLE_FILE_UPLOADS", "1")
    monkeypatch.setenv("FILE_UPLOAD_ROOT", str(store.root))
    http = server.app.test_client()
    def call(name, args):
        response = http.post("/mcp", headers={"Authorization":"Bearer synthetic-test-token"}, json={
            "jsonrpc":"2.0", "id":1,"method":"tools/call", "params":{"name":name,"arguments":args}}).get_json()
        assert "error" not in response
        result = unpack(response["result"])
        assert result["ok"] is True
        return result
    for data, name in [(bytes(range(256))*256,"binary.bin"), (archive(),"binary.zip"), (archive(True),"binary.xlsx")]:
        uid = call("begin_file_upload", {"name":name,"size":len(data),"sha256":digest(data),"request_key":secrets.token_hex(32)})["upload_id"]
        for offset in range(0,len(data),CHUNK_BYTES):
            part = data[offset:offset+CHUNK_BYTES]
            call("append_file_chunk", {"upload_id":uid,"offset":offset,"data":base64.b64encode(part).decode(),"chunk_sha256":digest(part)})
        result = call("finish_file_upload", {"upload_id":uid})
        with store.verified_chunks("github:123",result["file_id"]) as chunks:
            assert b"".join(chunks) == data


def test_file_backed_client_helper_preserves_binary_without_stdout(tmp_path):
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts/prepare_file_upload.py"
    raw = bytes(range(256)) * 300
    source = tmp_path / "synthetic.bin";source.write_bytes(raw)
    begin_args = tmp_path / "begin.json"
    result = subprocess.run([sys.executable, str(script), "begin", str(source), str(begin_args)], capture_output=True, text=True, check=True)
    args = json.loads(begin_args.read_text())
    assert args["size"] == len(raw) and args["sha256"] == digest(raw)
    parts = []
    for offset in range(0,len(raw),CHUNK_BYTES):
        output = tmp_path / f"part-{offset}.json"
        result = subprocess.run([sys.executable,str(script),"chunk",str(source),str(output),"--upload-id","a"*64,"--offset",str(offset)], capture_output=True,text=True,check=True)
        payload = json.loads(output.read_text())
        parts.append(base64.b64decode(payload["data"],validate=True))
        assert payload["data"] not in result.stdout + result.stderr
        assert output.stat().st_mode & 0o077 == 0
    assert b"".join(parts) == raw
    # Existing output is refused, not truncated/followed.
    before = begin_args.read_bytes()
    result = subprocess.run([sys.executable,str(script),"begin",str(source),str(begin_args)],capture_output=True,text=True)
    assert result.returncode != 0 and before == begin_args.read_bytes()


@pytest.mark.parametrize("length_header", [True, False])
def test_upload_mode_bounds_body_before_json_or_auth(monkeypatch, length_header):
    from mcp_server import server
    from werkzeug.test import EnvironBuilder
    monkeypatch.setenv("ENABLE_FILE_UPLOADS", "1")
    monkeypatch.setattr(server, "GitHubClient", lambda *args: pytest.fail("No auth for oversized body"))
    raw = b'x' * (1024 * 1024 + 1)
    builder = EnvironBuilder(path="/mcp", method="POST", data=raw, content_type="application/json")
    environ = builder.get_environ()
    if not length_header:
        environ.pop("CONTENT_LENGTH",None)
        environ["wsgi.input_terminated"] = True
    response = server.app.test_client().open(environ)
    assert response.status_code == 413
    assert "x" * 100 not in response.get_data(as_text=True)


@pytest.mark.parametrize("raw", [b'{bad', b'[]', b'null', b'\xff', b'['*1200])
def test_upload_mode_malformed_json_fails_without_trace(monkeypatch, raw):
    from mcp_server import server
    monkeypatch.setenv("ENABLE_FILE_UPLOADS", "1")
    response = server.app.test_client().post("/mcp", data=raw, content_type="application/json")
    assert response.status_code == 400


def test_real_header_to_verified_principal_isolation(monkeypatch, store):
    from mcp_server import server
    from mcp_server.tools.github.client import GitHubClient
    from mcp_server.core.registry import ToolRegistry
    monkeypatch.setenv("ENABLE_FILE_UPLOADS", "1")
    monkeypatch.setenv("FILE_UPLOAD_ROOT",str(store.root))
    monkeypatch.setenv("FILE_UPLOAD_ALLOWED_USERS","11,22")
    checked, clients = [], []
    def response(req):
        assert req.method == "GET" and str(req.url) == "https://api.github.com/user"
        bearer = req.headers["authorization"]
        checked.append(bearer)
        identity = {"Bearer synthetic-a":11, "Bearer synthetic-b":22}.get(bearer)
        return httpx.Response(200,json={"id":identity}) if identity else httpx.Response(401,json={"message":"sensitive detail"})
    def factory(token):
        c = GitHubClient(token)
        c._client.close()
        c._client = httpx.Client(transport=httpx.MockTransport(response))
        clients.append(c)
        return c
    reg = ToolRegistry()
    for name in ["begin_file_upload","get_file_upload_status","cancel_file_upload"]:
        reg.register(getattr(api,name)._mcp_tool)
    monkeypatch.setattr(server,"registry",reg)
    monkeypatch.setattr(server,"GitHubClient",factory)
    http=server.app.test_client()
    def call(name,args,token):
        body=http.post("/mcp",headers={"Authorization":f"Bearer {token}"},json={"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":name,"arguments":args}}).get_json()
        return unpack(body["result"])
    metadata={"name":"synthetic.bin","size":3,"sha256":digest(b"abc"),"request_key":secrets.token_hex(32)}
    assert call("begin_file_upload",metadata,"invalid")["error"] == "authentication_failed"
    assert not list(store.root.iterdir())
    uid=call("begin_file_upload",metadata,"synthetic-a")["upload_id"]
    assert call("get_file_upload_status",{"upload_id":uid},"synthetic-b")["error"] == "not_found_or_expired"
    assert call("cancel_file_upload",{"upload_id":uid},"synthetic-b")["error"] == "not_found_or_expired"
    assert call("get_file_upload_status",{"upload_id":uid},"synthetic-a")["ok"] is True
    assert len(checked)==5 and all(c._client.is_closed for c in clients)
    db=(store.root/"staging.sqlite3").read_bytes()
    assert b"synthetic-a" not in db and b"synthetic-b" not in db


def test_default_mode_keeps_large_legacy_text_call(monkeypatch):
    from mcp_server import server
    monkeypatch.setenv("ENABLE_FILE_UPLOADS","0")
    raw="x"*(1024*1024+1)
    result=server.app.test_client().post("/mcp",json={"jsonrpc":"2.0","id":1,"method":"tools/call",
        "params":{"name":"hash_text","arguments":{"text":raw,"algo":"sha256"}}})
    assert result.status_code==200
    assert digest(raw.encode()) in result.get_json()["result"]["content"][0]["text"]


def test_surrogate_filename_refused_as_stable_code(store):
    with pytest.raises(UploadError,match="invalid_name"):
        begin(store,name="bad\ud800name")
