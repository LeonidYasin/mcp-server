"""Exercise the orchestrator with fake accounts/commands, never a real install."""
import importlib.util
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace
import pytest

SPEC = importlib.util.spec_from_file_location('upload_deploy_simulation', Path(__file__).resolve().parents[1] / 'scripts/deploy_upload_test.py')
DEPLOY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEPLOY)


@pytest.mark.parametrize('health_fails', [False, True])
def test_root_orchestration_and_rollback_are_confined(monkeypatch, tmp_path, health_fails):
    target = 'b' * 40
    uid, gid = os.geteuid(), os.getegid()
    home = tmp_path / 'new-home'
    audit = tmp_path / 'private-audit'
    audit.mkdir()
    unit = tmp_path / 'new.service'
    for key, value in [('HOME', home), ('REPO', home/'repo'), ('VENV', home/'venv'), ('STAGING', home/'staging'), ('UNIT_FILE', unit)]:
        monkeypatch.setattr(DEPLOY, key, value)
    state = {'account': False}
    calls, sealed = [], []
    def account(name):
        assert name == DEPLOY.USER
        if not state['account']:
            raise KeyError(name)
        return SimpleNamespace(pw_uid=uid, pw_gid=gid)
    def absent_group(name):
        raise KeyError(name)
    def props(name):
        if name == DEPLOY.UNIT:
            return {'LoadState':'loaded' if unit.exists() else 'not-found', 'ActiveState':'active'}
        return {'LoadState':'loaded','ActiveState':'active','MainPID':'123','User':'existing'}
    def command(args, **kwargs):
        calls.append(list(map(str,args)))
        if args[0] == '/usr/sbin/useradd':
            state['account'] = True
            home.mkdir(mode=0o700)
        return subprocess.CompletedProcess(args, 0, stdout=target if 'rev-parse' in args else '')
    def health(sha):
        assert sha == target
        if health_fails:
            raise RuntimeError('synthetic health failure')
    real_open, real_fstat = os.open, os.fstat
    def safe_open(path, *args, **kwargs):
        if path == '/run/mcp-upload-test-setup.lock':
            path = tmp_path / 'lock'
        return real_open(path, *args, **kwargs)
    def fake_stat(fd):
        result = real_fstat(fd)
        return SimpleNamespace(st_mode=result.st_mode, st_uid=0, st_nlink=1)
    monkeypatch.setattr(DEPLOY.os, 'geteuid', lambda:0)
    monkeypatch.setattr(DEPLOY.os, 'umask', lambda mode:0o022)
    monkeypatch.setattr(DEPLOY.os, 'open', safe_open)
    monkeypatch.setattr(DEPLOY.os, 'fstat', fake_stat)
    monkeypatch.setattr(DEPLOY.os, 'chown', lambda *args, **kwargs:None)
    monkeypatch.setattr(DEPLOY.pwd, 'getpwnam', account)
    monkeypatch.setattr(DEPLOY.grp, 'getgrnam', absent_group)
    monkeypatch.setattr(DEPLOY, 'properties', props)
    monkeypatch.setattr(DEPLOY, 'available_port', lambda:None)
    monkeypatch.setattr(DEPLOY.shutil, 'disk_usage', lambda p:SimpleNamespace(free=3*1024**3))
    monkeypatch.setattr(DEPLOY.tempfile, 'mkdtemp', lambda **kwargs:str(audit))
    monkeypatch.setattr(DEPLOY.subprocess, 'run', command)
    monkeypatch.setattr(DEPLOY, 'seal_tree', lambda path:sealed.append(path))
    monkeypatch.setattr(DEPLOY, 'health_gate', health)
    if health_fails:
        with pytest.raises(RuntimeError, match='synthetic health failure'):
            DEPLOY.deploy(target, [11])
    else:
        DEPLOY.deploy(target, [11])
        assert (audit/'after.json').is_file()
    assert unit.is_file() and len(sealed) == 2
    controls = [c for c in calls if c[0] == '/usr/bin/systemctl']
    assert ['/usr/bin/systemctl','start',DEPLOY.UNIT] in controls
    assert ['/usr/bin/systemctl','stop',DEPLOY.UNIT] in controls if health_fails else all('stop' not in c for c in controls)
    assert all('restart' not in c and 'reload' not in c and 'enable' not in c for c in controls)
    assert all(not any(protected in c for protected in DEPLOY.PROTECTED) for c in controls)
    privileged = [c for c in calls if c[0] != '/usr/sbin/runuser']
    assert all('git' not in c[0] and 'python' not in c[0] and 'pip' not in c[0] for c in privileged)
