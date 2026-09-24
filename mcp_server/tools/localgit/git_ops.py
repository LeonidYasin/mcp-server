"""MCP tools: sandboxed local git operations.

Every repo path is resolved under LOCAL_TOOLS_ROOT. Commands are executed
with cwd inside the root. No shell=True, no arbitrary user-supplied flags
for dangerous options.
"""

import os
import shutil
import subprocess
from pathlib import Path

from mcp_server.core.registry import mcp_tool

MAX_OUTPUT_BYTES = int(os.environ.get("LOCAL_TOOLS_MAX_OUTPUT_BYTES", 200_000))
GIT_TIMEOUT = int(os.environ.get("LOCAL_TOOLS_GIT_TIMEOUT", 120))


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
        raise ValueError(
            f"Path '{user_path}' resolves to '{resolved}', outside root '{root}'"
        )
    if not resolved.is_dir():
        raise ValueError(f"Not a directory: {resolved}")
    return resolved


def _git_available() -> bool:
    return shutil.which("git") is not None


def _run_git(cwd: Path, *args: str) -> str:
    """Run `git <args...>` in cwd. Never uses shell."""
    if not _git_available():
        return "❌ git не установлен в PATH"
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return f"❌ git {' '.join(args)}: превышен таймаут {GIT_TIMEOUT}s"
    except Exception as e:  # noqa: BLE001
        return f"❌ git {' '.join(args)}: {e}"

    out = (proc.stdout or "") + (proc.stderr or "")
    if len(out) > MAX_OUTPUT_BYTES:
        out = out[:MAX_OUTPUT_BYTES] + f"\n\n[...обрезано, всего {len(out)} символов]"
    header = f"$ git {' '.join(args)} (exit={proc.returncode})\n"
    return header + (out or "(нет вывода)")


def _ensure_repo(cwd: Path) -> str | None:
    """Return error string if cwd is not a git repo, else None."""
    if not (cwd / ".git").exists():
        # also cover worktrees: .git can be a file
        if not (cwd / ".git").is_file():
            return f"❌ Не git-репозиторий: {cwd}"
    return None


@mcp_tool(
    name="git_status",
    description="git status в репозитории внутри workspace (sandboxed)",
    parameters={
        "path": {"type": "string", "description": "Путь к репозиторию (относительно workspace)"},
        "short": {"type": "boolean", "description": "Краткий вывод (--short)"},
    },
    required=[],
)
def git_status(client=None, **kwargs) -> str:
    try:
        cwd = _safe_dir(kwargs.get("path") or ".")
    except ValueError as e:
        return f"❌ {e}"
    err = _ensure_repo(cwd)
    if err:
        return err
    args = ["status"]
    if kwargs.get("short"):
        args.append("--short")
    return _run_git(cwd, *args)


@mcp_tool(
    name="git_log",
    description="git log в репозитории внутри workspace",
    parameters={
        "path": {"type": "string"},
        "limit": {"type": "integer", "description": "Сколько коммитов (по умолчанию 20)"},
        "oneline": {"type": "boolean", "description": "Одной строкой (по умолчанию true)"},
    },
    required=[],
)
def git_log(client=None, **kwargs) -> str:
    try:
        cwd = _safe_dir(kwargs.get("path") or ".")
    except ValueError as e:
        return f"❌ {e}"
    err = _ensure_repo(cwd)
    if err:
        return err
    limit = int(kwargs.get("limit", 20))
    oneline = kwargs.get("oneline", True)
    args = ["log", f"-n{limit}"]
    if oneline:
        args.append("--oneline")
    return _run_git(cwd, *args)


@mcp_tool(
    name="git_diff",
    description="git diff в репозитории внутри workspace",
    parameters={
        "path": {"type": "string"},
        "staged": {"type": "boolean", "description": "Показать staged (--cached)"},
        "target": {"type": "string", "description": "Коммит/ветка/файл для сравнения"},
    },
    required=[],
)
def git_diff(client=None, **kwargs) -> str:
    try:
        cwd = _safe_dir(kwargs.get("path") or ".")
    except ValueError as e:
        return f"❌ {e}"
    err = _ensure_repo(cwd)
    if err:
        return err
    args = ["diff"]
    if kwargs.get("staged"):
        args.append("--cached")
    target = kwargs.get("target")
    if target:
        # target may be 'HEAD~1' or a file path; both are fine as positional args
        args.append(target)
    return _run_git(cwd, *args)


@mcp_tool(
    name="git_commit",
    description="git add + git commit в репозитории внутри workspace",
    parameters={
        "path": {"type": "string"},
        "message": {"type": "string", "description": "Сообщение коммита"},
        "files": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Файлы для add (по умолчанию '.')",
        },
        "amend": {"type": "boolean", "description": "--amend (по умолчанию false)"},
    },
    required=["message"],
)
def git_commit(client=None, **kwargs) -> str:
    try:
        cwd = _safe_dir(kwargs.get("path") or ".")
    except ValueError as e:
        return f"❌ {e}"
    err = _ensure_repo(cwd)
    if err:
        return err

    files = kwargs.get("files") or ["."]
    if isinstance(files, str):
        files = [files]
    # add
    add_res = _run_git(cwd, "add", "--", *files)
    if "exit=" in add_res and "exit=0" not in add_res:
        return add_res

    commit_args = ["commit", "-m", kwargs["message"]]
    if kwargs.get("amend"):
        commit_args.append("--amend")
    return add_res + "\n" + _run_git(cwd, *commit_args)


@mcp_tool(
    name="git_push",
    description="git push в репозитории внутри workspace (без --force)",
    parameters={
        "path": {"type": "string"},
        "remote": {"type": "string", "description": "По умолчанию origin"},
        "branch": {"type": "string", "description": "По умолчанию текущая ветка"},
        "set_upstream": {"type": "boolean", "description": "-u (по умолчанию false)"},
    },
    required=[],
)
def git_push(client=None, **kwargs) -> str:
    try:
        cwd = _safe_dir(kwargs.get("path") or ".")
    except ValueError as e:
        return f"❌ {e}"
    err = _ensure_repo(cwd)
    if err:
        return err

    remote = kwargs.get("remote") or "origin"
    args = ["push"]
    if kwargs.get("set_upstream"):
        args.append("-u")
    args.append(remote)
    branch = kwargs.get("branch")
    if branch:
        args.append(branch)
    # NOTE: no --force, no --mirror, no --tags by default
    return _run_git(cwd, *args)


@mcp_tool(
    name="git_pull",
    description="git pull в репозитории внутри workspace",
    parameters={
        "path": {"type": "string"},
        "remote": {"type": "string", "description": "По умолчанию origin"},
        "branch": {"type": "string", "description": "По умолчанию текущая"},
        "rebase": {"type": "boolean", "description": "--rebase (по умолчанию false)"},
    },
    required=[],
)
def git_pull(client=None, **kwargs) -> str:
    try:
        cwd = _safe_dir(kwargs.get("path") or ".")
    except ValueError as e:
        return f"❌ {e}"
    err = _ensure_repo(cwd)
    if err:
        return err

    args = ["pull"]
    if kwargs.get("rebase"):
        args.append("--rebase")
    args.append(kwargs.get("remote") or "origin")
    branch = kwargs.get("branch")
    if branch:
        args.append(branch)
    return _run_git(cwd, *args)
