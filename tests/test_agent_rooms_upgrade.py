"""No VPS commands: import/pinning/configuration guard unit tests only."""
import ast
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import pytest

PATH = Path(__file__).resolve().parents[1] / 'scripts/upgrade_test_agent_rooms.py'
SPEC = importlib.util.spec_from_file_location('rooms_upgrade_test_module', PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_import_safe_and_exact_observed_base():
    ast.parse(PATH.read_text(encoding='utf-8'))
    assert MODULE.BASE == 'a323a67f13ecb175a91e8f9726c76c11497483af'
    assert MODULE.SOURCE == '48a029f2867df399e473dad927dec165d91fa518'
    assert MODULE.HELPER_BLOB == 'a61d2d133cbd9b74a93ad33ba246173470480379'
    source = PATH.read_text(encoding='utf-8')
    assert 'pip install' not in source and 'daemon-reload' not in source
    assert source.index("'snapshot': str(snapshot)") < source.index('changed = True')
    assert "'live_authenticated_room_gate': False" in source


def test_private_helper_requires_exact_blob_before_import(tmp_path, monkeypatch):
    helper = tmp_path / 'helper.py'
    helper.write_text('MARKER = 1\n'); helper.chmod(0o600)
    with pytest.raises(RuntimeError, match='checksum mismatch'):
        MODULE.load_helpers(helper)
    monkeypatch.setattr(MODULE, 'HELPER_BLOB', MODULE.blob_id(helper.read_bytes()))
    assert MODULE.load_helpers(helper).MARKER == 1
    helper.chmod(0o644)
    with pytest.raises(RuntimeError, match='private'):
        MODULE.load_helpers(helper)


def test_operator_file_rejects_symlink_and_hardlink(tmp_path):
    target = tmp_path / 'target'; target.write_text('x'); target.chmod(0o600)
    alias = tmp_path / 'alias'; alias.symlink_to(target)
    with pytest.raises(RuntimeError, match='Non-canonical'):
        MODULE.private_regular(alias)
    os.link(target, tmp_path / 'hardlink')
    with pytest.raises(RuntimeError, match='single-link'):
        MODULE.private_regular(target)


def test_configuration_must_match_known_existing_room_files(tmp_path, monkeypatch):
    env, drop, extra = [tmp_path / name for name in ('env', 'drop', 'extra')]
    fake = SimpleNamespace(ENV_FILE=env, ENV_TEXT='ENABLE_AGENT_ROOMS=1\n',
                           DROP_FILE=drop, DB_DIR=tmp_path / 'db')
    env.write_text(fake.ENV_TEXT)
    drop.write_text('[Service]\nEnvironmentFile=' + str(env) + '\n')
    extra.write_text('[Service]\nReadWritePaths=' + str(fake.DB_DIR) + '\n')
    monkeypatch.setattr(MODULE, 'EXTRA_DROP', extra)
    original = MODULE.config_fingerprint(fake)
    assert len(original) == 3
    env.write_text('different')
    with pytest.raises(RuntimeError, match='configuration changed'):
        MODULE.config_fingerprint(fake)


def test_rollback_rejects_wrong_revision_before_commands():
    with pytest.raises(RuntimeError, match='Invalid upgrade rollback state'):
        MODULE.rollback(None, {'old': 'bad'})
