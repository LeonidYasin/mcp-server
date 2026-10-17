"""Static and helper guards for operator script; never invoke rollout/systemctl/Git."""
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
    assert MODULE.SOURCE == '9f93eb0d1091bf3eca0f60d6be7c6bbe6c45cfc8'
    assert len(MODULE.PAYLOAD) == len(set(MODULE.PAYLOAD)) == 6
    assert all(path.startswith(('mcp_server/tools/rooms/', 'tests/', 'docs/agent-rooms')) for path in MODULE.PAYLOAD)
    assert 'ENABLE_LOCAL_SHELL' not in MODULE.ENV_TEXT
    assert MODULE.DROP_TEXT.startswith('[Service]\nEnvironmentFile=')


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
