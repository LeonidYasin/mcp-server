"""Operator-only temporary alias of existing TEST, never a new server or DB.

Caddy runtime config only: exact protected-host/header route, optimistic ETag CAS,
private rollback state, independent expiry attempt. No PAT/identity/allowlist change.
"""
import argparse
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler
import uuid

HOST = 'leonid-mcp.duckdns.org'
PREFIX = '/test-rooms-b'
ALIAS = PREFIX + '/mcp'
BASE = 'https://' + HOST
ADMIN = 'http://127.0.0.1:2019'
EXPECTED_TEST = '3c4eb8405c413a49374a17b73c973dbb9aeda9a6'
UNITS = ('mcp-test.service', 'mcp-server.service', 'caddy.service')
CADDYFILE = Path('/etc/caddy/Caddyfile')
MAX_BYTES = 2 * 1024 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = build_opener(ProxyHandler({}), NoRedirect())


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def private_write(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as output:
        output.write(value)
        output.flush(); os.fsync(output.fileno())


def private_state(path):
    require(path.is_absolute() and path.resolve() == path, 'Non-canonical state path.')
    info = path.stat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid() and
            info.st_nlink == 1 and not stat.S_IMODE(info.st_mode) & 0o077,
            'State file must be private and owned.')
    state = json.loads(path.read_text(encoding='utf-8'))
    require(re.fullmatch(r'rooms_test_alias_[0-9a-f]{32}', state.get('id', '')) and
            state.get('route', {}).get('@id') == state['id'] and
            state['route'].get('match') == [{'path': [ALIAS]}], 'Invalid alias state.')
    return state


def request(url, method='GET', payload=None, headers=None):
    values = dict(headers or {})
    body = None
    if payload is not None:
        body = canonical(payload).encode()
        values['Content-Type'] = 'application/json'
    req = Request(url, data=body, method=method, headers=values)
    try:
        with OPENER.open(req, timeout=12) as response:
            content = response.read(MAX_BYTES + 1)
            require(len(content) <= MAX_BYTES, 'Bounded HTTP response exceeded.')
            return response.status, content, response.headers.get('ETag')
    except HTTPError as exc:
        status = exc.code
        exc.close()
        return status, b'', None


def get_config():
    status, raw, etag = request(ADMIN + '/config/')
    require(status == 200 and etag, 'Caddy config/ETag unavailable.')
    return json.loads(raw), etag


def pointer(parts):
    return '/config/' + '/'.join(quote(str(part), safe='') for part in parts)


def walk(value, path=()):
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, path + (index,))


def plan(config, identity):
    require(re.fullmatch(r'rooms_test_alias_[0-9a-f]{32}', identity), 'Invalid alias ID.')
    for path, value in walk(config):
        if isinstance(value, dict):
            require(value.get('@id') != identity, 'Alias ID already exists.')
            patterns = value.get('path', [])
            if isinstance(patterns, list):
                require(not any(isinstance(p, str) and p.startswith(PREFIX) for p in patterns),
                        'Alias path already configured; never overwrite.')
    candidates = []
    servers = config.get('apps', {}).get('http', {}).get('servers', {})
    for name, server in servers.items():
        require(re.fullmatch(r'[A-Za-z0-9_-]+', name), 'Unsupported Caddy server name.')
        for host_index, host_route in enumerate(server.get('routes', [])):
            if host_route.get('match') != [{'host': [HOST]}] or not host_route.get('terminal'):
                continue
            handlers = host_route.get('handle', [])
            if len(handlers) != 1 or handlers[0].get('handler') != 'subroute':
                continue
            for guard_index, guard in enumerate(handlers[0].get('routes', [])):
                matches = guard.get('match', [])
                if len(matches) != 1 or set(matches[0]) != {'header'}:
                    continue
                headers = matches[0]['header']
                if len(headers) != 1 or next(iter(headers)).lower() != 'x-api-key':
                    continue
                values = next(iter(headers.values()))
                require(isinstance(values, list) and len(values) == 1 and
                        isinstance(values[0], str) and len(values[0]) >= 16 and
                        not any(c in values[0] for c in '*\r\n'), 'Non-exact/weak proxy-key guard; stop.')
                children = guard.get('handle', [])
                if len(children) != 1 or children[0].get('handler') != 'subroute':
                    continue
                for index, route in enumerate(children[0].get('routes', [])):
                    if route.get('match') != [{'path': ['/test/*']}]:
                        continue
                    proxies = []
                    for _, node in walk(route):
                        if not isinstance(node, dict):
                            continue
                        require(not any(key.lower() == 'authorization' for key in node),
                                'TEST route overrides Authorization; identity test unsafe.')
                        if 'handler' in node:
                            require(node['handler'] in {'subroute', 'rewrite', 'reverse_proxy'},
                                    'Unsupported handler inside TEST route.')
                        if node.get('handler') == 'reverse_proxy':
                            proxies.append(node)
                    require(len(proxies) == 1 and proxies[0].get('upstreams') in (
                        [{'dial': '127.0.0.1:3002'}], [{'dial': 'localhost:3002'}],
                        [{'dial': '[::1]:3002'}]), 'TEST must have one exact loopback upstream.')
                    parts = ('apps', 'http', 'servers', name, 'routes', host_index,
                             'handle', 0, 'routes', guard_index, 'handle', 0, 'routes', index)
                    alias = {'@id': identity, 'match': [{'path': [ALIAS]}], 'terminal': True,
                             'handle': [{'handler': 'rewrite', 'uri': '/mcp'}, copy.deepcopy(proxies[0])]}
                    candidates.append((parts, alias, values[0]))
    require(len(candidates) == 1, 'Expected exactly one guarded TEST route.')
    return candidates[0]


def without_alias(config, state):
    result = copy.deepcopy(config)
    found = [(path, value) for path, value in walk(result)
             if isinstance(value, dict) and value.get('@id') == state['id']]
    require(len(found) <= 1, 'Duplicate alias IDs; cleanup refused.')
    if not found:
        return result, None
    path, value = found[0]
    require(value == state['route'] and path and isinstance(path[-1], int),
            'Alias changed; cleanup refused rather than deleting foreign config.')
    parent = result
    for part in path[:-1]:
        parent = parent[part]
    del parent[path[-1]]
    return result, path


def remove(state):
    for _ in range(3):
        before, etag = get_config()
        expected, path = without_alias(before, state)
        if path is None:
            return 'absent'
        status, _, _ = request(ADMIN + pointer(path), 'DELETE', headers={'If-Match': etag})
        if status == 412:
            continue
        require(status == 200, 'Scoped alias cleanup request failed.')
        after, _ = get_config()
        _, remaining = without_alias(after, state)
        require(remaining is None, 'Alias cleanup not verified.')
        # Do not restore a whole stale config even if another admin changed it.
        return 'removed'
    raise RuntimeError('Concurrent Caddy changes; cleanup needs another approved attempt.')


def pids():
    result = {}
    for unit in UNITS:
        value = subprocess.check_output(['systemctl', 'show', unit, '-p', 'MainPID', '--value'],
                                        text=True, timeout=10).strip()
        require(value.isdigit() and int(value) > 0, 'Required service is not running.')
        result[unit] = value
    return result


def rpc(path, key=None, method='ping'):
    headers = {'Accept': 'application/json, text/event-stream'}
    if key is not None:
        headers['X-API-Key'] = key
    status, raw, _ = request(BASE + path, 'POST',
        {'jsonrpc': '2.0', 'id': 'rooms-alias-probe', 'method': method}, headers)
    return status, json.loads(raw) if status == 200 else None


def ping(path, key):
    status, payload = rpc(path, key)
    require(status == 200 and payload.get('id') == 'rooms-alias-probe' and
            payload.get('result') == {} and 'error' not in payload, 'Existing/alias MCP ping failed.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['add', 'remove'])
    parser.add_argument('--state')
    args = parser.parse_args(argv)
    require(os.geteuid() == 0, 'Run manually from the operator root console.')
    os.umask(0o077)
    lock = open('/run/lock/mcp-rooms-test-alias.lock', 'a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if args.action == 'remove':
        require(args.state, 'Cleanup requires the private state path.')
        print(json.dumps({'result': 'ROOMS ALIAS CLEANUP', 'state': remove(private_state(Path(args.state)))}))
        return
    require(not args.state, 'Unexpected state argument for add.')
    directory = Path(tempfile.mkdtemp(prefix='mcp-rooms-alias-', dir='/root'))
    state, attempted = None, False
    try:
        before_pids = pids()
        caddyfile = hashlib.sha256(CADDYFILE.read_bytes()).hexdigest()
        status, raw, _ = request('http://127.0.0.1:3002/health')
        require(status == 200, 'Local TEST health unavailable.')
        health = json.loads(raw)
        require(EXPECTED_TEST.startswith(health.get('commit', 'unknown')) and
                isinstance(health.get('tools'), list) and len(health['tools']) == 128,
                'Unexpected TEST source/tool baseline; stop and review.')
        before, etag = get_config()
        identity = 'rooms_test_alias_' + uuid.uuid4().hex
        parts, route, key = plan(before, identity)
        for old_path in ('/mcp', '/test/mcp'):
            ping(old_path, key)
        state = {'id': identity, 'route': route}
        private_write(directory / 'state.json', canonical(state))
        private_write(directory / 'before-config.json', canonical(before))
        private_write(directory / 'alias.py', Path(__file__).resolve().read_text(encoding='utf-8'))
        cleanup = ['/usr/bin/python3', '-I', str(directory / 'alias.py'), 'remove',
                   '--state', str(directory / 'state.json')]
        timer = 'mcp-rooms-alias-' + identity.rsplit('_', 1)[-1]
        result = subprocess.run(['systemd-run', '--quiet', '--collect', '--unit=' + timer,
            '--on-active=90m', '--timer-property=AccuracySec=1s', *cleanup],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20)
        require(result.returncode == 0, 'Cleanup timer setup failed; Caddy was not changed.')
        active = subprocess.run(['systemctl', 'is-active', '--quiet', timer + '.timer'], timeout=10)
        require(active.returncode == 0, 'Cleanup timer not active; Caddy was not changed.')
        attempted = True
        status, _, _ = request(ADMIN + pointer(parts), 'PUT', route, {'If-Match': etag})
        require(status == 200, 'Caddy CAS insert failed; no blind overwrite/retry.')
        after, _ = get_config()
        stripped, location = without_alias(after, state)
        require(location is not None and stripped == before,
                'Caddy differs beyond the alias; cleanup will preserve concurrent changes.')
        for wrong in (None, 'wrong-key-' + uuid.uuid4().hex):
            code, _ = rpc(ALIAS, wrong)
            require(code == 401, 'Alias missing/wrong-key denial failed.')
        ping(ALIAS, key)
        status, listed = rpc(ALIAS, key, 'tools/list')
        require(status == 200 and 'error' not in listed, 'Alias tools/list failed.')
        names = [tool['name'] for tool in listed['result']['tools']]
        require(set(names) == set(health['tools']) and len(names) == 128 and
                len([name for name in names if name.startswith('rooms_')]) == 8,
                'Alias does not expose the exact existing TEST registry.')
        for old_path in ('/mcp', '/test/mcp'):
            ping(old_path, key)
        require(before_pids == pids(), 'Service PID changed; investigate.')
        require(caddyfile == hashlib.sha256(CADDYFILE.read_bytes()).hexdigest(),
                'Caddyfile changed concurrently; investigate.')
        print(json.dumps({'result': 'PROTECTED ROOMS ALIAS READY', 'endpoint': BASE + ALIAS,
            'runtime_sha': EXPECTED_TEST, 'tools': len(names), 'room_tools': 8,
            'missing_or_wrong_key': '401', 'old_mcp_pings': 'passed',
            'protected_pids_unchanged': True, 'caddyfile_changed': False,
            'same_test_process_and_database': True, 'allowlist_changed': False,
            'authenticated_github_owner_gate': False, 'auto_cleanup_attempt_minutes': 90,
            'private_state': str(directory / 'state.json'), 'cleanup_command': ' '.join(cleanup)}))
    except Exception as exc:
        print('STOP: ' + (str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__))
        if attempted and state:
            try:
                print('Scoped cleanup: ' + remove(state))
            except Exception:
                print('CLEANUP NOT VERIFIED. Private state: ' + str(directory / 'state.json'))
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
