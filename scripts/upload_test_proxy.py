"""Root-only temporary Caddy route. Never exports keys or edits the Caddyfile.

Clone /test/* only under the SAME exact positive API-key and host guard. CAS via
Caddy root Etag; patch only the containing routes list. Cleanup removes only our
unchanged @id node and preserves concurrent unrelated edits.
"""
import argparse
import copy
import http.client
import json
import os
from pathlib import Path
import re
import secrets
import socket
import ssl
import stat
import subprocess
import time
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import build_opener, HTTPRedirectHandler, ProxyHandler, Request

HOST = "leonid-mcp.duckdns.org"
NEW_PATH = "/upload-test/mcp"
PROTECTED = ("mcp-server.service", "mcp-test.service", "caddy.service", "agora-mcp.service")
TEST_DIALS = {"127.0.0.1:3002", "localhost:3002", "[::1]:3002"}


class ProxyError(Exception):
    pass


def check(ok, code):
    if not ok:
        raise ProxyError(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def nodes(value, parts=()):
    yield value, parts
    if isinstance(value, dict):
        for key, child in value.items():
            yield from nodes(child, parts + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from nodes(child, parts + (index,))


def at(value, parts):
    for part in parts:
        value = value[part]
    return value


def exact_key_guard(node):
    matches = node.get("match")
    if not isinstance(matches, list) or len(matches) != 1 or not isinstance(matches[0], dict):
        return None
    match = matches[0]
    if set(match) != {"header"} or not isinstance(match["header"], dict) or len(match["header"]) != 1:
        return None
    name, values = next(iter(match["header"].items()))
    if name.lower() != "x-api-key" or not isinstance(values, list) or len(values) != 1:
        return None
    key = values[0]
    if not isinstance(key, str) or not key or "*" in key or any(not 33 <= ord(c) <= 126 for c in key):
        return None
    return key


def plan(config, route_id):
    check(isinstance(config, dict), "invalid_config")
    check(re.fullmatch(r"upload-test-91-[a-f0-9]{12}", route_id), "invalid_route_id")
    for node, _ in nodes(config):
        if isinstance(node, dict):
            check(node.get("@id") != route_id, "route_already_present")
            for match in node.get("match", []) if isinstance(node.get("match"), list) else []:
                if isinstance(match, dict):
                    check(not any(isinstance(p, str) and p.startswith("/upload-test") for p in match.get("path", [])), "route_already_present")
    found = []
    for node, parts in nodes(config):
        if not isinstance(node, dict) or node.get("match") != [{"path": ["/test/*"]}]:
            continue
        if not parts or not isinstance(parts[-1], int) or not isinstance(at(config, parts[:-1]), list):
            continue
        ancestors = [at(config, parts[:n]) for n in range(len(parts))]
        keys = [exact_key_guard(a) for a in ancestors if isinstance(a, dict)]
        keys = [key for key in keys if key is not None]
        host_guard = any(isinstance(a, dict) and a.get("match") == [{"host": [HOST]}] for a in ancestors)
        if not keys or not host_guard:
            continue
        proxies = [x for x, _ in nodes(node) if isinstance(x, dict) and x.get("handler") == "reverse_proxy"]
        rewrites = [x for x, _ in nodes(node) if isinstance(x, dict) and x.get("handler") == "rewrite"]
        if len(proxies) != 1 or len(rewrites) != 1:
            continue
        proxy, rewrite = proxies[0], rewrites[0]
        check(set(proxy) <= {"handler", "upstreams", "@id"}, "custom_proxy_policy_requires_review")
        check(isinstance(proxy.get("upstreams"), list) and len(proxy["upstreams"]) == 1
              and set(proxy["upstreams"][0]) == {"dial"} and proxy["upstreams"][0]["dial"] in TEST_DIALS,
              "unexpected_test_upstream")
        check(set(rewrite) <= {"handler", "strip_path_prefix", "@id"}
              and rewrite.get("strip_path_prefix") == "/test", "unexpected_test_rewrite")
        check(all(x.get("handler") in {"subroute", "rewrite", "reverse_proxy"}
                  for x, _ in nodes(node) if isinstance(x, dict) and "handler" in x), "custom_test_handler_requires_review")
        clone = copy.deepcopy(node)
        for x, _ in nodes(clone):
            if isinstance(x, dict):
                x.pop("@id", None)
                if x.get("handler") == "rewrite":
                    x["strip_path_prefix"] = "/upload-test"
                if x.get("handler") == "reverse_proxy":
                    x["upstreams"] = [{"dial": "127.0.0.1:3004"}]
        clone["match"] = [{"path": [NEW_PATH]}]
        clone["@id"] = route_id
        routes = copy.deepcopy(at(config, parts[:-1]))
        routes.insert(parts[-1], clone)
        found.append((parts[:-1], routes, clone, keys[-1]))
    check(len(found) == 1, "unique_protected_test_route_not_found")
    return found[0]


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def admin(method, parts=(), payload=None, etag=None):
    path = "/config/" + "/".join(quote(str(p), safe="") for p in parts)
    headers = {"Content-Type": "application/json"}
    if etag:
        headers["If-Match"] = etag
    body = None if payload is None else canonical(payload).encode()
    request = Request("http://127.0.0.1:2019" + path, data=body, headers=headers, method=method)
    try:
        with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=15) as response:
            raw = response.read(2097153)
            check(len(raw) <= 2097152, "admin_response_limit")
            if method == "GET":
                check(response.headers.get("Etag"), "admin_etag_missing")
                return json.loads(raw), response.headers["Etag"]
            return None
    except HTTPError as exc:
        raise ProxyError("config_changed" if exc.code == 412 else "admin_request_refused") from None
    except ProxyError:
        raise
    except Exception:
        raise ProxyError("admin_unavailable_or_invalid") from None


def private_json(path):
    check(path.is_absolute() and path == path.resolve() and str(path).startswith("/root/"), "unsafe_private_file")
    mode = path.lstat()
    check(stat.S_ISREG(mode.st_mode) and mode.st_uid == 0 and mode.st_nlink == 1
          and not mode.st_mode & 0o077, "unsafe_private_file")
    return json.loads(path.read_text())


def fingerprints():
    result = {}
    for unit in PROTECTED:
        raw = subprocess.check_output(["/usr/bin/systemctl", "show", unit,
                                       "--property=ActiveState,MainPID"], text=True, timeout=10)
        result[unit] = dict(line.split("=", 1) for line in raw.splitlines() if "=" in line)
    check(all(result[u].get("ActiveState") == "active" for u in PROTECTED), "protected_service_not_active")
    return result


class LocalTLS(http.client.HTTPSConnection):
    def connect(self):
        raw = socket.create_connection(("127.0.0.1", 443), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


def probe(path, key=None, method="ping"):
    connection = LocalTLS(HOST, timeout=15, context=ssl.create_default_context())
    headers = {"Host": HOST, "Content-Type": "application/json"}
    if key is not None:
        headers["X-API-Key"] = key
    body = json.dumps({"jsonrpc": "2.0", "id": "upload-proxy-gate", "method": method})
    try:
        connection.request("POST", path, body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read(1048577)
        check(len(raw) <= 1048576, "proxy_response_limit")
        parsed = None
        if response.status == 200:
            try:
                parsed = json.loads(raw)
            except ValueError:
                pass
        return response.status, parsed
    finally:
        connection.close()


def ping_gate(path, key):
    status, body = probe(path, key)
    check(status == 200 and isinstance(body, dict) and body.get("result") == {}, "existing_mcp_ping_failed")


def remove_route(state):
    for attempt in range(3):
        config, etag = admin("GET")
        matches = [(node, parts) for node, parts in nodes(config)
                   if isinstance(node, dict) and node.get("@id") == state["route"]["@id"]]
        if not matches:
            return "not_present"
        check(len(matches) == 1, "cleanup_identity_conflict")
        node, parts = matches[0]
        check(node == state["route"] and parts and isinstance(parts[-1], int), "cleanup_route_changed_requires_review")
        routes = copy.deepcopy(at(config, parts[:-1]))
        check(isinstance(routes, list), "cleanup_parent_changed")
        del routes[parts[-1]]
        try:
            admin("PATCH", parts[:-1], routes, etag)
            after, _ = admin("GET")
            check(not any(isinstance(n, dict) and n.get("@id") == state["route"]["@id"]
                          for n, _ in nodes(after)), "cleanup_readback_failed")
            return "removed"
        except ProxyError as exc:
            if str(exc) != "config_changed" or attempt == 2:
                raise
    raise ProxyError("config_changed")


def apply(snapshot, runtime_sha):
    check(re.fullmatch(r"[a-f0-9]{40}", runtime_sha), "invalid_runtime_sha")
    saved = private_json(snapshot)
    config, etag = admin("GET")
    check(config == saved.get("config"), "config_changed_since_snapshot")
    before = fingerprints()
    with build_opener(ProxyHandler({}), NoRedirect()).open("http://127.0.0.1:3004/health", timeout=5) as response:
        health = json.load(response)
    commit = health.get("commit", "")
    check(isinstance(commit, str) and len(commit) >= 7 and runtime_sha.startswith(commit)
          and health.get("status") == "ok" and health.get("tool_count") == 119, "upload_test_not_ready")
    route_id = "upload-test-91-" + secrets.token_hex(6)
    parts, routes, route, key = plan(config, route_id)
    ping_gate("/mcp", key)
    ping_gate("/test/mcp", key)
    state_path = Path(__file__).resolve().with_name("route-state.json")
    check(not os.path.lexists(state_path), "state_already_exists")
    state = {"route": route, "runtime_sha": runtime_sha, "cleanup_minutes": 45}
    os.umask(0o077)
    with state_path.open("x") as stream:
        json.dump(state, stream)
    state_path.chmod(0o600)
    timer = "mcp-upload-proxy-" + secrets.token_hex(6)
    # Schedule BEFORE the mutation: even a killed operator process leaves a
    # cleanup attempt. The route removal is ID/content/CAS guarded and idempotent.
    scheduled = subprocess.run([
        "/usr/bin/systemd-run", "--quiet", "--collect", "--unit=" + timer,
        "--on-active=45m", "--timer-property=AccuracySec=1s", "--property=UMask=0077",
        "/usr/bin/python3", "-I", str(Path(__file__).resolve()), "remove", "--state", str(state_path),
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
    check(scheduled.returncode == 0, "cleanup_timer_not_scheduled")
    expected = copy.deepcopy(config)
    parent = at(expected, parts)
    parent[:] = routes
    try:
        admin("PATCH", parts, routes, etag)
        after, _ = admin("GET")
        check(after == expected, "unexpected_config_readback")
        for invalid in (None, "synthetic-invalid-key-" + secrets.token_hex(12)):
            status, _ = probe(NEW_PATH, invalid)
            check(status == 401, "unauthorized_route_not_denied")
        status, body = probe(NEW_PATH, key, "tools/list")
        tools = body.get("result", {}).get("tools", []) if isinstance(body, dict) else []
        names = {t.get("name") for t in tools if isinstance(t, dict)}
        required = {"begin_file_upload", "append_file_chunk", "finish_file_upload",
                    "get_file_upload_status", "cancel_file_upload", "cleanup_file_uploads"}
        check(status == 200 and len(tools) == 119 and required <= names, "upload_proxy_schema_failed")
        ping_gate("/mcp", key)
        ping_gate("/test/mcp", key)
        check(fingerprints() == before, "protected_service_fingerprint_changed")
    except BaseException:
        try:
            remove_route(state)
        except Exception:
            print("STOP: cleanup needs operator review; private state retained, timer still scheduled.")
        raise
    print(json.dumps({"result": "PROTECTED UPLOAD ROUTE READY", "endpoint": "https://" + HOST + NEW_PATH,
                      "runtime_sha": runtime_sha, "tools": 119, "missing_or_wrong_key": "401",
                      "old_mcp_pings": "passed", "protected_master_pids_unchanged": True,
                      "caddyfile_changed": False, "auto_cleanup_attempt_minutes": 45,
                      "cleanup_command": "/usr/bin/python3 -I " + str(Path(__file__).resolve()) + " remove --state " + str(state_path),
                      "live_authenticated_upload_gate": False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("apply")
    add.add_argument("--snapshot", type=Path, required=True)
    add.add_argument("--runtime-sha", required=True)
    remove = sub.add_parser("remove")
    remove.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    try:
        check(os.geteuid() == 0, "root_console_required")
        if args.command == "apply":
            apply(args.snapshot, args.runtime_sha)
        else:
            result = remove_route(private_json(args.state))
            print(json.dumps({"result": "UPLOAD ROUTE CLEANUP", "state": result}))
    except Exception as exc:
        # No config, HTTP error body, key, response payload or traceback.
        code = str(exc) if isinstance(exc, ProxyError) else "operation_failed"
        print("STOP: " + code)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
