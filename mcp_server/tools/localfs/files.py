"""MCP tools: sandboxed local filesystem access.

Every path is resolved (symlinks included) and must live inside
LOCAL_TOOLS_ROOT. Anything outside is refused with a clear message.
"""

import os
from pathlib import Path

from mcp_server.core.registry import mcp_tool

# Limits (overridable by env)
MAX_READ_BYTES = int(os.environ.get("LOCAL_TOOLS_MAX_READ_BYTES", 1_000_000))       # 1 MB
MAX_WRITE_BYTES = int(os.environ.get("LOCAL_TOOLS_MAX_WRITE_BYTES", 1_000_000))     # 1 MB
MAX_LIST_ENTRIES = int(os.environ.get("LOCAL_TOOLS_MAX_LIST_ENTRIES", 1000))
MAX_GREP_MATCHES = int(os.environ.get("LOCAL_TOOLS_MAX_GREP_MATCHES", 200))
DOWNLOAD_PREVIEW_LINES = int(os.environ.get("LOCAL_TOOLS_DOWNLOAD_PREVIEW_LINES", 20))


def _root() -> Path:
    raw = os.environ.get("LOCAL_TOOLS_ROOT") or str(Path.home() / "workspace")
    root = Path(raw).expanduser().resolve()
    return root


def _safe_path(user_path: str) -> Path:
    """Resolve user_path under the whitelist root, or raise ValueError."""
    root = _root()
    if not root.exists():
        raise ValueError(
            f"LOCAL_TOOLS_ROOT does not exist: {root}. "
            "Create it or set LOCAL_TOOLS_ROOT to an existing directory."
        )
    # Treat absolute-looking inputs as relative to root to avoid accidental escape;
    # also accept explicit relative paths.
    p = Path(user_path)
    if p.is_absolute():
        candidate = p
    else:
        candidate = root / p
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        raise ValueError(
            f"Path '{user_path}' resolves to '{resolved}', which is outside "
            f"the allowed root '{root}'."
        )
    return resolved


@mcp_tool(
    name="read_local_file",
    description="Читает текстовый файл из локального workspace (только внутри LOCAL_TOOLS_ROOT)",
    parameters={
        "path": {"type": "string", "description": "Путь относительно корня workspace"},
        "max_bytes": {"type": "integer", "description": "Лимит байт (по умолчанию из env)"},
    },
    required=["path"],
)
def read_local_file(client=None, **kwargs) -> str:
    try:
        p = _safe_path(kwargs["path"])
    except ValueError as e:
        return f"❌ {e}"
    if not p.exists():
        return f"❌ Файл не найден: {p}"
    if not p.is_file():
        return f"❌ Не файл: {p}"
    limit = int(kwargs.get("max_bytes") or MAX_READ_BYTES)
    size = p.stat().st_size
    if size > limit:
        return f"❌ Файл слишком большой: {size} байт (лимит {limit})"
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"❌ Не текстовый файл (или не UTF-8): {p}"


@mcp_tool(
    name="write_local_file",
    description="Записывает текстовый файл в локальный workspace (только внутри LOCAL_TOOLS_ROOT)",
    parameters={
        "path": {"type": "string", "description": "Путь относительно корня workspace"},
        "content": {"type": "string", "description": "Содержимое файла"},
        "overwrite": {"type": "boolean", "description": "Перезаписать, если существует (по умолчанию true)"},
    },
    required=["path", "content"],
)
def write_local_file(client=None, **kwargs) -> str:
    try:
        p = _safe_path(kwargs["path"])
    except ValueError as e:
        return f"❌ {e}"
    content = kwargs["content"]
    data = content.encode("utf-8")
    if len(data) > MAX_WRITE_BYTES:
        return f"❌ Содержимое слишком большое: {len(data)} байт (лимит {MAX_WRITE_BYTES})"
    overwrite = kwargs.get("overwrite", True)
    if p.exists() and not overwrite:
        return f"❌ Файл уже существует и overwrite=false: {p}"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"✅ Записано {len(data)} байт в {p}"


@mcp_tool(
    name="list_local_dir",
    description="Список файлов в директории workspace (только внутри LOCAL_TOOLS_ROOT)",
    parameters={
        "path": {"type": "string", "description": "Путь директории (по умолчанию корень)"},
        "recursive": {"type": "boolean", "description": "Рекурсивно (по умолчанию false)"},
    },
    required=[],
)
def list_local_dir(client=None, **kwargs) -> str:
    try:
        p = _safe_path(kwargs.get("path") or ".")
    except ValueError as e:
        return f"❌ {e}"
    if not p.exists():
        return f"❌ Директория не найдена: {p}"
    if not p.is_dir():
        return f"❌ Не директория: {p}"
    recursive = bool(kwargs.get("recursive"))
    entries = []
    iterator = p.rglob("*") if recursive else p.iterdir()
    for item in iterator:
        if len(entries) >= MAX_LIST_ENTRIES:
            entries.append(f"... (обрезано на {MAX_LIST_ENTRIES})")
            break
        rel = item.relative_to(p)
        icon = "📁" if item.is_dir() else "📄"
        size = item.stat().st_size if item.is_file() else 0
        entries.append(f"{icon} {rel} ({size} b)")
    if not entries:
        return f"(пусто) {p}"
    return f"{p} — {len(entries)} элементов:\n" + "\n".join(entries)


@mcp_tool(
    name="search_in_files",
    description="Поиск подстроки в файлах workspace (grep-подобно, только внутри LOCAL_TOOLS_ROOT)",
    parameters={
        "pattern": {"type": "string", "description": "Строка или regex-шаблон"},
        "path": {"type": "string", "description": "Директория для поиска (по умолчанию корень)"},
        "regex": {"type": "boolean", "description": "Использовать regex (по умолчанию false)"},
        "case_sensitive": {"type": "boolean", "description": "Учитывать регистр (по умолчанию false)"},
        "glob": {"type": "string", "description": "Маска файлов, напр. '*.py' (по умолчанию все текстовые)"},
    },
    required=["pattern"],
)
def search_in_files(client=None, **kwargs) -> str:
    import re

    try:
        base = _safe_path(kwargs.get("path") or ".")
    except ValueError as e:
        return f"❌ {e}"
    if not base.exists() or not base.is_dir():
        return f"❌ Директория не найдена: {base}"

    pattern = kwargs["pattern"]
    use_regex = bool(kwargs.get("regex"))
    case_sensitive = bool(kwargs.get("case_sensitive"))
    glob = kwargs.get("glob") or "**/*"

    flags = 0 if case_sensitive else re.IGNORECASE
    if use_regex:
        try:
            rx = re.compile(pattern, flags)
        except re.error as e:
            return f"❌ Ошибка в regex: {e}"
        def matcher(line: str) -> bool:
            return rx.search(line) is not None
    else:
        needle = pattern if case_sensitive else pattern.lower()
        def matcher(line: str) -> bool:
            hay = line if case_sensitive else line.lower()
            return needle in hay

    results = []
    for f in base.glob(glob):
        if not f.is_file():
            continue
        try:
            if f.stat().st_size > MAX_READ_BYTES:
                continue
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if matcher(line):
                rel = f.relative_to(base)
                results.append(f"{rel}:{i}: {line.strip()[:200]}")
                if len(results) >= MAX_GREP_MATCHES:
                    results.append(f"... (обрезано на {MAX_GREP_MATCHES} совпадений)")
                    break
        if len(results) >= MAX_GREP_MATCHES:
            break

    if not results:
        return "Совпадений не найдено"
    return "\n".join(results)


@mcp_tool(
    name="download_file_to_disk",
    description=(
        "Скачивает файл из GitHub-репозитория в локальный workspace (sandbox) и возвращает "
        "только метаданные: путь, blob SHA, размер, число строк и короткое превью. "
        "Используйте вместо get_file_contents для больших файлов — контент не идёт через "
        "tool-output и не обрезается клиентом. Дальше читайте локальную копию через "
        "read_local_file / search_in_files."
    ),
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "path": {"type": "string", "description": "Путь к файлу в репозитории"},
        "ref": {"type": "string", "description": "Git ref (ветка, тег, коммит). По умолчанию — дефолтная ветка"},
        "dest_path": {"type": "string", "description": "Куда сохранить внутри workspace (по умолчанию basename файла)"},
        "overwrite": {"type": "boolean", "description": "Перезаписать, если существует (по умолчанию true)"},
    },
    required=["owner", "repo", "path"],
)
def download_file_to_disk(client=None, **kwargs) -> str:
    """Download a file from GitHub into the local sandbox and return metadata only.

    This exists specifically to bypass MCP client tool-output truncation for large
    files: the file body never travels through the model context, only its path and
    a short preview do.
    """
    import base64

    if client is None:
        return "❌ download_file_to_disk requires a GitHub client"

    owner = kwargs["owner"]
    repo = kwargs["repo"]
    repo_path = kwargs["path"]
    ref = kwargs.get("ref")

    try:
        data = client.get_file(owner, repo, repo_path, ref)
    except Exception as e:
        return f"❌ Не удалось получить файл {owner}/{repo}/{repo_path}: {e}"

    if isinstance(data, list):
        return (
            f"❌ '{repo_path}' — это директория, а не файл. "
            "Используйте list_directory / list_local_dir."
        )
    if "content" not in data:
        return f"❌ Неожиданный ответ GitHub API: {str(data)[:200]}"

    try:
        raw = base64.b64decode(data["content"])
    except Exception as e:
        return f"❌ Не удалось декодировать base64: {e}"

    blob_sha = data.get("sha", "?")
    size = len(raw)

    dest = kwargs.get("dest_path") or Path(repo_path).name
    try:
        dest_abs = _safe_path(dest)
    except ValueError as e:
        return f"❌ {e}"

    if dest_abs.exists() and not kwargs.get("overwrite", True):
        return f"❌ Файл уже существует и overwrite=false: {dest_abs}"

    # Text vs binary: store bytes as-is either way, but only try to preview text.
    try:
        text = raw.decode("utf-8")
        is_text = True
    except UnicodeDecodeError:
        text = None
        is_text = False

    dest_abs.parent.mkdir(parents=True, exist_ok=True)
    if is_text:
        dest_abs.write_text(text, encoding="utf-8")
    else:
        dest_abs.write_bytes(raw)

    root = _root()
    try:
        rel_dest = dest_abs.relative_to(root)
    except ValueError:
        rel_dest = dest_abs

    lines = [
        f"✅ Сохранено в sandbox: {rel_dest}",
        f"   источник: {owner}/{repo}/{repo_path}@{ref or 'default'}",
        f"   blob SHA: {blob_sha}",
        f"   размер: {size} байт ({'текст UTF-8' if is_text else 'бинарь'})",
    ]

    if is_text:
        total_lines = len(text.splitlines())
        lines.append(f"   строк: {total_lines}")
        preview_lines = text.splitlines()[:DOWNLOAD_PREVIEW_LINES]
        if preview_lines:
            lines.append(f"--- превью ({len(preview_lines)} стр.) ---")
            lines.extend(preview_lines)
            if total_lines > len(preview_lines):
                lines.append(f"... ещё {total_lines - len(preview_lines)} строк — читайте через read_local_file / search_in_files")
    else:
        lines.append("   превью недоступно (не текстовый файл)")

    return "\n".join(lines)
