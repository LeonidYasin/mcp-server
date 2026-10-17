"""Operator-run root rollout for ONE observed TEST revision; never production.

Not executed by the agent. Builds a local composite from existing TEST + only
reviewed room files, validates before downtime, preserves dependencies/config.
"""
import fcntl
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

UNIT = 'mcp-test.service'
USER = 'mcp-test'
REPO = Path('/home/mcp-test/mcp-server')
PYTHON = Path('/home/mcp-test/venv/bin/python')
OLD = '65ddae12bfaf6d117bb8f472ba396016db36610a'
SOURCE = 'a7b3cb6619f66c706fecf924cf831d6174f44e71'
REMOTE = 'https://github.com/LeonidYasin/mcp-server.git'
DB_DIR = Path('/home/mcp-test/agent-rooms-115')
ENV_FILE = Path('/etc/mcp-test-agent-rooms-115.env')
DROP_DIR = Path('/etc/systemd/system/mcp-test.service.d')
DROP_FILE = DROP_DIR / '99-agent-rooms-115.conf'
ENV_TEXT = ('ENABLE_AGENT_ROOMS=1\nAGENT_ROOMS_DB=' + str(DB_DIR / 'rooms.sqlite3') +
            '\nROOMS_ALLOWED_GITHUB_USERS=79429232\n')
DROP_TEXT = ('[Service]\nEnvironmentFile=' + str(ENV_FILE) +
             '\nReadWritePaths=' + str(DB_DIR) + '\n')
PAYLOAD = ['mcp_server/tools/rooms/__init__.py', 'mcp_server/tools/rooms/store.py',
           'mcp_server/tools/rooms/ops.py', 'tests/test_agent_rooms.py',
           'docs/agent-rooms.md', 'docs/agent-rooms-two-chats.md',
           'mcp_server/tools/rooms/maintenance.py', 'tests/test_agent_rooms_production.py',
           'docs/agent-rooms-production.md']
ROOMS = {'rooms_create', 'rooms_list', 'rooms_join', 'rooms_leave', 'rooms_read',
         'rooms_send', 'rooms_delete_message', 'rooms_close'}
LOG = None


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def command(args, cwd=None, env=None, timeout=60, check=True):
    result = subprocess.run([str(x) for x in args], cwd=cwd, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, timeout=timeout)
    if LOG:
        LOG.write(result.stdout); LOG.flush()
    if check and result.returncode:
        raise RuntimeError('Command failed; details in private rollout log.')
    return result.stdout.strip(), result.returncode


def git(*args, repo=REPO, check=True):
    return command(['runuser', '-u', USER, '--', 'git', '--no-optional-locks',
                    '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false',
                    '-C', repo, *args], check=check)[0]


def prop(unit, name):
    return command(['systemctl', 'show', unit, '-p', name, '--value'])[0]


def health():
    with urlopen('http://127.0.0.1:3002/health', timeout=3) as response:
        data = json.load(response)
    require(isinstance(data.get('tools'), list) and all(isinstance(x, str) for x in data['tools']),
            'Unexpected TEST health format.')
    return data


def storage_probe(pid):
    """Check SQLite inside the running TEST mount namespace, not merely as its UID.

    No tokens, room messages or HTTP calls. Root enters only the mount namespace;
    the probe itself runs as mcp-test with an empty environment and fixed code.
    This is NOT the live authenticated MCP acceptance gate.
    """
    require(pid.isdigit() and int(pid) > 0 and prop(UNIT, 'MainPID') == pid,
            'TEST PID changed before storage probe.')
    nsenter, runuser = shutil.which('nsenter'), shutil.which('runuser')
    require(nsenter and runuser, 'nsenter/runuser required for service storage probe.')
    code = ('from mcp_server.tools.rooms.store import RoomStore; '
            'RoomStore(' + repr(str(DB_DIR / 'rooms.sqlite3')) + ').list("github:79429232"); '
            'print("ROOM_STORAGE_PROBE_PASS")')
    output = command([nsenter, '--target', pid, '--mount', '--', runuser, '-u', USER,
                      '--', '/usr/bin/env', '-i', 'HOME=/home/mcp-test',
                      'PATH=/usr/bin:/bin', 'LANG=C.UTF-8', 'PYTHONDONTWRITEBYTECODE=1',
                      'PYTHONPATH=' + str(REPO), PYTHON, '-c', code], cwd=REPO, timeout=20)[0]
    require(output.splitlines()[-1:] == ['ROOM_STORAGE_PROBE_PASS'] and
            prop(UNIT, 'MainPID') == pid, 'TEST storage probe failed or PID changed.')


def private_write(path, text):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as output:
        output.write(text)


def remove_owned(path, expected):
    if path.exists():
        require(not path.is_symlink() and path.read_text(encoding='utf-8') == expected,
                'Own rollout file changed; automatic removal refused.')
        path.unlink()


def rollback(state):
    require(state.get('old') == OLD and re.fullmatch(r'[0-9a-f]{40}', state.get('new', '')),
            'Invalid rollback state.')
    require(git('rev-parse', 'HEAD') in {OLD, state['new']}, 'TEST HEAD changed concurrently; rollback refused.')
    require(not git('status', '--porcelain', '--untracked-files=normal'), 'TEST became dirty; rollback refused.')
    # Check these files before stopping; never delete other drop-ins/configuration.
    for path, text in [(ENV_FILE, ENV_TEXT), (DROP_FILE, DROP_TEXT)]:
        if path.exists():
            require(not path.is_symlink() and path.read_text(encoding='utf-8') == text,
                    'Rollout configuration changed; rollback refused.')
    command(['systemctl', 'stop', UNIT])
    git('checkout', '--detach', OLD)
    remove_owned(DROP_FILE, DROP_TEXT)
    remove_owned(ENV_FILE, ENV_TEXT)
    command(['systemctl', 'daemon-reload'])
    command(['systemctl', 'start', UNIT])
    for _ in range(30):
        try:
            data = health()
            if set(data['tools']) == set(state['tools']) and OLD.startswith(data.get('commit', 'unknown')):
                require(prop(UNIT, 'ActiveState') == 'active', 'Rollback service not active.')
                print('ROLLBACK PASS: previous TEST restored; rooms DB retained.')
                return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError('Rollback verification failed; inspect private log and TEST service.')


def main():
    global LOG
    require(os.geteuid() == 0, 'Run only from the operator root console.')
    lock = open('/run/lock/mcp-test-agent-rooms-115.lock', 'a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if len(sys.argv) == 3 and sys.argv[1] == '--rollback':
        state = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
        rollback(state)
        return
    require(len(sys.argv) == 1, 'Unexpected arguments.')
    os.umask(0o077)
    backup = Path(tempfile.mkdtemp(prefix='mcp-test-rooms-115-', dir='/root'))
    LOG = (backup / 'rollout.log').open('w', encoding='utf-8')
    state = None
    changed = False
    try:
        require(prop(UNIT, 'LoadState') == 'loaded' and prop(UNIT, 'ActiveState') == 'active', 'TEST must be active.')
        require(prop(UNIT, 'User') == USER and prop(UNIT, 'Group') == USER and
                prop(UNIT, 'WorkingDirectory') == str(REPO), 'Unexpected TEST user/group/working directory.')
        old_pid = prop(UNIT, 'MainPID')
        require(old_pid.isdigit() and int(old_pid) > 0, 'Missing TEST PID.')
        require(git('rev-parse', 'HEAD') == OLD, 'TEST SHA changed; stop and inspect.')
        require(not git('status', '--porcelain', '--untracked-files=normal'), 'TEST checkout is not clean.')
        require(PYTHON.is_file(), 'Expected TEST venv not found.')
        require(not DB_DIR.exists() and not DB_DIR.is_symlink(), 'Rooms data path already exists; never overwrite it.')
        require(not ENV_FILE.exists() and not ENV_FILE.is_symlink() and
                not DROP_FILE.exists() and not DROP_FILE.is_symlink(), 'Rollout config already exists; stop.')
        require(not DROP_DIR.is_symlink(), 'Unexpected symlink in drop-in path.')
        protected = {unit: prop(unit, 'MainPID') for unit in
                     ['mcp-server.service', 'caddy.service', 'agora-mcp.service']}
        require(int(protected['mcp-server.service'] or '0') > 0, 'Production must already be running.')
        previous = health()
        require(OLD.startswith(previous.get('commit', 'unknown')) and not (set(previous['tools']) & ROOMS),
                'Health does not match observed TEST base, or rooms already present.')
        require(not git('ls-tree', '-r', '--name-only', OLD, '--', *PAYLOAD),
                'Room payload paths already exist in TEST; do not overlay blindly.')
        account = pwd.getpwnam(USER)
        workspace = Path('/home/mcp-test/workspace')
        require(workspace.is_dir() and not workspace.is_symlink(), 'Expected TEST workspace directory missing.')
        candidate = Path(tempfile.mkdtemp(prefix='rooms-115-', dir=workspace))
        os.chown(candidate, account.pw_uid, account.pw_gid)
        # Exact immutable source; no dependency installation or default-branch merge.
        git('fetch', '--no-tags', REMOTE, SOURCE)
        require(git('rev-parse', 'FETCH_HEAD') == SOURCE, 'Source commit mismatch.')
        git('worktree', 'add', '--detach', str(candidate), OLD)
        git('checkout', SOURCE, '--', *PAYLOAD, repo=candidate)
        git('-c', 'user.name=TEST room rollout', '-c', 'user.email=test-rollout@localhost',
            'commit', '-m', 'TEST-only room overlay on observed 65ddae12; source 9f93eb0d', repo=candidate)
        composite = git('rev-parse', 'HEAD', repo=candidate)
        require(sorted(git('diff', '--name-only', OLD, composite, repo=candidate).splitlines()) == sorted(PAYLOAD),
                'Composite changes more than the room payload.')
        env = {'PATH': '/usr/bin:/bin', 'HOME': '/home/mcp-test', 'LANG': 'C.UTF-8',
               'PYTHONPATH': str(candidate), 'PYTHONNOUSERSITE': '1', 'PYTHONDONTWRITEBYTECODE': '1',
               'ENABLE_LOCAL_TOOLS': '0', 'ENABLE_LOCAL_SHELL': '0', 'ENABLE_SYNAPSE': '0',
               'ENABLE_AGENT_ROOMS': '0', 'GIT_TERMINAL_PROMPT': '0'}
        def as_test(code_args, extra=None):
            values = dict(env, **(extra or {}))
            return command(['runuser', '-u', USER, '--', '/usr/bin/env', '-i',
                            *[key + '=' + value for key, value in values.items()],
                            PYTHON, *code_args], cwd=candidate, timeout=300)[0]
        origin = as_test(['-c', 'import mcp_server; from pathlib import Path; print(Path(mcp_server.__file__).resolve().parent.parent)'])
        require(origin.splitlines()[-1] == str(candidate), 'venv imports a different source tree.')
        as_test(['-m', 'pytest', '-q'])
        probe = ('import json; from mcp_server.server import registry; '
                 'print(json.dumps(sorted(t.name for t in registry.get_all() if t.name.startswith("rooms_"))))')
        require(set(json.loads(as_test(['-c', probe], {'ENABLE_AGENT_ROOMS': '1'}).splitlines()[-1])) == ROOMS,
                'Room discovery failed in composite candidate.')
        require(not git('status', '--porcelain', '--untracked-files=normal', repo=candidate), 'Validation changed candidate files.')
        require(git('rev-parse', 'HEAD') == OLD and not git('status', '--porcelain', '--untracked-files=normal') and
                prop(UNIT, 'MainPID') == old_pid, 'TEST changed during preparation; no rollout.')
        require(all(prop(unit, 'MainPID') == pid for unit, pid in protected.items()), 'Protected service changed during preparation.')
        state = {'old': OLD, 'new': composite, 'source': SOURCE, 'tools': previous['tools'],
                 'protected': protected, 'candidate': str(candidate)}
        private_write(backup / 'state.json', json.dumps(state, ensure_ascii=False, indent=2))
        shutil.copyfile(Path(__file__).resolve(), backup / 'rollout.py')
        os.chmod(backup / 'rollout.py', 0o600)
        # Data path is fresh; future reruns stop rather than modifying an existing DB.
        DB_DIR.mkdir(mode=0o700)
        os.chown(DB_DIR, account.pw_uid, account.pw_gid)
        as_test(['-c', 'from mcp_server.tools.rooms.store import RoomStore; RoomStore(' + repr(str(DB_DIR / 'rooms.sqlite3')) + ')'])
        print('Preflight/tests PASS. Private state and log: ' + str(backup))
        changed = True
        command(['systemctl', 'stop', UNIT])
        git('checkout', '--detach', composite)
        DROP_DIR.mkdir(mode=0o755, parents=True, exist_ok=True)
        private_write(ENV_FILE, ENV_TEXT)
        private_write(DROP_FILE, DROP_TEXT)
        command(['systemctl', 'daemon-reload'])
        command(['systemctl', 'start', UNIT])
        expected = set(previous['tools']) | ROOMS
        ready = False
        for _ in range(30):
            try:
                current = health()
                if set(current['tools']) == expected and composite.startswith(current.get('commit', 'unknown')):
                    ready = True; break
            except Exception:
                pass
            time.sleep(1)
        require(ready and prop(UNIT, 'ActiveState') == 'active', 'New TEST health failed.')
        storage_probe(prop(UNIT, 'MainPID'))
        require(all(prop(unit, 'MainPID') == pid for unit, pid in protected.items()), 'Protected PID changed; investigate.')
        print(json.dumps({'result': 'TEST ROOMS REGISTERED', 'old_sha': OLD, 'composite_sha': composite,
            'rooms_source_sha': SOURCE, 'tools_before': len(previous['tools']), 'tools_after': len(current['tools']),
            'room_tools': 8, 'allowed_github_users': [79429232], 'production_pids_unchanged': True,
            'dependencies_changed': False, 'caddy_changed': False, 'live_authenticated_room_gate': False,
            'private_backup': str(backup), 'rollback_command': '/usr/bin/python3 -I ' + str(backup / 'rollout.py') +
            ' --rollback ' + str(backup / 'state.json')}, ensure_ascii=False))
    except Exception as exc:
        reason = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
        print('STOP: ' + reason)
        print('Details retained in private log: ' + str(backup / 'rollout.log'))
        if changed and state:
            try:
                rollback(state)
            except Exception:
                print('ROLLBACK NOT VERIFIED. Inspect TEST manually; do not change production.')
        raise SystemExit(1) from None
    finally:
        if LOG:
            LOG.close()


if __name__ == '__main__':
    main()
