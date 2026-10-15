"""Root orchestrator guards, with no root/network/pip/service mutations."""
import importlib.util
from pathlib import Path
import pytest

SPEC = importlib.util.spec_from_file_location('deploy_upload_test', Path(__file__).resolve().parents[1] / 'scripts/deploy_upload_test.py')
DEPLOY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEPLOY)


@pytest.mark.parametrize('sha,users', [('main',[1]),('a'*39,[1]),('A'*40,[1]),('a'*40,[]),('a'*40,[0]),('a'*40,[True]),('a'*40,[-1])])
def test_bad_deployment_identity(sha, users):
    with pytest.raises(RuntimeError):
        DEPLOY.validate(sha, users)


def test_deploy_requires_root_before_side_effect(monkeypatch):
    monkeypatch.setattr(DEPLOY.os, 'geteuid', lambda:123)
    with pytest.raises(RuntimeError, match='root console'):
        DEPLOY.deploy('a'*40, [1])


def test_unit_is_separate_loopback_restricted_and_temporary():
    text = DEPLOY.unit_text('a'*40, [22,11,22])
    assert '--bind 127.0.0.1:3004' in text
    assert 'FILE_UPLOAD_ALLOWED_USERS=11,22' in text
    assert 'ENABLE_FILE_UPLOADS=1' in text
    for flag in ['ENABLE_LOCAL_TOOLS','ENABLE_LOCAL_SHELL','ENABLE_SYNAPSE']:
        assert f'{flag}=0' in text
    assert 'RuntimeMaxSec=7200' in text and 'Restart=no' in text
    assert 'ReadWritePaths=/home/mcp-upload-test/staging' in text
    assert 'NoNewPrivileges=true' in text and 'MemoryMax=256M' in text
    assert '[Install]' not in text
    assert '0.0.0.0' not in text and 'EnvironmentFile=' not in text


def test_unprivileged_commands_drop_parent_credentials(monkeypatch):
    seen = []
    monkeypatch.setenv('FAKE_PARENT_SECRET', 'not-for-child')
    monkeypatch.setattr(DEPLOY.subprocess, 'run', lambda args, **kw:seen.append(args))
    DEPLOY.run_as_user(['/usr/bin/python3','--version'], None)
    args = seen[0]
    assert args[:7] == ['/usr/sbin/runuser','-u','mcp-upload-test','--','/usr/bin/env','-i','PATH=/usr/bin:/bin']
    assert 'PIP_CONFIG_FILE=/dev/null' in args
    assert all('not-for-child' not in arg for arg in args)


def test_dependency_lock_has_only_exact_public_package_versions():
    assert len(DEPLOY.LOCK) == 18
    assert all('==' in item and '/' not in item and '@' not in item for item in DEPLOY.LOCK)
