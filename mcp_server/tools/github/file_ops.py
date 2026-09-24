"""File operations tools: get_file_contents, create_or_update_file, delete_file,
read_file_chunk, grep_file."""

import base64
import json
import re

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient

# Hard ceiling for a single chunk response. Keeps tool-output small enough
# that no MCP client will truncate it, regardless of model context limits.
MAX_CHUNK_BYTES = 32_768       # 32 KB
DEFAULT_CHUNK_LINES = 100
MAX_CHUNK_LINES = 400
MAX_GREP_MATCHES = 200


@mcp_tool(
    name="get_file_contents",
    description="Получает содержимое файла из репозитория",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "path": {"type": "string", "description": "Путь к файлу в репозитории"},
        "ref": {"type": "string", "description": "Ветка или коммит (опционально)"},
    },
    required=["owner", "repo", "path"],
)
def get_file_contents(client: GitHubClient, owner: str, repo: str, path: str, ref: str | None = None) -> str:
    """Get file contents from a GitHub repository."""
    try:
        data = client.get_file(owner, repo, path, ref)
        if "content" in data:
            decoded = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
            return decoded
        elif isinstance(data, list):
            # Directory listing
            items = [f"{'📁' if item['type'] == 'dir' else '📄'} {item['name']}" for item in data]
            return "\n".join(items)
        else:
            return json.dumps(data, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"❌ Ошибка: {e}"


@mcp_tool(
    name="create_or_update_file",
    description="Создаёт или обновляет ТЕКСТОВЫЙ файл в репозитории",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "path": {"type": "string", "description": "Путь к файлу"},
        "content": {"type": "string", "description": "Содержимое файла"},
        "message": {"type": "string", "description": "Коммит-сообщение"},
        "branch": {"type": "string", "description": "Ветка"},
        "sha": {"type": "string", "description": "SHA файла при обновлении"},
    },
    required=["owner", "repo", "path", "content", "message", "branch"],
)
def create_or_update_file(
    client: GitHubClient,
    owner: str, repo: str, path: str, content: str,
    message: str, branch: str, sha: str | None = None
) -> str:
    """Create or update a file."""
    try:
        client.create_or_update_file(owner, repo, path, content, message, branch, sha)
        return f"✅ Файл {path} успешно сохранён в {owner}/{repo} ({branch})"
    except Exception as e:
        return f"❌ Ошибка: {e}"


@mcp_tool(
    name="delete_file",
    description="Удаляет файл из GitHub репозитория (автоматически получает SHA)",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "path": {"type": "string", "description": "Путь к файлу"},
        "message": {"type": "string", "description": "Коммит-сообщение"},
        "branch": {"type": "string", "description": "Ветка"},
    },
    required=["owner", "repo", "path", "message", "branch"],
)
def delete_file(
    client: GitHubClient,
    owner: str, repo: str, path: str,
    message: str, branch: str
) -> str:
    """Delete a file, auto-fetching SHA."""
    try:
        sha = client.get_file_sha(owner, repo, path, branch)
        if not sha:
            return f"❌ Файл {path} не найден в {owner}/{repo}"
        client.delete_file(owner, repo, path, message, branch, sha)
        return f"✅ Файл {path} успешно удалён из {owner}/{repo} ({branch})"
    except Exception as e:
        return f"❌ Ошибка: {e}"


@mcp_tool(
    name="read_file_chunk",
    description=(
        "Читает диапазон строк файла прямо из GitHub. Возвращает жёстко ограниченный "
        "кусок (<= 32 KB), поэтому ответ гарантированно не будет обрезан клиентом. "
        "Для больших файлов вызывайте несколько раз, увеличивая offset. "
        "В заголовке указано, какие строки вернулись и сколько их всего."
    ),
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "path": {"type": "string", "description": "Путь к файлу"},
        "ref": {"type": "string", "description": "Git ref (ветка, тег, коммит). По умолчанию — дефолтная ветка"},
        "offset": {"type": "integer", "description": "С какой строки начать (0-based, по умолчанию 0)"},
        "limit": {"type": "integer", "description": f"Сколько строк вернуть (по умолчанию {DEFAULT_CHUNK_LINES}, максимум {MAX_CHUNK_LINES})"},
    },
    required=["owner", "repo", "path"],
)
def read_file_chunk(
    client: GitHubClient,
    owner: str, repo: str, path: str,
    ref: str | None = None, offset: int | None = None, limit: int | None = None
) -> str:
    """Read a line-range of a file directly from GitHub, bounded in size."""
    try:
        data = client.get_file(owner, repo, path, ref)
    except Exception as e:
        return f"❌ Ошибка: {e}"

    if isinstance(data, list):
        return f"❌ '{path}' — директория. Используйте list_directory."
    if "content" not in data:
        return f"❌ Неожиданный ответ GitHub API: {str(data)[:200]}"
    try:
        text = base64.b64decode(data["content"]).decode("utf-8")
    except Exception:
        return f"❌ Не текстовый файл (или не UTF-8): {path}"

    lines = text.splitlines()
    total = len(lines)
    off = max(int(offset or 0), 0)
    lim = int(limit or DEFAULT_CHUNK_LINES)
    lim = max(1, min(lim, MAX_CHUNK_LINES))

    if off >= total:
        return f"[строки {off}-{off} из {total}] — offset за пределами файла (всего {total} строк)"

    chunk = lines[off:off + lim]
    body = "\n".join(chunk)
    encoded = body.encode("utf-8")

    truncated_note = ""
    if len(encoded) > MAX_CHUNK_BYTES:
        cut = encoded[:MAX_CHUNK_BYTES].decode("utf-8", errors="ignore")
        chunk = cut.splitlines()
        body = "\n".join(chunk)
        truncated_note = f" (обрезано по {MAX_CHUNK_BYTES} байт)"

    first = off + 1 if chunk else off
    last = off + len(chunk)
    header = f"[строки {first}-{last} из {total}{truncated_note}]"

    next_offset = off + len(chunk)
    if next_offset < total:
        tail = f"\n... ещё {total - next_offset} строк — продолжить: offset={next_offset}"
    else:
        tail = "\n(конец файла)"

    return header + "\n" + body + tail


@mcp_tool(
    name="grep_file",
    description=(
        "Ищет подстроку или regex в файле прямо на сервере и возвращает только "
        "совпавшие строки с номерами. Маленький ответ — идеально для больших файлов, "
        "когда нужен не весь файл, а конкретные места."
    ),
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "path": {"type": "string", "description": "Путь к файлу"},
        "pattern": {"type": "string", "description": "Строка или regex-шаблон"},
        "ref": {"type": "string", "description": "Git ref (ветка, тег, коммит)"},
        "regex": {"type": "boolean", "description": "Использовать regex (по умолчанию false)"},
        "case_sensitive": {"type": "boolean", "description": "Учитывать регистр (по умолчанию false)"},
        "max_matches": {"type": "integer", "description": f"Максимум совпадений (по умолчанию {MAX_GREP_MATCHES})"},
    },
    required=["owner", "repo", "path", "pattern"],
)
def grep_file(
    client: GitHubClient,
    owner: str, repo: str, path: str, pattern: str,
    ref: str | None = None, regex: bool | None = None,
    case_sensitive: bool | None = None, max_matches: int | None = None
) -> str:
    """Search a pattern inside a file on the server side, return matched lines only."""
    try:
        data = client.get_file(owner, repo, path, ref)
    except Exception as e:
        return f"❌ Ошибка: {e}"

    if isinstance(data, list):
        return f"❌ '{path}' — директория. Используйте list_directory."
    if "content" not in data:
        return f"❌ Неожиданный ответ GitHub API: {str(data)[:200]}"
    try:
        text = base64.b64decode(data["content"]).decode("utf-8")
    except Exception:
        return f"❌ Не текстовый файл (или не UTF-8): {path}"

    use_regex = bool(regex)
    cs = bool(case_sensitive)
    limit = int(max_matches or MAX_GREP_MATCHES)

    flags = 0 if cs else re.IGNORECASE
    if use_regex:
        try:
            rx = re.compile(pattern, flags)
        except re.error as e:
            return f"❌ Ошибка в regex: {e}"
        def matcher(line: str) -> bool:
            return rx.search(line) is not None
    else:
        needle = pattern if cs else pattern.lower()
        def matcher(line: str) -> bool:
            hay = line if cs else line.lower()
            return needle in hay

    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        if matcher(line):
            hits.append(f"{i}: {line.strip()[:200]}")
            if len(hits) >= limit:
                hits.append(f"... (обрезано на {limit} совпадений)")
                break

    if not hits:
        return f"Совпадений не найдено: {path}"
    return f"{path} — {len(hits)} совпадений:\n" + "\n".join(hits)
