"""Тесты process_ops: start_background, stop_process, process_status, tail_log.

Ключевая мотивация этих тестов — не только happy path, но и то, что
всплыло при ручной проверке на реальных процессах и намеренно
регрессионно закреплено здесь:

1. `_is_alive` не должен путать зомби с живым процессом (SIGKILL не
   мгновенен + процесс не reaped, пока родитель не wait()'нет) —
   иначе stop_process всегда "не удавалось остановить".
2. `stop_process` шлёт сигнал ГРУППЕ (`os.killpg`), не одному pid —
   иначе `bash -c "...; sleep N"` может не среагировать на SIGTERM,
   потому что bash откладывает обработку trap до возврата из
   синхронного форграунд-child.

Реальные процессы (sleep/bash) здесь не поднимаются — только моки на
уровне subprocess.Popen / os.killpg / _is_alive, чтобы тесты были
быстрыми и не зависели от таймингов ОС.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from mcp_server.tools.process import process_ops as po


@pytest.fixture(autouse=True)
def sandbox_root(tmp_path, monkeypatch):
    """Каждый тест — в своём чистом LOCAL_TOOLS_ROOT."""
    monkeypatch.setattr(po, "_root", lambda: tmp_path)
    return tmp_path


def _fake_popen(pid=4242):
    proc = MagicMock()
    proc.pid = pid
    return proc


# --------------------------------------------------------------------
# start_background: validation before we ever touch subprocess.Popen
# --------------------------------------------------------------------

def test_start_background_rejects_denylisted_command():
    result = po.start_background(name="a", cmd=["sudo", "rm", "-rf", "/"])
    assert "❌" in result and "deny-list" in result


def test_start_background_rejects_invalid_name():
    result = po.start_background(name="bad name!", cmd=["sleep", "1"])
    assert "❌" in result


def test_start_background_rejects_missing_binary():
    with patch.object(po.shutil, "which", return_value=None):
        result = po.start_background(name="a", cmd=["no-such-binary-xyz"])
    assert "❌" in result and "PATH" in result


def test_start_background_refuses_duplicate_when_alive(sandbox_root):
    meta = {
        "name": "a", "pid": 111, "cmd": ["sleep", "5"],
        "cwd": str(sandbox_root), "log_file": str(sandbox_root / "a.log"),
        "started_at": "2026-01-01T00:00:00+00:00",
    }
    po._meta_path("a").parent.mkdir(parents=True, exist_ok=True)
    po._meta_path("a").write_text(json.dumps(meta))

    with patch.object(po, "_is_alive", return_value=True):
        result = po.start_background(name="a", cmd=["sleep", "5"])
    assert "уже запущен" in result


# --------------------------------------------------------------------
# start_background: happy path (subprocess.Popen mocked)
# --------------------------------------------------------------------

def test_start_background_writes_metadata_and_uses_expected_popen_args(sandbox_root):
    fake_proc = _fake_popen(pid=555)
    with patch.object(po.shutil, "which", return_value="/bin/sleep"), \
         patch.object(po.subprocess, "Popen", return_value=fake_proc) as popen:
        result = po.start_background(
            name="my-app", cmd=["sleep", "30"], cwd=".", env={"FOO": "bar"}
        )

    assert "✅" in result and "555" in result

    args, kwargs = popen.call_args
    assert args[0] == ["sleep", "30"]
    assert kwargs["shell"] is False
    assert kwargs["start_new_session"] is True  # detach — must survive this call
    assert kwargs["env"]["FOO"] == "bar"

    meta = json.loads(po._meta_path("my-app").read_text())
    assert meta["pid"] == 555
    assert meta["cmd"] == ["sleep", "30"]


def test_start_background_accepts_string_command(sandbox_root):
    fake_proc = _fake_popen(pid=556)
    with patch.object(po.shutil, "which", return_value="/bin/sleep"), \
         patch.object(po.subprocess, "Popen", return_value=fake_proc) as popen:
        po.start_background(name="my-app2", cmd="sleep 30")

    args, _ = popen.call_args
    assert args[0] == ["sleep", "30"]  # shlex-split, not passed as a raw string


def test_start_background_cwd_confined_to_root(sandbox_root):
    result = po.start_background(name="a", cmd=["sleep", "1"], cwd="/etc")
    assert "❌" in result


# --------------------------------------------------------------------
# stop_process
# --------------------------------------------------------------------

def _write_meta(root, name, pid):
    po._processes_dir().mkdir(parents=True, exist_ok=True)
    meta = {
        "name": name, "pid": pid, "cmd": ["sleep", "30"],
        "cwd": str(root), "log_file": str(po._log_path(name)),
        "started_at": "2026-01-01T00:00:00+00:00",
    }
    po._meta_path(name).write_text(json.dumps(meta))


def test_stop_process_not_found():
    result = po.stop_process(name="ghost")
    assert "❌" in result and "не найден" in result


def test_stop_process_already_dead_cleans_meta(sandbox_root):
    _write_meta(sandbox_root, "a", 999)
    with patch.object(po, "_is_alive", return_value=False):
        result = po.stop_process(name="a")
    assert "уже не выполняется" in result
    assert not po._meta_path("a").exists()


def _alive_then_dead():
    """Side-effect: True on the first call (pre-signal check), False after."""
    calls = {"n": 0}

    def _side_effect(pid):
        calls["n"] += 1
        return calls["n"] == 1

    return _side_effect


def test_stop_process_sends_signal_to_process_group_not_just_pid(sandbox_root):
    """Regression: must be killpg(pid, ...), not kill(pid, ...) — see module docstring."""
    _write_meta(sandbox_root, "a", 777)
    with patch.object(po, "_is_alive", side_effect=_alive_then_dead()), \
         patch.object(po.os, "killpg") as killpg, \
         patch.object(po.os, "kill") as kill:
        result = po.stop_process(name="a")

    assert "остановлен" in result
    killpg.assert_called_once()
    assert killpg.call_args[0][0] == 777
    kill.assert_not_called()  # must not fall back to signaling just the one pid


def test_stop_process_force_uses_sigkill(sandbox_root):
    import signal as sig
    _write_meta(sandbox_root, "a", 778)
    with patch.object(po, "_is_alive", side_effect=_alive_then_dead()), \
         patch.object(po.os, "killpg") as killpg:
        po.stop_process(name="a", force=True)
    assert killpg.call_args[0][1] == sig.SIGKILL


def test_stop_process_reports_timeout_without_force(sandbox_root):
    _write_meta(sandbox_root, "a", 779)
    with patch.object(po, "_is_alive", return_value=True), \
         patch.object(po.os, "killpg"), \
         patch.object(po.time, "sleep"):  # don't actually wait DEFAULT_STOP_TIMEOUT seconds
        result = po.stop_process(name="a", timeout=1)
    assert "не завершился" in result
    assert po._meta_path("a").exists()  # still tracked — it's still running


# --------------------------------------------------------------------
# process_status / tail_log
# --------------------------------------------------------------------

def test_process_status_empty():
    assert "Нет отслеживаемых" in po.process_status()


def test_process_status_lists_alive_and_dead(sandbox_root):
    _write_meta(sandbox_root, "alive-one", 1)
    _write_meta(sandbox_root, "dead-one", 2)
    with patch.object(po, "_is_alive", side_effect=lambda pid: pid == 1):
        result = po.process_status()
    assert "🟢 alive-one" in result
    assert "🔴 dead-one" in result


def test_process_status_unknown_name():
    result = po.process_status(name="nope")
    assert "❌" in result


def test_tail_log_returns_last_n_lines(sandbox_root):
    po._processes_dir().mkdir(parents=True, exist_ok=True)
    log = po._log_path("a")
    log.write_text("\n".join(f"line{i}" for i in range(1, 11)) + "\n")
    _write_meta(sandbox_root, "a", 123)

    result = po.tail_log(name="a", lines=3)
    assert "line8" in result and "line9" in result and "line10" in result
    assert "line7" not in result


def test_tail_log_missing_file():
    result = po.tail_log(name="never-started")
    assert "❌" in result
