"""Linux safety regressions and real disposable process lifecycle checks."""
import json
import os
import signal
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mcp_server.tools.process import process_ops as po

pytestmark = pytest.mark.skipif(sys.platform != 'linux', reason='Linux /proc safety')


@pytest.fixture(autouse=True)
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(po, '_root', lambda: tmp_path)
    return tmp_path


def identity(pid=4242):
    return dict(uid=os.geteuid(), pgid=pid, sid=pid,
                boot_id='test-boot', start_ticks='123')


def meta(pid=4242):
    return dict(name='a', pid=pid, identity=identity(pid), cmd=['sleep', '30'],
                started_at='test-time', log_file='/etc/passwd')


@pytest.mark.parametrize('field,value', [
    ('uid', -1), ('pgid', 4243), ('sid', 4243),
    ('boot_id', 'other-boot'), ('start_ticks', '124'),
])
def test_identity_mismatch_never_sends_signal(monkeypatch, field, value):
    po._write_meta('a', meta())
    changed = dict(identity(), **{field: value})
    monkeypatch.setattr(po, '_process_identity', lambda pid: changed)
    monkeypatch.setattr(po, '_is_alive', lambda pid: True)
    kill = MagicMock()
    monkeypatch.setattr(po.os, 'killpg', kill)
    assert 'сигнал НЕ отправлен' in po.stop_process(name='a')
    kill.assert_not_called()


def test_identity_rechecked_immediately_before_signal(monkeypatch):
    po._write_meta('a', meta())
    values = iter([identity(), dict(identity(), start_ticks='124')])
    monkeypatch.setattr(po, '_process_identity', lambda pid: next(values))
    monkeypatch.setattr(po, '_is_alive', lambda pid: True)
    kill = MagicMock()
    monkeypatch.setattr(po.os, 'killpg', kill)
    assert 'сигнал НЕ отправлен' in po.stop_process(name='a')
    kill.assert_not_called()


def test_legacy_metadata_cannot_signal(monkeypatch):
    old = meta()
    old.pop('identity')
    po._write_meta('a', old)
    monkeypatch.setattr(po, '_is_alive', lambda pid: True)
    kill = MagicMock()
    monkeypatch.setattr(po.os, 'killpg', kill)
    assert 'сигнал НЕ отправлен' in po.stop_process(name='a')
    kill.assert_not_called()


@pytest.mark.parametrize('pid', [-1, 0, 1, '4242', True])
def test_invalid_pid_rejected_without_signal(monkeypatch, pid):
    po._write_meta('a', dict(meta(), pid=pid))
    kill = MagicMock()
    monkeypatch.setattr(po.os, 'killpg', kill)
    assert '❌' in po.stop_process(name='a')
    kill.assert_not_called()


def test_log_path_from_metadata_is_ignored(sandbox):
    outside = sandbox.parent / (sandbox.name + '-private')
    outside.write_text('SHOULD-NOT-APPEAR')
    po._write_meta('a', dict(meta(), log_file=str(outside)))
    po._log_path('a').write_text('safe-output\n')
    output = po.tail_log(name='a')
    assert 'safe-output' in output and 'SHOULD-NOT-APPEAR' not in output


@pytest.mark.parametrize('operation', ['tail', 'start'])
def test_log_symlink_rejected(sandbox, operation):
    outside = sandbox.parent / (sandbox.name + '-private')
    outside.write_text('SHOULD-NOT-APPEAR')
    po._log_path('a').symlink_to(outside)
    output = (po.tail_log(name='a') if operation == 'tail'
              else po.start_background(name='a', cmd=[sys.executable, '-c', 'print(1)']))
    assert '❌' in output and 'SHOULD-NOT-APPEAR' not in output
    assert outside.read_text() == 'SHOULD-NOT-APPEAR'


def test_metadata_symlink_rejected(sandbox):
    outside = sandbox.parent / (sandbox.name + '-meta')
    outside.write_text(json.dumps(meta()))
    po._meta_path('a').symlink_to(outside)
    assert '❌' in po.stop_process(name='a')


def test_store_symlink_rejected(sandbox):
    other = sandbox.parent / (sandbox.name + '-other')
    other.mkdir()
    (sandbox / '.mcp_processes').symlink_to(other, target_is_directory=True)
    assert '❌' in po.process_status()
    assert list(other.iterdir()) == []


def test_log_hardlink_rejected(sandbox):
    outside = sandbox.parent / (sandbox.name + '-private')
    outside.write_text('SHOULD-NOT-APPEAR')
    os.link(outside, po._log_path('a'))
    assert '❌' in po.tail_log(name='a')


def test_fifo_log_rejected_without_blocking():
    os.mkfifo(po._log_path('a'))
    assert '❌' in po.tail_log(name='a')


@pytest.mark.parametrize('lines', [-1, 1001, True, '5'])
def test_bad_line_limits_rejected(lines):
    assert '❌' in po.tail_log(name='a', lines=lines)


def test_tail_reads_bounded_utf8_bytes(monkeypatch):
    po._log_path('a').write_text('ёж\n' * 10000)
    monkeypatch.setattr(po, 'MAX_OUTPUT_BYTES', 13)
    output = po.tail_log(name='a', lines=100)
    body = output.split('---\n', 1)[1]
    assert len(body.encode()) <= 13 and '\ufffd' not in body
    assert 'bytes_truncated=true' in output


def test_atomic_metadata_owner_and_permissions():
    po._write_meta('a', meta())
    assert po._load_meta('a')['pid'] == 4242
    assert po._meta_path('a').stat().st_mode & 0o777 == 0o600
    assert po._processes_dir().stat().st_mode & 0o777 == 0o700
    assert list(po._processes_dir().glob('*.tmp')) == []


@pytest.mark.parametrize('env', [{'X': 123}, {'BAD=KEY': 'value'}, {'X': 'bad\x00value'}])
def test_invalid_env_values_not_echoed(env):
    output = po.start_background(name='a', cmd=[sys.executable, '-c', 'pass'], env=env)
    assert '❌' in output and 'bad\x00value' not in output


def test_real_process_start_status_tail_stop():
    output = po.start_background(name='a', cmd=[sys.executable, '-u', '-c',
        'import time; print("process-test-ready", flush=True); time.sleep(10)'])
    assert '✅' in output
    saved = po._load_meta('a')
    try:
        assert saved['identity']['uid'] == os.geteuid()
        assert saved['identity']['pgid'] == saved['pid']
        assert '🟢 a' in po.process_status(name='a')
        # Readiness without an unbounded sleep or process lifetime.
        import time
        for _ in range(100):
            if 'process-test-ready' in po.tail_log(name='a'):
                break
            time.sleep(.01)
        else:
            pytest.fail('child never wrote readiness marker')
        assert 'остановлен' in po.stop_process(name='a', timeout=3)
        assert not po._is_alive(saved['pid'])
        assert not po._meta_path('a').exists()
    finally:
        if po._same_process(saved) and po._is_alive(saved['pid']):
            os.killpg(saved['pid'], signal.SIGKILL)
            po._reap_if_zombie(saved['pid'])


@pytest.mark.parametrize('timeout', [-1, 31, True, '5'])
def test_stop_invalid_timeout_never_signals(monkeypatch, timeout):
    po._write_meta('a', meta())
    monkeypatch.setattr(po, '_process_identity', lambda pid: identity())
    monkeypatch.setattr(po, '_is_alive', lambda pid: True)
    kill = MagicMock()
    monkeypatch.setattr(po.os, 'killpg', kill)
    assert '❌' in po.stop_process(name='a', timeout=timeout)
    kill.assert_not_called()


def _wait_log_marker(name, marker):
    import time
    for _ in range(100):
        output = po.tail_log(name=name)
        if marker in output:
            return output
        time.sleep(.01)
    pytest.fail('child readiness timeout')


def test_real_sigkill_after_sigterm_ignored():
    output = po.start_background(name='a', cmd=[sys.executable, '-u', '-c',
        'import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); '
        'print("ignores-term",flush=True); time.sleep(10)'])
    assert '✅' in output
    saved = po._load_meta('a')
    try:
        _wait_log_marker('a', 'ignores-term')
        assert 'остановлен' in po.stop_process(name='a', force=True, timeout=3)
        assert not po._is_alive(saved['pid'])
    finally:
        if po._same_process(saved) and po._is_alive(saved['pid']):
            os.killpg(saved['pid'], signal.SIGKILL)
            po._reap_if_zombie(saved['pid'])


def test_real_signal_reaches_child_in_same_process_group():
    code = ('import subprocess,sys,time; '
            'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(10)"]); '
            'print("child-pid="+str(p.pid),flush=True); time.sleep(10)')
    assert '✅' in po.start_background(name='a', cmd=[sys.executable, '-u', '-c', code])
    saved = po._load_meta('a')
    try:
        output = _wait_log_marker('a', 'child-pid=')
        child_pid = int(output.split('child-pid=', 1)[1].splitlines()[0])
        assert po._process_identity(child_pid)['pgid'] == saved['pid']
        assert 'остановлен' in po.stop_process(name='a', timeout=3)
        import time
        for _ in range(100):
            if not po._is_alive(child_pid):
                break
            time.sleep(.01)
        assert not po._is_alive(child_pid)
    finally:
        if po._same_process(saved) and po._is_alive(saved['pid']):
            os.killpg(saved['pid'], signal.SIGKILL)
            po._reap_if_zombie(saved['pid'])


def test_metadata_write_failure_cleans_direct_child(monkeypatch):
    real_popen = po.subprocess.Popen
    children = []
    def tracked(*args, **kwargs):
        child = real_popen(*args, **kwargs)
        children.append(child)
        return child
    def fail(*args):
        raise OSError('simulated storage failure')
    monkeypatch.setattr(po.subprocess, 'Popen', tracked)
    monkeypatch.setattr(po, '_write_meta', fail)
    output = po.start_background(name='a', cmd=[sys.executable, '-c',
                                               'import time;time.sleep(10)'])
    assert '❌' in output
    assert len(children) == 1 and children[0].poll() is not None
    assert not po._meta_path('a').exists()


@pytest.mark.parametrize('enabled', ['0', '1'])
def test_runtime_discovery_gate_in_fresh_interpreter(enabled):
    import subprocess
    code = ('from mcp_server.core.registry import ToolRegistry; '
            'r=ToolRegistry();r.discover(); '
            'n={t.name for t in r.get_all()}; '
            'p={"start_background","stop_process","process_status","tail_log"}; '
            f'assert (p <= n) if {enabled!r} == "1" else not (p & n)')
    subprocess.run([sys.executable, '-c', code], check=True,
                   env=dict(os.environ, ENABLE_LOCAL_SHELL=enabled),
                   capture_output=True, timeout=30)


def test_status_does_not_report_reused_pid_as_running(monkeypatch):
    po._write_meta('a', meta())
    monkeypatch.setattr(po, '_is_alive', lambda pid: True)
    monkeypatch.setattr(po, '_process_identity', lambda pid: dict(identity(), start_ticks='124'))
    output = po.process_status(name='a')
    assert '⚠️' in output and 'identity не подтверждена' in output
    assert '🟢' not in output


def test_status_bounds_record_count(monkeypatch):
    for i in range(101):
        po._write_meta(f'p{i}', dict(meta(), name=f'p{i}'))
    monkeypatch.setattr(po, '_is_alive', lambda pid: False)
    output = po.process_status()
    assert output.count('🔴') == 100
    assert 'truncated=true' in output


def test_start_refuses_tracking_over_limit(monkeypatch):
    for i in range(100):
        po._write_meta(f'p{i}', dict(meta(), name=f'p{i}'))
    popen = MagicMock()
    monkeypatch.setattr(po.subprocess, 'Popen', popen)
    assert 'Лимит 100' in po.start_background(name='a', cmd=[sys.executable, '-c', 'pass'])
    popen.assert_not_called()
