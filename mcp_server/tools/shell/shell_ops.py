"""MCP tools: sandboxed shell / python execution.

Safety model (see SANDBOX.md):
- Disabled by default; registered only when ENABLE_LOCAL_SHELL is truthy.
- Every command runs with cwd inside LOCAL_TOOLS_ROOT.
- Never uses shell=True. `cmd` is a list of argv; a plain string is split
  with shlex.split (POSIX-ish) — no shell metacharacter interpretation.
- Timeout and output size are bounded.
- Obvious destructive commands are refused before execution.

This module does NOT provide OS-level isolation. It must be combined with
a separate Linux user (level 1), WSL2 without automount (level 2) or
bwrap/Docker (levels 3-4). Without that, a determined command can still
read world-readable files or reach the network.
"""

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from mcp_server.core.registry import mcp_tool

MAX_OUTPUT_BYTES = int(os.environ.get("LOCAL_TOOLS_MAX_OUTPUT_BYTES", 200_000))
SHELL_TIMEOUT = int(os.environ.get("LOCAL_TOOLS_SHELL_TIMEOUT", 60))

# Deny-list of substrings that are almost always destructive or abusive.
# This is a guard-rail, not a sandbox. Real isolation is external.
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


def _root() -> Path:
    raw = os.environ.get("LOCAL_TOOLS_ROOT") or str(Path.home() / "workspace")
    return Path(raw).expanduser().resolve()


def _safe_dir(user_path: str) -> Path:
    """Resolve `user_path` under LOCAL_TOOLS_ROOT, refusing escapes."""
    root = _root()
    if not root.exists():
        raise ValueError(f"LOCAL_TOOLS_ROOT does not exist: {root}")
    p = Path(user_path or ".")
    candidate = p if p.is_absolute() else (root / p)
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        raise ValueError(
            f"Path '{user_path}' resolves to '{resolved}', outside root '{root}'"
        )
    if not resolved.is_dir():
        raise ValueError(f"Not a directory: {resolved}")
    return resolved


def _is_denied(argv: list[str]) -> str | None:
    joined = " ".join(argv)
    for bad in _DENY_SUBSTRINGS:
        if bad in joined:
            return bad
    return None


def _truncate(text: str) -> str:
    if len(text) > MAX_OUTPUT_BYTES:
        return text[:MAX_OUTPUT_BYTES] + f"\n\n[...обрезано, всего {len(text)} символов]"
    return text


def _to_argv(cmd) -> list[str]:
    if isinstance(cmd, list):
        return [str(a) for a in cmd]
    if isinstance(cmd, str):
        return shlex.split(cmd)
    raise ValueError("cmd must be a string or a list of strings")


@mcp_tool(
    name="run_command",
    description=(
        "Запускает команду в sandbox-корне (без shell). cwd ограничен "
        "LOCAL_TOOLS_ROOT. Требует ENABLE_LOCAL_SHELL=1."
    ),
    parameters={
        "cmd": {
            "type": "array",
            "description": "Команда и аргументы списком, например ['ls','-la']. Строка будет разбита через shlex.split.",
            "items": {"type": "string"},
        },
        "cwd": {
            "type": "string",
            "description": "Рабочая директория относительно LOCAL_TOOLS_ROOT (по умолчанию '.')",
        },
        "timeout": {
            "type": "integer",
            "description": f"Таймаут в секундах (по умолчанию {SHELL_TIMEOUT})",
        },
    },
    required=["cmd"],
)
def run_command(client=None, **kwargs) -> str:
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

    timeout = int(kwargs.get("timeout") or SHELL_TIMEOUT)

    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return f"❌ Команда превысила таймаут {timeout}s: {' '.join(argv)}"
    except Exception as e:  # noqa: BLE001
        return f"❌ Ошибка запуска: {e}"

    out = (proc.stdout or "") + (proc.stderr or "")
    header = f"$ {' '.join(argv)} (exit={proc.returncode})\n"
    return header + _truncate(out or "(нет вывода)")


@mcp_tool(
    name="run_python",
    description=(
        "Запускает Python-код в отдельном процессе внутри sandbox-корня. "
        "Требует ENABLE_LOCAL_SHELL=1."
    ),
    parameters={
        "code": {"type": "string", "description": "Python-код для выполнения"},
        "cwd": {
            "type": "string",
            "description": "Рабочая директория относительно LOCAL_TOOLS_ROOT (по умолчанию '.')",
        },
        "timeout": {
            "type": "integer",
            "description": f"Таймаут в секундах (по умолчанию {SHELL_TIMEOUT})",
        },
    },
    required=["code"],
)
def run_python(client=None, **kwargs) -> str:
    code = kwargs.get("code") or ""
    if not code.strip():
        return "❌ Пустой код"

    try:
        cwd = _safe_dir(kwargs.get("cwd") or ".")
    except ValueError as e:
        return f"❌ {e}"

    timeout = int(kwargs.get("timeout") or SHELL_TIMEOUT)

    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return f"❌ Python-код превысил таймаут {timeout}s"
    except Exception as e:  # noqa: BLE001
        return f"❌ Ошибка запуска: {e}"

    out = (proc.stdout or "") + (proc.stderr or "")
    header = f"$ python -c <{len(code)} chars> (exit={proc.returncode})\n"
    return header + _truncate(out or "(нет вывода)")
