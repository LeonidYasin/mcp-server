"""File operations tools: get_file_contents, create_or_update_file, delete_file,
read_file_chunk, grep_file, read_full_file, get_file_sha, read_multiple_files."""

import base64
import json
import re

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient

# Hard ceiling for a single chunk response.
MAX_CHUNK_BYTES = 32_768       # 32 KB
DEFAULT_CHUNK_LINES = 100
MAX_CHUNK_LINES = 400
MAX_GREP_MATCHES = 200

# read_full_file tuning.
SAFE_CHUNK_BYTES = 24_576          # ~24 KB
MIN_AUTO_CHUNK_LINES = 20
MAX_AUTO_CHUNK_LINES = MAX_CHUNK_LINES
MAX_FULL_FILE_BYTES = 512_000      # 512 KB

# read_multiple_files tuning.
MAX_BATCH_FILES = 20
MAX_BATCH_TOTAL_BYTES = 256_000    # 256 KB на весь батч


def _validate_ref_inputs(owner, repo, path=None) -> str | None:
    """Return a friendly error string if required inputs are empty."""
    if not owner or not str(owner).strip():
        return "❌ Не указан owner."
    if not repo or not str(repo).strip():
        return "❌ Не указан repo."
    if path is not None and (not path or not str(path).strip()):
        return "❌ Не указан path."
    return None


def _file_links(owner: str, repo: str, path: str, ref: str | None) -> str:
    """Build web + raw URLs for a file so the user can open it in a browser."""
    branch = ref or "HEAD"
    html_url = f"https://github.com/{owner}/{repo}/blob/{branch}/{path}"
    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
    return f"🔗 {html_url}\n📄 {raw_url}"


def _sha_line(blob_sha: str | None) -> str:
    """One-line blob SHA hint, so callers can pass it straight to create_or_update_file."""
    if not blob_sha:
        return ""
    return f"SHA: {blob_sha}"


@mcp_tool(
    name="get_file_contents",
    description="Получает содержимое файла из репозитория (со ссылками web/raw и blob SHA)",
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
    err = _validate_ref_inputs(owner, repo, path)
    if err:
        return err
    try:
        data = client.get_file(owner, repo, path, ref)
        if "content" in data:
            decoded = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
            header = _file_links(owner, repo, path, ref)
            sha = _sha_line(data.get("sha"))
            if sha:
                header += "\n" + sha
            return header + "\n\n" + decoded
        elif isinstance(data, list):
            items = [f"{'📁' if item['type'] == 'dir' else '📄'} {item['name']}" for item in data]
            return "\n".join(items)
        else:
            return json.dumps(data, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"❌ Ошибка: {e}"


@mcp_tool(
    name="get_file_sha",
    description="Возвращает blob SHA файла (для последующего create_or_update_file)",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "path": {"type": "string", "description": "Путь к файлу"},
        "ref": {"type": "string", "description": "Ветка/коммит (по умолчанию — дефолтная ветка)"},
    },
    required=["owner", "repo", "path"],
)
def get_file_sha(client: GitHubClient, owner: str, repo: str, path: str, ref: str | None = None) -> str:
    """Return blob SHA of a file, or a friendly message if missing."""
    err = _validate_ref_inputs(owner, repo, path)
    if err:
        return err
    try:
        data = client.get_file(owner, repo, path, ref)
    except Exception as e:
        return f"❌ Ошибка: {e}"
    if isinstance(data, list):
        return f"❌ '{path}' — директория, SHA не применим."
    sha = data.get("sha")
    if not sha:
        return f"❌ Не удалось получить SHA для {path}"
    return f"SHA: {sha}"


@mcp_tool(
    name="read_multiple_files",
    description=(
        "Читает несколько файлов одним вызовом. paths — массив путей (или строка через запятую). "
        "Бюджет на батч ~256 KB и не более 20 файлов. Для каждого файла — ссылки + SHA в шапке."
    ),
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "paths": {"type": "array", "items": {"type": "string"}, "description": "Массив путей к файлам"},
        "ref": {"type": "string", "description": "Ветка/коммит (по умолчанию — дефолтная ветка)"},
    },
    required=["owner", "repo", "paths"],
)
def read_multiple_files(client: GitHubClient, **kwargs) -> str:
    owner, repo = kwargs.get("owner"), kwargs.get("repo")
    err = _validate_ref_inputs(owner, repo)
    if err:
        return err
    paths = kwargs.get("paths")
    if isinstance(paths, str):
        paths = [p.strip() for p in paths.split(",") if p.strip()]
    if not paths:
        return "❌ paths пуст — передай массив путей или строку через запятую."
    if len(paths) > MAX_BATCH_FILES:
        return f"❌ Слишком много файлов ({len(paths)}). Максимум {MAX_BATCH_FILES} за вызов."

    ref = kwargs.get("ref")
    out = []
    total_bytes = 0
    for p in paths:
        try:
            data = client.get_file(owner, repo, p, ref)
        except Exception as e:
            out.append(f"### {p}\n❌ Ошибка: {e}")
            continue
        if isinstance(data, list):
            out.append(f"### {p}\n❌ Это директория (используй list_directory).")
            continue
        if "content" not in data:
            out.append(f"### {p}\n❌ Неожиданный ответ GitHub API.")
            continue
        try:
            decoded = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        except Exception:
            out.append(f"### {p}\n❌ Не текстовый файл (или не UTF-8).")
            continue

        encoded = len(decoded.encode("utf-8"))
        if total_bytes + encoded > MAX_BATCH_TOTAL_BYTES:
            out.append(
                f"### {p}\n⚠️ Пропущен: превышен бюджет батча {MAX_BATCH_TOTAL_BYTES} байт "
                f"(уже {total_bytes}). Читай отдельно через read_full_file."
            )
            continue
        total_bytes += encoded

        header = f"### {p}\n{_file_links(owner, repo, p, ref)}"
        sha = _sha_line(data.get("sha"))
        if sha:
            header += "\n" + sha
        out.append(header + "\n\n" + decoded)

    summary = f"[батч: {len(paths)} файлов, {total_bytes} байт]"
    return summary + "\n\n" + "\n\n".join(out)


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
    err = _validate_ref_inputs(owner, repo, path)
    if err:
        return err
    if not branch or not str(branch).strip():
        return "❌ Не указана branch."
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
    err = _validate_ref_inputs(owner, repo, path)
    if err:
        return err
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
    err = _validate_ref_inputs(owner, repo, path)
    if err:
        return err
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
    name="read_full_file",
    description=(
        "Читает файл ЦЕЛИКОМ, автоматически подбирая размер чанка. "
        "Не нужно вручную угадывать limit/offset: инструмент сам вычисляет "
        "безопасный размер куска по средней длине строки (бюджет ~24 KB на чанк), "
        "последовательно склеивает все куски и возвращает полный текст. "
        "В конце гарантированно стоит маркер (конец файла) либо предупреждение "
        "о достижении защитного бюджета max_bytes."
    ),
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "path": {"type": "string", "description": "Путь к файлу"},
        "ref": {"type": "string", "description": "Git ref (ветка, тег, коммит). По умолчанию — дефолтная ветка"},
        "max_bytes": {"type": "integer", "description": f"Защитный бюджет на весь файл в байтах (по умолчанию {MAX_FULL_FILE_BYTES})"},
        "include_line_numbers": {"type": "boolean", "description": "Добавлять номера строк (по умолчанию false)"},
    },
    required=["owner", "repo", "path"],
)
def read_full_file(
    client: GitHubClient,
    owner: str, repo: str, path: str,
    ref: str | None = None, max_bytes: int | None = None,
    include_line_numbers: bool | None = None
) -> str:
    """Прочитать весь текстовый файл, автоматически выбрав безопасный размер чанка."""
    err = _validate_ref_inputs(owner, repo, path)
    if err:
        return err
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

    links = _file_links(owner, repo, path, ref)
    sha = _sha_line(data.get("sha"))
    if sha:
        links += "\n" + sha

    lines = text.splitlines()
    total = len(lines)
    if total == 0:
        return f"{links}\n[полный файл] {path} — пустой (0 строк)\n(конец файла)"

    budget = max(int(max_bytes or MAX_FULL_FILE_BYTES), MIN_AUTO_CHUNK_LINES)
    total_bytes = len(text.encode("utf-8"))
    avg_line_bytes = max(total_bytes // max(total, 1), 1)

    auto_lines = max(SAFE_CHUNK_BYTES // avg_line_bytes, MIN_AUTO_CHUNK_LINES)
    auto_lines = min(auto_lines, MAX_AUTO_CHUNK_LINES)

    collected: list[str] = []
    collected_bytes = 0
    off = 0
    guard = 0
    max_iterations = total // max(auto_lines, 1) + 8

    while off < total:
        guard += 1
        if guard > max_iterations:
            return (
                f"❌ Внутренняя ошибка: offset не продвинулся на строке {off} "
                f"(итерация {guard}). Прервано, чтобы не зациклиться."
            )

        chunk = lines[off:off + auto_lines]
        if not chunk:
            break

        if include_line_numbers:
            piece = "\n".join(f"{off + i + 1}: {ln}" for i, ln in enumerate(chunk))
        else:
            piece = "\n".join(chunk)

        piece_bytes = len(piece.encode("utf-8"))
        if collected_bytes + piece_bytes > budget:
            remaining = budget - collected_bytes
            if remaining <= 0:
                collected.append(
                    f"\n... ⚠️ достигнут бюджет {budget} байт — файл прочитан НЕ полностью "
                    f"(остановлено на строке {off} из {total}). Увеличьте max_bytes и вызовите снова."
                )
                break
            cut = piece.encode("utf-8")[:remaining].decode("utf-8", errors="ignore")
            collected.append(cut)
            collected_bytes += len(cut.encode("utf-8"))
            collected.append(
                f"\n... ⚠️ достигнут бюджет {budget} байт — файл прочитан НЕ полностью "
                f"(остановлено на строке {off + len(cut.splitlines())} из {total}). "
                f"Увеличьте max_bytes и вызовите снова."
            )
            break

        collected.append(piece)
        collected_bytes += piece_bytes
        off += len(chunk)

    body = "\n".join(collected)
    read_lines = off if off > 0 else total
    full = read_lines >= total

    header = (
        f"{links}\n"
        f"[полный файл] {path} — строк: {total}, "
        f"чанк: {auto_lines} строк (~{SAFE_CHUNK_BYTES} B), "
        f"прочитано: {read_lines}/{total}, байт: {collected_bytes}"
    )
    tail = "\n(конец файла)" if full else ""
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
    err = _validate_ref_inputs(owner, repo, path)
    if err:
        return err
    if not pattern:
        return "❌ Не указан pattern."
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
