"""Operator script guards. Commands are mocked; never execute systemctl/Git/nsenter."""
import ast
import importlib.util
from pathlib import Path
import pytest

PATH = Path(__file__).resolve().parents[1] / 'scripts/enable_test_agent_rooms.py'
SPEC = importlib.util.spec_from_file_location('room_rollout_guard', PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_script_is_import_safe_and_payload_is_additive():
    ast.parse(PATH.read_text(encoding='utf-8'))
    assert MODULE.LOG is None
    assert MODULE.UNIT == 'mcp-test.service'
    assert MODULE.OLD == '65ddae12bfaf6d117bb8f472ba396016db36610a'
    assert len(MODULE.SOURCE) == 40 and all(c in '0123456789abcdef' for c in MODULE.SOURCE)
    assert len(MODULE.PAYLOAD) == len(set(MODULE.PAYLOAD)) == 9
    assert all(path.startswith(('mcp_server/tools/rooms/', 'tests/', 'docs/agent-rooms')) for path in MODULE.PAYLOAD)
    assert 'ENABLE_LOCAL_SHELL' not in MODULE.ENV_TEXT
    assert MODULE.DROP_TEXT.splitlines() == ['[Service]', 'EnvironmentFile=' + str(MODULE.ENV_FILE),
                                           'ReadWritePaths=' + str(MODULE.DB_DIR)]
    assert 'ProtectSystem=' not in MODULE.DROP_TEXT and 'ProtectHome=' not in MODULE.DROP_TEXT
    source = PATH.read_text(encoding='utf-8')
    assert source.index("storage_probe(prop(UNIT, 'MainPID'))") < source.index("'result': 'TEST ROOMS REGISTERED'")


def test_private_write_never_overwrites_and_cleanup_requires_exact_own_file(tmp_path):
    path = tmp_path / 'config'
    MODULE.private_write(path, 'ours')
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        MODULE.private_write(path, 'new')
    with pytest.raises(RuntimeError):
        MODULE.remove_owned(path, 'not-ours')
    assert path.read_text() == 'ours'
    MODULE.remove_owned(path, 'ours')
    assert not path.exists()


def test_cleanup_refuses_symlink(tmp_path):
    target = tmp_path / 'target'
    target.write_text('ours')
    link = tmp_path / 'link'
    link.symlink_to(target)
    with pytest.raises(RuntimeError):
        MODULE.remove_owned(link, 'ours')
    assert target.exists()


def test_storage_probe_enters_test_mount_namespace_and_drops_privileges(monkeypatch):
    calls = []
    monkeypatch.setattr(MODULE, 'prop', lambda unit, name: '123')
    monkeypatch.setattr(MODULE.shutil, 'which', lambda name: '/usr/bin/' + name)
    def fake(args, **kwargs):
        calls.append((args, kwargs))
        return 'ROOM_STORAGE_PROBE_PASS', 0
    monkeypatch.setattr(MODULE, 'command', fake)
    MODULE.storage_probe('123')
    args, kwargs = calls[0]
    assert args[:5] == ['/usr/bin/nsenter', '--target', '123', '--mount', '--']
    assert args[5:10] == ['/usr/bin/runuser', '-u', 'mcp-test', '--', '/usr/bin/env']
    assert '-i' in args and 'PYTHONDONTWRITEBYTECODE=1' in args
    assert kwargs['cwd'] == MODULE.REPO and kwargs['timeout'] == 20
    assert 'Bearer' not in str(args) and 'Authorization' not in str(args)
    assert str(MODULE.DB_DIR / 'rooms.sqlite3') in args[-1]
    assert '.list(' in args[-1] and '.send(' not in args[-1]


def test_storage_probe_fails_closed_if_namespace_command_fails(monkeypatch):
    monkeypatch.setattr(MODULE, 'prop', lambda unit, name: '123')
    monkeypatch.setattr(MODULE.shutil, 'which', lambda name: '/usr/bin/' + name)
    def failure(*args, **kwargs):
        raise RuntimeError('mock namespace probe denied')
    monkeypatch.setattr(MODULE, 'command', failure)
    with pytest.raises(RuntimeError, match='mock namespace probe denied'):
        MODULE.storage_probe('123')


def test_storage_probe_rejects_changed_pid_and_missing_success_marker(monkeypatch):
    monkeypatch.setattr(MODULE, 'prop', lambda unit, name: '456')
    with pytest.raises(RuntimeError, match='PID changed'):
        MODULE.storage_probe('123')
    monkeypatch.setattr(MODULE, 'prop', lambda unit, name: '123')
    monkeypatch.setattr(MODULE.shutil, 'which', lambda name: '/usr/bin/' + name)
    monkeypatch.setattr(MODULE, 'command', lambda *args, **kwargs: ('wrong', 0))
    with pytest.raises(RuntimeError, match='storage probe failed'):
        MODULE.storage_probe('123')
