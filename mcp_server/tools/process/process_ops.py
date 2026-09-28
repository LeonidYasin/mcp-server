"""MCP tools: background process management inside the local sandbox.

Why this exists (see SANDBOX.md / shell_ops.py): `run_command` in the shell
tools blocks for the command's duration and is killed at its timeout — it
cannot start a long-lived daemon (e.g. `node dist/index.js`) and leave it
running. These tools fill that one gap: start something detached, then
check on it, read its log, or stop it — nothing else.

Safety model, same class as shell_ops.py:
- Disabled by default; registered only when ENABLE_LOCAL_SHELL is truthy.
- cwd is confined to LOCAL_TOOLS_ROOT, same as the other local tools.
- Never uses shell=True; `cmd` is argv (list) or a shlex-split string.
- Same command deny-list as run_command (sudo, rm -rf /, mkfs, ...).
- No OS-level isolation. Combine with a dedicated non-root Linux user.

Process bookkeeping is a JSON file per named process under
LOCAL_TOOLS_ROOT/.mcp_processes/<name>.json, plus its own log file next to
it. Disk-backed (not just in-memory) on purpose: this MCP server can be
restarted by systemd independently of the processes it started, and
status/stop/tail must keep working for those orphaned-but-alive children.
"""

import json
import os
import shlex
import shutil
import signal as signal_module
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from mcp_server.core.registry import mcp_tool

MAX_OUTPUT_BYTES = int(os.environ.get("LOCAL_TOOLS_MAX_OUTPUT_BYTES", 200_000))
DEFAULT_STOP_TIMEOUT = int(os.environ.get("LOCAL_TOOLS_STOP_TIMEOUT", 10))

# Same guard-rail list as shell_ops.py. Duplicated rather than imported —
# every local-tools module here is self-contained (see localfs/files.py,
# shell/shell_ops.py), and this keeps it that way.
_DENY_SUBSTRINGS = (
    "rm -rf /",
    "rm -fr /",
    "sudo ",
    " su ",
    "mkfs",
    "dd if=",
    ":(){:|:&};:",  # fork bomb
    "/dev/sd",
    "chmod -R 777 /",
    "chown -R ",
    "> /dev/sda",
    "shutdown",
    "reboot",
    "halt",
)

_NAME_ALLOWED = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")


def _root() -> Path:
    raw = os.environ.get("LOCAL_TOOLS_ROOT") or str(Path.home() / "workspace")
    return Path(raw).expanduser().resolve()


def _safe_dir(user_path: str) -> Path:
    root = _root()
    if not root.exists():
        raise ValueError(f"LOCAL_TOOLS_ROOT does not exist: {root}")
    p = Path(user_path or ".")
    candidate = p if p.is_absolute() else (root / p)
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        raise ValueError(f"Path '{user_path}' resolves to '{resolved}', outside root '{root}'")
    if not resolved.is_dir():
        raise ValueError(f"Not a directory: {resolved}")
    return resolved


def _processes_dir() -> Path:
    d = _root() / ".mcp_processes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _validate_name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        raise ValueError("'name' не может быть пустым")
    if len(name) > 64 or any(c not in _NAME_ALLOWED for c in name):
        raise ValueError(
            "'name' должно быть из букв/цифр/'-'/'_', не длиннее 64 символов"
        )
    return name


def _meta_path(name: str) -> Path:
    return _processes_dir() / f"{name}.json"


def _log_path(name: str) -> Path:
    return _processes_dir() / f"{name}.log"


def _is_denied(argv: list[str]) -> str | None:
    joined = " ".join(argv)
    for bad in _DENY_SUBSTRINGS:
        if bad in joined:
            return bad
    return None


def _to_argv(cmd) -> list[str]:
    if isinstance(cmd, list):
        return [str(a) for a in cmd]
    if isinstance(cmd, str):
        return shlex.split(cmd)
    raise ValueError("cmd must be a string or a list of strings")


def _load_meta(name: str) -> dict | None:
    p = _meta_path(name)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _proc_state(pid: int) -> str | None:
    """Linux /proc state char ('R','S','D','Z','T',...), or None if pid is gone."""
    try:
        with open(f"/proc/{pid}/status", encoding="utf-8") as f:
            for line in f:
                if line.startswith("State:"):
                    # e.g. "State:\tZ (zombie)"
                    return line.split()[1]
    except FileNotFoundError:
        return None
    return None


def _reap_if_zombie(pid: int) -> None:
    """Best-effort wait() on a zombie child so it leaves the process table."""
    try:
        os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        pass  # not our child (already reaped, or we're not its parent)
    except OSError:
        pass


def _is_alive(pid: int) -> bool:
    """True if pid is a real, running (non-zombie) process.

    A killed child stays a zombie until its parent wait()s on it — and since
    we don't hold the Popen object across separate tool calls, nothing else
    ever reaps it. `os.kill(pid, 0)` alone can't tell "running" from "dead,
    pending reap", so on Linux we read /proc/<pid>/status instead, and reap
    zombies on sight so they don't pile up in the process table.
    """
    state = _proc_state(pid)
    if state is not None:
        if state == "Z":
            _reap_if_zombie(pid)
            return _proc_state(pid) is not None and _proc_state(pid) != "Z"
        return True
    if Path("/proc").is_dir():
        # /proc exists but this pid doesn't — definitely gone.
        return False
    # Non-Linux fallback: best effort, can't distinguish zombie from alive.
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _truncate(text: str) -> str:
    if len(text) > MAX_OUTPUT_BYTES:
        return text[-MAX_OUTPUT_BYTES:]
    return text


@mcp_tool(
    name="start_background",
    description=(
        "Запускает команду в фоне (detached, переживает сам вызов инструмента) "
        "внутри sandbox-корня. Для управления долгоживущими процессами "
        "(например, node-сервером), которые run_command не может запустить — "
        "он блокирующий и убивает по таймауту. Требует ENABLE_LOCAL_SHELL=1."
    ),
    parameters={
        "name": {
            "type": "string",
            "description": "Уникальное имя процесса (буквы/цифры/-/_), для stop/status/tail_log",
        },
        "cmd": {
            "type": "array",
            "description": "Команда и аргументы списком, например ['node','dist/index.js']. Строка тоже допустима.",
            "items": {"type": "string"},
        },
        "cwd": {
            "type": "string",
            "description": "Рабочая директория относительно LOCAL_TOOLS_ROOT (по умолчанию '.')",
        },
        "env": {
            "type": "object",
            "description": "Дополнительные переменные окружения (поверх текущего окружения сервера)",
        },
    },
    required=["name", "cmd"],
)
def start_background(client=None, **kwargs) -> str:
    try:
        name = _validate_name(kwargs.get("name"))
    except ValueError as e:
        return f"❌ {e}"

    existing = _load_meta(name)
    if existing and _is_alive(existing.get("pid", -1)):
        return (
            f"❌ Процесс '{name}' уже запущен (pid={existing['pid']}). "
            f"Останови его через stop_process сначала."
        )

    try:
        argv = _to_argv(kwargs.get("cmd"))
    except ValueError as e:
        return f"❌ {e}"
    if not argv:
        return "❌ Пустая команда"

    denied = _is_denied(argv)
    if denied:
        return f"❌ Команда отклонена (deny-list): обнаружено '{denied}'"

    try:
        cwd = _safe_dir(kwargs.get("cwd") or ".")
    except ValueError as e:
        return f"❌ {e}"

    if shutil.which(argv[0]) is None:
        return f"❌ Команда не найдена в PATH: {argv[0]}"

    env_overrides = kwargs.get("env") or {}
    if not isinstance(env_overrides, dict):
        return "❌ 'env' должен быть объектом строка->строка"
    env = {**os.environ, **{str(k): str(v) for k, v in env_overrides.items()}}

    log_file = _log_path(name)
    log_handle = open(log_file, "ab")
    try:
        proc = subprocess.Popen(
            argv,
            cwd=str(cwd),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=env,
            shell=False,
            start_new_session=True,  # detach: survives this request, its own process group
        )
    except Exception as e:  # noqa: BLE001
        log_handle.close()
        return f"❌ Ошибка запуска: {e}"
    finally:
        log_handle.close()

    meta = {
        "name": name,
        "pid": proc.pid,
        "cmd": argv,
        "cwd": str(cwd),
        "log_file": str(log_file),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    _meta_path(name).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return (
        f"✅ Запущен '{name}' (pid={proc.pid})\n"
        f"   $ {' '.join(argv)}\n"
        f"   cwd: {cwd}\n"
        f"   log: {log_file}"
    )


@mcp_tool(
    name="stop_process",
    description=(
        "Останавливает фоновый процесс, запущенный через start_background. "
        "По умолчанию SIGTERM с ожиданием, при необходимости — SIGKILL. "
        "Требует ENABLE_LOCAL_SHELL=1."
    ),
    parameters={
        "name": {"type": "string", "description": "Имя процесса (как в start_background)"},
        "force": {
            "type": "boolean",
            "description": "Сразу SIGKILL вместо SIGTERM+ожидание (по умолчанию false)",
        },
        "timeout": {
            "type": "integer",
            "description": f"Секунд ждать после SIGTERM перед выводом статуса (по умолчанию {DEFAULT_STOP_TIMEOUT})",
        },
    },
    required=["name"],
)
def stop_process(client=None, **kwargs) -> str:
    try:
        name = _validate_name(kwargs.get("name"))
    except ValueError as e:
        return f"❌ {e}"

    meta = _load_meta(name)
    if not meta:
        return f"❌ Процесс '{name}' не найден (не запускался через start_background или уже забыт)"

    pid = meta["pid"]
    if not _is_alive(pid):
        _meta_path(name).unlink(missing_ok=True)
        return f"ℹ️ '{name}' (pid={pid}) уже не выполняется. Запись убрана."

    force = bool(kwargs.get("force"))
    timeout = int(kwargs.get("timeout") or DEFAULT_STOP_TIMEOUT)

    try:
        target = signal_module.SIGKILL if force else signal_module.SIGTERM
        # pid == its own process group id here (start_new_session=True made
        # it a session/group leader), so signal the whole group — otherwise
        # a shell-wrapped command (`bash -c "...; sleep 30"`) can eat the
        # signal without it ever reaching the real work, since bash defers
        # trap handling until a synchronous foreground child returns.
        os.killpg(pid, target)
    except ProcessLookupError:
        _meta_path(name).unlink(missing_ok=True)
        return f"ℹ️ '{name}' (pid={pid}) исчез между проверкой и сигналом. Запись убрана."
    except PermissionError as e:
        return f"❌ Нет прав отправить сигнал pid={pid}: {e}"

    if not force:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not _is_alive(pid):
                break
            time.sleep(0.2)
    else:
        # SIGKILL is not instantaneous either — the kernel still needs a
        # moment to reap it. Poll briefly instead of checking immediately.
        deadline = time.monotonic() + min(timeout, 3)
        while time.monotonic() < deadline:
            if not _is_alive(pid):
                break
            time.sleep(0.05)

    if _is_alive(pid):
        if force:
            return f"❌ Не удалось остановить '{name}' (pid={pid}) даже SIGKILL'ом"
        return (
            f"⚠️ '{name}' (pid={pid}) не завершился за {timeout}s после SIGTERM. "
            f"Повтори с force=true для SIGKILL."
        )

    _meta_path(name).unlink(missing_ok=True)
    return f"✅ '{name}' (pid={pid}) остановлен"


@mcp_tool(
    name="process_status",
    description=(
        "Статус фоновых процессов, запущенных через start_background. "
        "Без 'name' — список всех отслеживаемых. Требует ENABLE_LOCAL_SHELL=1."
    ),
    parameters={
        "name": {"type": "string", "description": "Имя конкретного процесса (опционально)"},
    },
    required=[],
)
def process_status(client=None, **kwargs) -> str:
    name = kwargs.get("name")

    def _line(meta: dict) -> str:
        alive = _is_alive(meta["pid"])
        icon = "🟢" if alive else "🔴"
        return (
            f"{icon} {meta['name']} (pid={meta['pid']}, {'работает' if alive else 'остановлен'}) "
            f"— $ {' '.join(meta['cmd'])} — started {meta['started_at']}"
        )

    if name:
        try:
            name = _validate_name(name)
        except ValueError as e:
            return f"❌ {e}"
        meta = _load_meta(name)
        if not meta:
            return f"❌ Процесс '{name}' не найден"
        return _line(meta)

    metas = []
    for f in sorted(_processes_dir().glob("*.json")):
        try:
            metas.append(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    if not metas:
        return "Нет отслеживаемых процессов."
    return "\n".join(_line(m) for m in metas)


@mcp_tool(
    name="tail_log",
    description=(
        "Последние строки лог-файла процесса, запущенного через start_background. "
        "Требует ENABLE_LOCAL_SHELL=1."
    ),
    parameters={
        "name": {"type": "string", "description": "Имя процесса (как в start_background)"},
        "lines": {"type": "integer", "description": "Сколько последних строк (по умолчанию 100)"},
    },
    required=["name"],
)
def tail_log(client=None, **kwargs) -> str:
    try:
        name = _validate_name(kwargs.get("name"))
    except ValueError as e:
        return f"❌ {e}"

    meta = _load_meta(name)
    log_file = Path(meta["log_file"]) if meta else _log_path(name)
    if not log_file.exists():
        return f"❌ Лог-файл не найден: {log_file}"

    n = int(kwargs.get("lines") or 100)
    try:
        text = log_file.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return f"❌ Не удалось прочитать лог: {e}"

    all_lines = text.splitlines()
    tail = all_lines[-n:] if n > 0 else all_lines
    body = _truncate("\n".join(tail))
    return f"--- {log_file} (последние {len(tail)} из {len(all_lines)} строк) ---\n{body}"
