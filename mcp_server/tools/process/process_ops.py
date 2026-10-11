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
restarted while bookkeeping remains. Actual child survival depends on the
service manager KillMode/cgroup policy; new sessions do not escape a cgroup.
"""

import json
import stat
import uuid
from contextlib import contextmanager
from functools import wraps
from itertools import islice
import os
import shlex
import shutil
import signal as signal_module
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from mcp_server.core.registry import mcp_tool

MAX_OUTPUT_BYTES = min(max(int(os.environ.get("LOCAL_TOOLS_MAX_OUTPUT_BYTES", 200_000)), 1), 1_000_000)
DEFAULT_STOP_TIMEOUT = min(max(int(os.environ.get("LOCAL_TOOLS_STOP_TIMEOUT", 10)), 0), 30)

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
    if d.is_symlink():
        raise ValueError("Bookkeeping directory must not be a symlink")
    d.mkdir(mode=0o700, parents=False, exist_ok=True)
    if not d.is_dir() or d.stat().st_uid != os.geteuid():
        raise ValueError("Bookkeeping directory must belong to the server user")
    return d


@contextmanager
def _store():
    # Anchor all opens/renames/unlinks to a no-follow directory descriptor.
    directory = _processes_dir()
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if os.fstat(fd).st_uid != os.geteuid():
            raise ValueError("Bookkeeping owner mismatch")
        os.fchmod(fd, 0o700)
        yield fd
    finally:
        os.close(fd)


def _regular_fd(directory_fd, filename, flags):
    fd = os.open(filename, flags | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, 0o600,
                 dir_fd=directory_fd)
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_uid != os.geteuid():
        os.close(fd)
        raise ValueError("Bookkeeping/log must be a single-link regular file owned by the server")
    return fd


def _locked_result(func):
    @wraps(func)
    def guarded(*args, **kwargs):
        try:
            if not Path("/proc/sys/kernel/random/boot_id").is_file():
                raise ValueError("Safe process management requires Linux /proc")
            import fcntl
            with _store() as directory_fd:
                lock_fd = _regular_fd(directory_fd, ".lock", os.O_CREAT | os.O_RDWR)
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return func(*args, **kwargs)
                finally:
                    os.close(lock_fd)
        except (ValueError, OSError, TypeError) as error:
            return f"❌ {error}"
    return guarded


def _validate_name(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("'name' не может быть пустым и должен быть строкой")
    name = name.strip()
    if len(name) > 64 or any(c not in _NAME_ALLOWED for c in name):
        raise ValueError("'name' должно быть из букв/цифр/'-'/'_', не длиннее 64 символов")
    return name


def _meta_path(name: str) -> Path:
    return _processes_dir() / f"{_validate_name(name)}.json"


def _log_path(name: str) -> Path:
    return _processes_dir() / f"{_validate_name(name)}.log"


def _is_denied(argv: list[str]) -> str | None:
    joined = " ".join(argv)
    for bad in _DENY_SUBSTRINGS:
        if bad in joined:
            return bad
    return None


def _to_argv(cmd) -> list[str]:
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    if not isinstance(cmd, list) or not all(isinstance(a, str) and "\x00" not in a for a in cmd):
        raise ValueError("cmd must be a string or a list of NUL-free strings")
    return cmd


def _load_meta(name: str) -> dict | None:
    with _store() as directory_fd:
        try:
            fd = _regular_fd(directory_fd, f"{name}.json", os.O_RDONLY)
        except FileNotFoundError:
            return None
        with os.fdopen(fd, "r", encoding="utf-8") as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise ValueError("Metadata exceeds the read limit")
        try:
            meta = json.loads(raw)
        except json.JSONDecodeError:
            raise ValueError("Invalid process metadata") from None
    if (not isinstance(meta, dict) or meta.get("name") != name
            or type(meta.get("pid")) is not int or meta["pid"] <= 1
            or not isinstance(meta.get("cmd"), list)
            or not all(isinstance(arg, str) for arg in meta["cmd"])
            or not isinstance(meta.get("started_at"), str)):
        raise ValueError("Invalid process metadata fields")
    return meta


def _write_meta(name: str, meta: dict) -> None:
    temporary = f".{name}-{uuid.uuid4().hex}.tmp"
    with _store() as directory_fd:
        try:
            fd = _regular_fd(directory_fd, temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(meta, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, f"{name}.json", src_dir_fd=directory_fd,
                       dst_dir_fd=directory_fd)
        finally:
            try:
                os.unlink(temporary, dir_fd=directory_fd)
            except FileNotFoundError:
                pass


def _forget(name: str) -> None:
    with _store() as directory_fd:
        try:
            os.unlink(f"{name}.json", dir_fd=directory_fd)
        except FileNotFoundError:
            pass


def _process_identity(pid: int) -> dict | None:
    if type(pid) is not int or pid <= 1:
        return None
    try:
        raw = Path(f"/proc/{pid}/stat").read_text()
        fields = raw.rsplit(")", 1)[1].split()
        uid_line = next(line for line in Path(f"/proc/{pid}/status").read_text().splitlines()
                        if line.startswith("Uid:"))
        return {
            "start_ticks": fields[19],
            "uid": int(uid_line.split()[2]),
            "pgid": int(fields[2]), "sid": int(fields[3]),
            "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        }
    except (FileNotFoundError, PermissionError, IndexError, ValueError, StopIteration):
        return None


def _same_process(meta: dict) -> bool:
    saved = meta.get("identity")
    current = _process_identity(meta["pid"])
    return (isinstance(saved, dict) and saved == current
            and saved.get("uid") == os.geteuid()
            and saved.get("pgid") == meta["pid"]
            and saved.get("sid") == meta["pid"])


def _cancel_start(proc, identity) -> None:
    """Best-effort cleanup of a just-created child after tracking failure."""
    meta = {"pid": proc.pid, "identity": identity}
    if identity and _same_process(meta):
        try:
            os.killpg(proc.pid, signal_module.SIGTERM)
        except ProcessLookupError:
            pass
    else:
        proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        if identity and _same_process(meta):
            os.killpg(proc.pid, signal_module.SIGKILL)
        else:
            proc.kill()
        proc.wait(timeout=3)


def _proc_state(pid: int) -> str | None:
    """Linux /proc state char ('R','S','D','Z','T',...), or None if pid is gone."""
    try:
        with open(f"/proc/{pid}/status", encoding="utf-8") as f:
            for line in f:
                if line.startswith("State:"):
                    # e.g. "State:\tZ (zombie)"
                    return line.split()[1]
    except (FileNotFoundError, ProcessLookupError):
        # A Linux /proc entry can vanish after open, while iterating its contents.
        # Catch only confirmed disappearance, not permission or unrelated I/O errors.
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
            after_reap = _proc_state(pid)
            return after_reap is not None and after_reap != "Z"
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
    if len(text.encode("utf-8")) > MAX_OUTPUT_BYTES:
        return text.encode("utf-8")[-MAX_OUTPUT_BYTES:].decode("utf-8", errors="ignore")
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
@_locked_result
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

    if existing is None and len(list(islice(_processes_dir().glob("*.json"), 100))) >= 100:
        return "❌ Лимит 100 tracked processes; сначала очисти завершённые записи через stop_process"

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
    if (not isinstance(env_overrides, dict)
            or not all(isinstance(k, str) and k and "=" not in k and "\x00" not in k
                       and isinstance(v, str) and "\x00" not in v
                       for k, v in env_overrides.items())):
        return "❌ 'env' должен быть объектом строка->строка без NUL"
    env = {**os.environ, **env_overrides}

    log_file = _log_path(name)
    with _store() as directory_fd:
        log_fd = _regular_fd(directory_fd, f"{name}.log", os.O_CREAT | os.O_WRONLY | os.O_APPEND)
    log_handle = os.fdopen(log_fd, "ab")
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

    identity = _process_identity(proc.pid)
    exited = identity is None and proc.poll() is not None
    if identity is None and not exited:
        _cancel_start(proc, identity)
        return "❌ Не удалось подтвердить identity процесса; запуск отменён"

    meta = {
        "identity": identity, "exited": exited,
        "name": name,
        "pid": proc.pid,
        "cmd": argv,
        "cwd": str(cwd),
        "log_file": str(log_file),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        _write_meta(name, meta)
    except (ValueError, OSError):
        # Do not leave an untracked direct child when persistence fails.
        _cancel_start(proc, identity)
        return "❌ Не удалось сохранить metadata; запуск отменён"

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
            "minimum": 0, "maximum": 30,
            "description": f"Секунд ждать после сигнала: 0–30 (по умолчанию {DEFAULT_STOP_TIMEOUT})",
        },
    },
    required=["name"],
)
@_locked_result
def stop_process(client=None, **kwargs) -> str:
    try:
        name = _validate_name(kwargs.get("name"))
    except ValueError as e:
        return f"❌ {e}"

    meta = _load_meta(name)
    if not meta:
        return f"❌ Процесс '{name}' не найден (не запускался через start_background или уже забыт)"

    pid = meta["pid"]
    if meta.get("exited") or not _is_alive(pid):
        _forget(name)
        return f"ℹ️ '{name}' (pid={pid}) уже не выполняется. Запись убрана."

    if not _same_process(meta):
        return "❌ Identity/owner/group не подтверждены; сигнал НЕ отправлен (stale или legacy metadata)"
    force = kwargs.get("force", False)
    timeout = kwargs.get("timeout", DEFAULT_STOP_TIMEOUT)
    if type(force) is not bool or type(timeout) is not int or not 0 <= timeout <= 30:
        return "❌ force должен быть boolean, timeout — целым числом 0–30"

    try:
        # Recheck just before signaling; group signaling still has a narrow
        # OS-level race and is not an atomic pidfd-based group operation.
        if not _same_process(meta):
            return "❌ Identity изменилась перед сигналом; сигнал НЕ отправлен"
        target = signal_module.SIGKILL if force else signal_module.SIGTERM
        # pid == its own process group id here (start_new_session=True made
        # it a session/group leader), so signal the whole group — otherwise
        # a shell-wrapped command (`bash -c "...; sleep 30"`) can eat the
        # signal without it ever reaching the real work, since bash defers
        # trap handling until a synchronous foreground child returns.
        os.killpg(pid, target)
    except ProcessLookupError:
        _forget(name)
        return f"ℹ️ '{name}' (pid={pid}) исчез между проверкой и сигналом. Запись убрана."
    except PermissionError as e:
        return f"❌ Нет прав отправить сигнал pid={pid}: {e}"

    if not force:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not _is_alive(pid) or not _same_process(meta):
                break
            time.sleep(0.2)
    else:
        # SIGKILL is not instantaneous either — the kernel still needs a
        # moment to reap it. Poll briefly instead of checking immediately.
        deadline = time.monotonic() + min(timeout, 3)
        while time.monotonic() < deadline:
            if not _is_alive(pid) or not _same_process(meta):
                break
            time.sleep(0.05)

    if _is_alive(pid) and _same_process(meta):
        if force:
            return f"❌ Не удалось остановить '{name}' (pid={pid}) даже SIGKILL'ом"
        return (
            f"⚠️ '{name}' (pid={pid}) не завершился за {timeout}s после SIGTERM. "
            f"Повтори с force=true для SIGKILL."
        )

    _forget(name)
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
@_locked_result
def process_status(client=None, **kwargs) -> str:
    name = kwargs.get("name")

    def _line(meta: dict) -> str:
        alive = not meta.get("exited") and _is_alive(meta["pid"])
        verified = alive and _same_process(meta)
        icon = "🟢" if verified else ("⚠️" if alive else "🔴")
        state = "работает" if verified else ("identity не подтверждена" if alive else "остановлен")
        return (
            f"{icon} {meta['name']} (pid={meta['pid']}, {state}) "
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
    paths = list(islice(_processes_dir().glob("*.json"), 101))
    for f in sorted(paths[:100]):
        try:
            meta = _load_meta(_validate_name(f.stem))
            if meta:
                metas.append(meta)
        except (OSError, ValueError):
            continue
    if not metas:
        return "Нет отслеживаемых процессов."
    result = "\n".join(_line(m) for m in metas)
    if len(paths) > 100:
        result += "\n... truncated=true: максимум 100 записей; запроси конкретное name"
    return result


@mcp_tool(
    name="tail_log",
    description=(
        "Последние строки лог-файла процесса, запущенного через start_background. "
        "Требует ENABLE_LOCAL_SHELL=1."
    ),
    parameters={
        "name": {"type": "string", "description": "Имя процесса (как в start_background)"},
        "lines": {"type": "integer", "minimum": 0, "maximum": 1000,
                  "description": "Сколько последних строк: 0–1000 (по умолчанию 100; 0 — пустой вывод)"},
    },
    required=["name"],
)
@_locked_result
def tail_log(client=None, **kwargs) -> str:
    try:
        name = _validate_name(kwargs.get("name"))
    except ValueError as e:
        return f"❌ {e}"

    # Never trust log_file from mutable metadata. Canonical name only.
    n = kwargs.get("lines", 100)
    if type(n) is not int or not 0 <= n <= 1000:
        return "❌ lines должен быть целым числом 0–1000"
    log_file = _log_path(name)
    with _store() as directory_fd:
        try:
            fd = _regular_fd(directory_fd, f"{name}.log", os.O_RDONLY)
        except FileNotFoundError:
            return f"❌ Лог-файл не найден: {log_file}"
        with os.fdopen(fd, "rb") as stream:
            size = os.fstat(stream.fileno()).st_size
            budget = max(MAX_OUTPUT_BYTES, 0)
            stream.seek(max(0, size - budget))
            raw = stream.read(budget)
    text = raw.decode("utf-8", errors="ignore")
    tail = text.splitlines()[-n:] if n else []
    body = _truncate("\n".join(tail))
    clipped = size > len(raw)
    return (f"--- {log_file} (последние {len(tail)} строк; "
            f"bytes_truncated={str(clipped).lower()}) ---\n{body}")
