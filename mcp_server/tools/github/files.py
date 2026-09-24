"""MCP tools: file operations (create, read, delete)."""

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient

# Hard ceiling for a single chunk response. Keeps tool-output small enough that
# no MCP client will ever truncate it, regardless of model context limits.
MAX_CHUNK_BYTES = 32_768       # 32 KB
DEFAULT_CHUNK_LINES = 100
MAX_CHUNK_LINES = 400
MAX_GREP_MATCHES = 200


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
        "sha": {"type": "string", "description": "SHA файла (для обновления)"},
    },
    required=["owner", "repo", "path", "content", "message", "branch"],
)
def create_or_update_file(client: GitHubClient, **kwargs) -> str:
    result = client.create_or_update_file(
        owner=kwargs["owner"], repo=kwargs["repo"], path=kwargs["path"],
        content=kwargs["content"], message=kwargs["message"],
        branch=kwargs["branch"], sha=kwargs.get("sha"),
    )
    return f"✅ Файл '{kwargs['path']}' сохранён в {kwargs['owner']}/{kwargs['repo']} ({kwargs['branch']})"


@mcp_tool(
    name="get_file_contents",
    description=(
        "Получает содержимое файла из репозитория. Для больших файлов используйте "
        "read_file_chunk (гарантированно без обрезки). Параметры offset/limit здесь "
        "оставлены для обратной совместимости."
    ),
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "path": {"type": "string", "description": "Путь к файлу"},
        "ref": {"type": "string", "description": "Git ref (ветка, тег, коммит)"},
        "offset": {"type": "integer", "description": "С какой строки начать (0-based, по умолчанию 0)"},
        "limit": {"type": "integer", "description": "Сколько строк вернуть (по умолчанию все)"},
    },
    required=["owner", "repo", "path"],
)
def get_file_contents(client: GitHubClient, **kwargs) -> str:
    import base64, json
    data = client.get_file(kwargs["owner"], kwargs["repo"], kwargs["path"], kwargs.get("ref"))

    if isinstance(data, list):
        items = []
        for item in data:
            icon = "📁" if item.get("type") == "dir" else "📄"
            items.append(f"{icon} {item['name']}")
        return "\n".join(items) if items else "(empty)"

    if "content" not in data:
        return json.dumps(data, indent=2, ensure_ascii=False)

    try:
        text = base64.b64decode(data["content"]).decode("utf-8")
    except Exception:
        return f"[Binary: {data.get('size', '?')} bytes]"

    offset = kwargs.get("offset")
    limit = kwargs.get("limit")
    if offset is None and limit is None:
        return text

    lines = text.splitlines()
    total = len(lines)
    off = max(int(offset or 0), 0)
    lim = int(limit) if limit else total
    chunk = lines[off:off + lim]
    first = off + 1 if chunk else off
    last = off + len(chunk)
    header = f"[строки {first}-{last} из {total}]"
    return header + "\n" + "\n".join(chunk)


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
def read_file_chunk(client: GitHubClient, **kwargs) -> str:
    import base64

    data = client.get_file(kwargs["owner"], kwargs["repo"], kwargs["path"], kwargs.get("ref"))
    if isinstance(data, list):
        return f"❌ '{kwargs['path']}' — директория. Используйте list_directory."
    if "content" not in data:
        return f"❌ Неожиданный ответ GitHub API: {str(data)[:200]}"
    try:
        text = base64.b64decode(data["content"]).decode("utf-8")
    except Exception:
        return f"❌ Не текстовый файл (или не UTF-8): {kwargs['path']}"

    lines = text.splitlines()
    total = len(lines)
    off = max(int(kwargs.get("offset") or 0), 0)
    lim = int(kwargs.get("limit") or DEFAULT_CHUNK_LINES)
    lim = max(1, min(lim, MAX_CHUNK_LINES))

    if off >= total:
        return f"[строки {off}-{off} из {total}] — offset за пределами файла (всего {total} строк)"

    chunk = lines[off:off + lim]
    body = "\n".join(chunk)
    encoded = body.encode("utf-8")

    truncated_note = ""
    if len(encoded) > MAX_CHUNK_BYTES:
        # Cut by bytes, then by lines to stay valid
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
def grep_file(client: GitHubClient, **kwargs) -> str:
    import base64, re

    data = client.get_file(kwargs["owner"], kwargs["repo"], kwargs["path"], kwargs.get("ref"))
    if isinstance(data, list):
        return f"❌ '{kwargs['path']}' — директория. Используйте list_directory."
    if "content" not in data:
        return f"❌ Неожиданный ответ GitHub API: {str(data)[:200]}"
    try:
        text = base64.b64decode(data["content"]).decode("utf-8")
    except Exception:
        return f"❌ Не текстовый файл (или не UTF-8): {kwargs['path']}"

    pattern = kwargs["pattern"]
    use_regex = bool(kwargs.get("regex"))
    case_sensitive = bool(kwargs.get("case_sensitive"))
    limit = int(kwargs.get("max_matches") or MAX_GREP_MATCHES)

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

    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        if matcher(line):
            hits.append(f"{i}: {line.strip()[:200]}")
            if len(hits) >= limit:
                hits.append(f"... (обрезано на {limit} совпадений)")
                break

    if not hits:
        return f"Совпадений не найдено: {kwargs['path']}"
    return f"{kwargs['path']} — {len(hits)} совпадений:\n" + "\n".join(hits)


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
def delete_file(client: GitHubClient, **kwargs) -> str:
    sha = client.get_file_sha(kwargs["owner"], kwargs["repo"], kwargs["path"])
    if not sha:
        return f"❌ Файл '{kwargs['path']}' не найден"
    client.delete_file(kwargs["owner"], kwargs["repo"], kwargs["path"], kwargs["message"], kwargs["branch"], sha)
    return f"✅ Файл '{kwargs['path']}' удалён из {kwargs['owner']}/{kwargs['repo']} ({kwargs['branch']})"


@mcp_tool(
    name="create_or_update_binary_file",
    description="Создаёт или обновляет БИНАРНЫЙ файл в репозитории (base64)",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "path": {"type": "string"},
        "content_base64": {"type": "string", "description": "Base64-encoded содержимое"},
        "message": {"type": "string"},
        "branch": {"type": "string"},
        "sha": {"type": "string"},
    },
    required=["owner", "repo", "path", "content_base64", "message", "branch"],
)
def create_or_update_binary_file(client: GitHubClient, **kwargs) -> str:
    import base64 as b64, httpx
    try:
        b64.b64decode(kwargs["content_base64"])
    except Exception:
        return "❌ Неверный base64"
    body = {"message": kwargs["message"], "content": kwargs["content_base64"], "branch": kwargs["branch"]}
    if kwargs.get("sha"):
        body["sha"] = kwargs["sha"]
    with httpx.Client(timeout=30.0) as c:
        resp = c.put(
            f"https://api.github.com/repos/{kwargs['owner']}/{kwargs['repo']}/contents/{kwargs['path']}",
            headers=client._headers, json=body,
        )
        resp.raise_for_status()
    return f"✅ Бинарный файл '{kwargs['path']}' сохранён"
