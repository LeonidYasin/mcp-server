"""Operator-run upgrade of the observed rooms TEST only. Never agent-executed.

Requires the separately downloaded immutable enable_test_agent_rooms.py helper.
No environment/config changes, dependency install, production restart or DB overwrite.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import stat
import tempfile
import time

BASE = 'a323a67f13ecb175a91e8f9726c76c11497483af'
SOURCE = '48a029f2867df399e473dad927dec165d91fa518'
HELPER_BLOB = 'a61d2d133cbd9b74a93ad33ba246173470480379'
HELPER_URL = ('https://raw.githubusercontent.com/LeonidYasin/mcp-server/' + SOURCE +
              '/scripts/enable_test_agent_rooms.py')
EXTRA_DROP = Path('/etc/systemd/system/mcp-test.service.d/99-agent-rooms-storage-115.conf')


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def blob_id(content):
    return hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()


def private_regular(path):
    path = Path(path)
    require(path.is_absolute() and path.resolve() == path, 'Non-canonical operator file.')
    info = path.stat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid() and
            info.st_nlink == 1 and not stat.S_IMODE(info.st_mode) & 0o077,
            'Operator file must be private, owned and single-link.')
    return path


def load_helpers(path):
    path = private_regular(path)
    require(blob_id(path.read_bytes()) == HELPER_BLOB, 'Helper Git blob checksum mismatch.')
    spec = importlib.util.spec_from_file_location('rooms_upgrade_helpers', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def config_fingerprint(h):
    # Only the known non-secret rooms files; no dump of the inherited environment.
    expected = {
        h.ENV_FILE: h.ENV_TEXT,
        h.DROP_FILE: '[Service]\nEnvironmentFile=' + str(h.ENV_FILE) + '\n',
        EXTRA_DROP: '[Service]\nReadWritePaths=' + str(h.DB_DIR) + '\n',
    }
    result = {}
    for path, text in expected.items():
        require(not path.is_symlink() and path.is_file(), 'Expected rooms configuration missing.')
        content = path.read_bytes()
        require(content == text.encode(), 'Rooms configuration changed; review before upgrade.')
        result[str(path)] = hashlib.sha256(content).hexdigest()
    return result


def wait_ready(h, sha, tools):
    for _ in range(30):
        try:
            current = h.health()
            if (set(current['tools']) == set(tools) and
                    sha.startswith(current.get('commit', 'unknown')) and
                    h.prop(h.UNIT, 'ActiveState') == 'active'):
                return current
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError('TEST health did not match the pinned revision/tool baseline.')


def rollback(h, state):
    require(state.get('old') == BASE and state.get('source') == SOURCE and
            re.fullmatch(r'[0-9a-f]{40}', state.get('new', '')), 'Invalid upgrade rollback state.')
    require(config_fingerprint(h) == state['config'], 'Config changed; rollback refused.')
    require(h.git('rev-parse', 'HEAD') in {BASE, state['new']} and
            not h.git('status', '--porcelain', '--untracked-files=normal'),
            'TEST checkout changed; rollback refused.')
    h.command(['systemctl', 'stop', h.UNIT])
    h.git('checkout', '--detach', BASE)
    h.command(['systemctl', 'start', h.UNIT])
    wait_ready(h, BASE, state['tools'])
    h.storage_probe(h.prop(h.UNIT, 'MainPID'))
    print('ROLLBACK PASS: previous TEST code restored; rooms data/config retained.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--helper', required=True)
    parser.add_argument('--rollback')
    args = parser.parse_args(argv)
    require(os.geteuid() == 0, 'Run manually from the operator root console.')
    os.umask(0o077)
    lock = open('/run/lock/mcp-test-agent-rooms-115.lock', 'a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    h = load_helpers(Path(args.helper))
    if args.rollback:
        state_path = private_regular(Path(args.rollback))
        rollback(h, json.loads(state_path.read_text(encoding='utf-8')))
        return
    backup = Path(tempfile.mkdtemp(prefix='mcp-test-rooms-upgrade-', dir='/root'))
    h.LOG = (backup / 'upgrade.log').open('w', encoding='utf-8')
    state, changed = None, False
    try:
        require(h.prop(h.UNIT, 'User') == h.USER and h.prop(h.UNIT, 'Group') == h.USER and
                h.prop(h.UNIT, 'WorkingDirectory') == str(h.REPO) and
                h.prop(h.UNIT, 'ActiveState') == 'active', 'Unexpected TEST service profile.')
        require(h.git('rev-parse', 'HEAD') == BASE and
                not h.git('status', '--porcelain', '--untracked-files=normal'),
                'TEST is not the clean observed a323a67f composite; stop and inspect.')
        config = config_fingerprint(h)
        previous, pid = h.health(), h.prop(h.UNIT, 'MainPID')
        require(BASE.startswith(previous.get('commit', 'unknown')) and
                len(previous['tools']) == 128 and h.ROOMS <= set(previous['tools']),
                'Unexpected TEST health/tool baseline.')
        protected = {unit: h.prop(unit, 'MainPID') for unit in
                     ['mcp-server.service', 'caddy.service', 'agora-mcp.service']}
        require(int(protected['mcp-server.service'] or '0') > 0, 'Production must already be running.')
        h.storage_probe(pid)
        workspace, data = Path('/home/mcp-test/workspace'), Path('/home/mcp-test/data')
        require(all(path.is_dir() and path.resolve() == path for path in (workspace, data)),
                'Expected canonical TEST workspace/data paths missing.')
        free = shutil.disk_usage(data)
        require(free.free >= 256 * 1024 * 1024 and free.free / free.total >= 0.10,
                'Insufficient disk reserve; no rollout.')
        account = pwd.getpwnam(h.USER)
        candidate = Path(tempfile.mkdtemp(prefix='rooms-hardening-', dir=workspace))
        os.chown(candidate, account.pw_uid, account.pw_gid)
        h.git('fetch', '--no-tags', h.REMOTE, SOURCE)
        require(h.git('rev-parse', 'FETCH_HEAD') == SOURCE, 'Source commit mismatch.')
        h.git('worktree', 'add', '--detach', str(candidate), BASE)
        h.git('checkout', SOURCE, '--', *h.PAYLOAD, repo=candidate)
        h.git('-c', 'user.name=TEST room hardening', '-c', 'user.email=test-rollout@localhost',
              'commit', '-m', 'TEST room hardening on a323a67f; source ' + SOURCE, repo=candidate)
        composite = h.git('rev-parse', 'HEAD', repo=candidate)
        changed_paths = set(h.git('diff', '--name-only', BASE, composite, repo=candidate).splitlines())
        require(changed_paths and changed_paths <= set(h.PAYLOAD), 'Upgrade changed unrelated paths.')
        env = {'PATH': '/usr/bin:/bin', 'HOME': '/home/mcp-test', 'LANG': 'C.UTF-8',
               'PYTHONPATH': str(candidate), 'PYTHONNOUSERSITE': '1', 'PYTHONDONTWRITEBYTECODE': '1',
               'ENABLE_LOCAL_TOOLS': '0', 'ENABLE_LOCAL_SHELL': '0', 'ENABLE_SYNAPSE': '0',
               'ENABLE_AGENT_ROOMS': '0', 'GIT_TERMINAL_PROMPT': '0'}
        def as_test(arguments):
            return h.command(['runuser', '-u', h.USER, '--', '/usr/bin/env', '-i',
                              *[key + '=' + value for key, value in env.items()],
                              h.PYTHON, *arguments], cwd=candidate, timeout=300)[0]
        origin = as_test(['-c', 'import mcp_server; from pathlib import Path; print(Path(mcp_server.__file__).resolve().parent.parent)'])
        require(origin.splitlines()[-1] == str(candidate), 'Candidate import origin mismatch.')
        as_test(['-m', 'pytest', '-q'])
        require(not h.git('status', '--porcelain', '--untracked-files=normal', repo=candidate),
                'Validation changed candidate checkout.')
        snapshots = Path(tempfile.mkdtemp(prefix='rooms-upgrade-', dir=data))
        os.chown(snapshots, account.pw_uid, account.pw_gid)
        source_db, snapshot, restored = h.DB_DIR / 'rooms.sqlite3', snapshots / 'snapshot.db', snapshots / 'restore-drill.db'
        first = json.loads(as_test(['-m', 'mcp_server.tools.rooms.maintenance', 'backup', str(source_db), str(snapshot)]))
        second = json.loads(as_test(['-m', 'mcp_server.tools.rooms.maintenance', 'backup', str(snapshot), str(restored)]))
        verified = json.loads(as_test(['-m', 'mcp_server.tools.rooms.maintenance', 'verify', str(restored)]))
        require(first.get('ok') and second.get('ok') and verified.get('ok') and
                first['counts'] == second['counts'] == verified['counts'], 'Snapshot/restore verification failed.')
        require(h.git('rev-parse', 'HEAD') == BASE and
                not h.git('status', '--porcelain', '--untracked-files=normal') and
                config_fingerprint(h) == config and h.prop(h.UNIT, 'MainPID') == pid,
                'TEST changed during preparation; no rollout.')
        require(all(h.prop(unit, 'MainPID') == value for unit, value in protected.items()),
                'Protected service changed during preparation.')
        state = {'old': BASE, 'new': composite, 'source': SOURCE, 'config': config,
                 'tools': previous['tools'], 'protected': protected, 'snapshot': str(snapshot)}
        h.private_write(backup / 'state.json', json.dumps(state, indent=2))
        shutil.copyfile(Path(__file__).resolve(), backup / 'upgrade.py')
        shutil.copyfile(Path(args.helper), backup / 'common.py')
        print('Preflight/tests/snapshot PASS. Private backup: ' + str(backup))
        changed = True
        h.command(['systemctl', 'stop', h.UNIT])
        h.git('checkout', '--detach', composite)
        h.command(['systemctl', 'start', h.UNIT])
        current = wait_ready(h, composite, previous['tools'])
        h.storage_probe(h.prop(h.UNIT, 'MainPID'))
        require(config_fingerprint(h) == config, 'Rooms config changed during rollout.')
        require(all(h.prop(unit, 'MainPID') == value for unit, value in protected.items()),
                'Protected PID changed during rollout; investigate.')
        print(json.dumps({'result': 'TEST ROOMS HARDENING INSTALLED', 'old_sha': BASE,
            'composite_sha': composite, 'source_sha': SOURCE, 'tools': len(current['tools']),
            'config_unchanged': True, 'dependencies_unchanged': True, 'protected_pids_unchanged': True,
            'storage_namespace_probe': True, 'snapshot_restore_integrity': True,
            'live_authenticated_room_gate': False, 'distinct_owner_gate': False,
            'private_backup': str(backup), 'private_snapshot_directory': str(snapshots),
            'rollback_command': '/usr/bin/python3 -I ' + str(backup / 'upgrade.py') +
                ' --helper ' + str(backup / 'common.py') + ' --rollback ' + str(backup / 'state.json')}))
    except Exception as exc:
        print('STOP: ' + (str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__))
        print('Private details: ' + str(backup / 'upgrade.log'))
        if changed and state:
            try:
                rollback(h, state)
            except Exception:
                print('ROLLBACK NOT VERIFIED; inspect TEST manually. Production was not targeted.')
        raise SystemExit(1) from None
    finally:
        h.LOG.close()
        h.LOG = None


if __name__ == '__main__':
    main()
