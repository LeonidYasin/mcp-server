"""Operator-run TEST-only exact-SHA rollout; never imported by the MCP service."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, urlopen

TARGET = '65ddae12bfaf6d117bb8f472ba396016db36610a'
OLD = '20d26756b87f78f28d9c3f5ea8a14b3fd1de36b7'
ROOT = Path('/home/mcp-test/mcp-server')
PYTHON = '/home/mcp-test/venv/bin/python3'
UNIT = 'mcp-test.service'
PROTECTED = ('mcp-server.service', 'caddy.service', 'agora-mcp.service')
ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8'}
CHILD_ENV = ['PATH=/usr/bin:/bin', 'HOME=/home/mcp-test', 'LANG=C.UTF-8',
             'GIT_CONFIG_NOSYSTEM=1', 'GIT_CONFIG_GLOBAL=/dev/null',
             'GIT_TERMINAL_PROMPT=0', 'PYTHONDONTWRITEBYTECODE=1',
             'PYTHONNOUSERSITE=1']


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def properties(unit):
    p = subprocess.run(['/usr/bin/systemctl', 'show', unit, '--no-pager',
                        '--property=Id,LoadState,ActiveState,SubState,MainPID,User,Group,WorkingDirectory,ExecStart'],
                       capture_output=True, text=True, timeout=15, check=True, env=ENV)
    return dict(x.split('=', 1) for x in p.stdout.splitlines() if '=' in x)


def public_props(unit):
    return {k: v for k, v in properties(unit).items() if k != 'ExecStart'}


def child(args, log, timeout=60):
    return subprocess.run(['/usr/sbin/runuser', '-u', 'mcp-test', '--', '/usr/bin/env', '-i',
                           *CHILD_ENV, *map(str, args)], cwd=ROOT, env=ENV,
                          stdout=subprocess.PIPE, stderr=log, timeout=timeout, check=True).stdout


def git(args, log, timeout=60):
    return child(['/usr/bin/git', '-c', 'core.hooksPath=/dev/null', *args], log, timeout)


def health():
    with urlopen('http://127.0.0.1:3002/health', timeout=3) as r:
        require(r.status == 200, 'TEST health HTTP failure')
        return json.loads(r.read(1048576))


def inventory():
    data = json.dumps({'jsonrpc': '2.0', 'id': 'pr112-rollout-schema', 'method': 'tools/list'}).encode()
    req = Request('http://127.0.0.1:3002/mcp', data=data, headers={'Content-Type': 'application/json'})
    with urlopen(req, timeout=5) as r:
        body = json.loads(r.read(1048576))
    require('error' not in body, 'TEST tools/list error')
    return {x['name']: x for x in body['result']['tools']}


def restart(log):
    subprocess.run(['/usr/bin/systemctl', 'restart', UNIT], check=True, env=ENV,
                   stdout=log, stderr=log, timeout=45)


def await_health(sha, names, master_not=None):
    for _ in range(30):
        try:
            p = properties(UNIT)
            h = health()
            reported = h.get('commit', '')
            ok = (p['ActiveState'] == 'active' and p['SubState'] == 'running'
                  and isinstance(reported, str) and len(reported) >= 7 and sha.startswith(reported)
                  and set(h.get('tools', [])) == names)
            if ok and (master_not is None or p['MainPID'] != master_not):
                return h
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError('TEST health/revision/inventory verification failed')


def main():
    require(os.geteuid() == 0, 'Run in the existing root console, not through MCP')
    os.umask(0o077)
    lock = open('/run/lock/mcp-test-pr112-rollout.lock', 'a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    require(ROOT.resolve() == ROOT and (ROOT / '.git').is_dir()
            and not (ROOT / '.git').is_symlink(), 'Unexpected TEST checkout path')
    require(shutil.disk_usage(ROOT).free >= 2 * 1024**3, 'Less than 2 GiB free')
    p = properties(UNIT)
    require(p.get('User') == 'mcp-test' and p.get('Group') == 'mcp-test'
            and p.get('WorkingDirectory') == str(ROOT)
            and p.get('ActiveState') == 'active' and p.get('SubState') == 'running'
            and '/home/mcp-test/venv/bin/gunicorn' in p.get('ExecStart', '')
            and 'mcp_server.server:app' in p.get('ExecStart', ''), 'Unexpected TEST service configuration')
    protected = {u: public_props(u) for u in PROTECTED}
    before = health()
    require(OLD.startswith(before.get('commit', '!')) and len(before.get('commit', '')) >= 7,
            'Unexpected running TEST revision')
    names = set(before['tools'])
    require('find_repository_analogs' in names and len(names) == 120,
            'Unexpected existing TEST inventory; inspect instead of blind rerun')
    backup = Path(tempfile.mkdtemp(prefix='mcp-test-pr112-', dir='/root'))
    changed = False
    with (backup / 'rollout.log').open('wb') as log:
        require(git(['rev-parse', 'HEAD'], log).decode().strip() == OLD, 'TEST HEAD changed')
        require(not git(['status', '--porcelain', '--untracked-files=all'], log).strip(),
                'TEST working tree is not clean; nothing discarded')
        (backup / 'source-before.tar').write_bytes(git(['archive', '--format=tar', OLD], log))
        (backup / 'state-before.json').write_text(json.dumps({
            'old': OLD, 'target': TARGET, 'test': public_props(UNIT), 'protected': protected,
            'tools': sorted(names)}, indent=2))
        print('BACKUP ' + str(backup), flush=True)
        git(['fetch', '--no-tags', 'https://github.com/LeonidYasin/mcp-server.git', TARGET], log)
        require(git(['rev-parse', 'FETCH_HEAD^{commit}'], log).decode().strip() == TARGET,
                'Fetched SHA does not match reviewed target')
        # No pip/install, root execution of repository code, unit edits, or sudo-policy changes.
        child([PYTHON, '-c', 'import flask, flask_cors, httpx, dotenv, gunicorn'], log)
        require(all(public_props(u) == snap for u, snap in protected.items()),
                'Protected service state changed before rollout')
        require(git(['rev-parse', 'HEAD'], log).decode().strip() == OLD
                and not git(['status', '--porcelain', '--untracked-files=all'], log).strip(),
                'TEST changed during preflight')
        try:
            changed = True
            git(['checkout', '--detach', TARGET], log)
            require(git(['rev-parse', 'HEAD'], log).decode().strip() == TARGET, 'Checkout failed')
            restart(log)
            h = await_health(TARGET, names | {'find_repository_analogs'}, p['MainPID'])
            tools = inventory()
            require(set(tools) == names | {'find_repository_analogs'}, 'tools/list inventory mismatch')
            props = tools['find_repository_analogs']['inputSchema']['properties']
            require({'idea', 'queries', 'source_repository', 'max_search_requests', 'start_probe'} <= set(props),
                    'Analog tool schema mismatch')
            require('mode' in tools['get_repo_info']['inputSchema']['properties'], 'Evidence mode missing')
            require(not git(['status', '--porcelain', '--untracked-files=all'], log).strip(),
                    'Unexpected tracked/untracked files after restart')
            require(all(public_props(u) == snap for u, snap in protected.items()),
                    'Protected service state changed during rollout')
            result = {'state': 'TEST_ROLLOUT_PASS', 'target': TARGET, 'previous': OLD,
                      'tools': h['tool_count'], 'backup': str(backup),
                      'protected_services_unchanged': True,
                      'external_four_case_acceptance': 'pending'}
            (backup / 'result.json').write_text(json.dumps(result, indent=2))
            print(json.dumps(result), flush=True)
        except BaseException:
            if changed:
                try:
                    git(['checkout', '--detach', OLD], log)
                    restart(log)
                    await_health(OLD, names)
                    print('TEST_ROLLBACK_PASS; private log: ' + str(backup / 'rollout.log'), flush=True)
                except BaseException:
                    print('TEST_ROLLBACK_FAILED; manual TEST recovery required; backup: ' + str(backup), flush=True)
            raise


if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        # Never dump environment, service ExecStart, private logs or credential-bearing output.
        print('STOP: ' + type(exc).__name__ + ': ' + str(exc)[:600], file=sys.stderr)
        sys.exit(1)
