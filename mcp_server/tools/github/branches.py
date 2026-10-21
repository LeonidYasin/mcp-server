"""MCP tools: GitHub branches."""

import json
import re
from urllib.parse import quote

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


def _branch_hint(owner: str, repo: str, ref: str, err: Exception) -> str:
    return (
        f"❌ Ветка/ref '{ref}' не найдена в {owner}/{repo}.\n"
        f"   GitHub: {err}\n"
        f"   Подсказка: вызови list_branches(owner='{owner}', repo='{repo}')."
    )


@mcp_tool(
    name="list_branches",
    description="Список веток репозитория (с пагинацией)",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "limit": {"type": "integer", "description": "Сколько вернуть на странице (по умолчанию 30, максимум 100)"},
        "page": {"type": "integer", "description": "Номер страницы (по умолчанию 1)"},
    },
    required=["owner", "repo"],
)
def list_branches(client: GitHubClient, **kwargs) -> str:
    page = max(int(kwargs.get("page", 1) or 1), 1)
    per_page = min(int(kwargs.get("limit", 30)), 100)
    resp = client._request(
        "GET",
        f"/repos/{kwargs['owner']}/{kwargs['repo']}/branches",
        params={"per_page": per_page, "page": page},
    )
    items = resp.json()
    if not items:
        return f"Веток нет (страница {page})"
    lines = [f"Ветки ({len(items)}) — страница {page}:"]
    for b in items:
        lines.append(f"  {b['name']} -> {b['commit']['sha'][:8]}")
    if len(items) == per_page:
        lines.append(f"... возможно, есть ещё — вызови с page={page + 1}")
    return "\n".join(lines)


@mcp_tool(
    name="get_branch",
    description="Информация о ветке",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "branch": {"type": "string"},
    },
    required=["owner", "repo", "branch"],
)
def get_branch(client: GitHubClient, **kwargs) -> str:
    resp = client._request(
        "GET", f"/repos/{kwargs['owner']}/{kwargs['repo']}/branches/{kwargs['branch']}"
    )
    b = resp.json()
    return (
        f"Ветка: {b['name']}\n"
        f"HEAD: {b['commit']['sha']}\n"
        f"Защищена: {b.get('protected', False)}"
    )


def _branch_http_status(error: Exception):
    """The client wraps HTTP errors; retain status via exception chaining."""
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        response = getattr(error, "response", None)
        status = getattr(response, "status_code", None)
        if type(status) is int:
            return status
        error = error.__cause__ or error.__context__
    return None


def _valid_new_branch(branch):
    if not isinstance(branch, str) or not branch or branch == "@":
        return False
    if (branch.startswith(("/", "-")) or branch.endswith(("/", "."))
            or ".." in branch or "@{" in branch or "//" in branch
            or re.search(r"[\x00-\x20\x7f~^:?*\\\[]", branch)):
        return False
    return all(not part.startswith(".") and not part.endswith(".lock")
               for part in branch.split("/"))


@mcp_tool(
    name="create_branch",
    description=(
        "Создаёт ветку от from_branch (ветка/ref/SHA, default main) или точного from_sha. "
        "SHA из доступного fork network сохраняет историю без merge. "
        "Существующая ветка — no-op только при совпадении SHA; никогда не перезаписывает ref."
    ),
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "branch": {"type": "string", "description": "Имя новой ветки"},
        "from_branch": {"type": "string", "description": "Ветка/ref/SHA (default main); не сочетать с from_sha"},
        "from_sha": {"type": "string", "pattern": "^[0-9a-fA-F]{40}$",
                     "description": "Точный 40-значный SHA коммита, в том числе из доступного форка"},
    },
    required=["owner", "repo", "branch"],
)
def create_branch(client: GitHubClient, **kwargs) -> str:
    owner, repo, branch = kwargs["owner"], kwargs["repo"], kwargs["branch"]
    if not _valid_new_branch(branch):
        raise ValueError("branch: недопустимое имя Git-ветки")
    if "from_sha" in kwargs and "from_branch" in kwargs:
        raise ValueError("Укажи только один источник: from_sha или from_branch")
    source = kwargs.get("from_sha") if "from_sha" in kwargs else kwargs.get("from_branch", "main")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("Источник должен быть непустой строкой")
    if "from_sha" in kwargs and not re.fullmatch(r"[0-9a-fA-F]{40}", source):
        raise ValueError("from_sha: требуется полный 40-значный SHA коммита")
    prefix = f"/repos/{owner}/{repo}"
    ref_path = f"{prefix}/git/ref/heads/{quote(branch, safe='')}"

    # Resolve a commit, not heads/<source>: this also accepts tags and fork SHAs.
    try:
        sha = client._request("GET", f"{prefix}/commits/{quote(source, safe='')}").json()["sha"]
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", sha):
            raise ValueError("GitHub не вернул полный SHA коммита")
        sha = sha.lower()
        if ("from_sha" in kwargs or re.fullmatch(r"[0-9a-fA-F]{40}", source)) and sha != source.lower():
            raise ValueError("GitHub вернул другой SHA")
    except Exception as error:
        return f"❌ Не удалось разрешить источник '{source}' в {owner}/{repo}: {error}"

    def read_ref():
        data = client._request("GET", ref_path).json()
        if data.get("ref") != f"refs/heads/{branch}" or data.get("object", {}).get("type") != "commit":
            raise ValueError("GitHub вернул неожиданный ref или тип объекта")
        return data["object"]["sha"]

    def existing_result(actual):
        if actual == sha:
            return f"ℹ️ Ветка '{branch}' уже существует на нужном SHA: {sha} (без изменений)"
        return (f"❌ Конфликт: ветка '{branch}' уже существует на SHA {actual}, "
                f"ожидался {sha}. Ветка не изменена.")

    try:
        return existing_result(read_ref())
    except Exception as error:
        # Auth, rate limit, transport and malformed responses are NOT absence.
        if _branch_http_status(error) != 404:
            return f"❌ Не удалось проверить целевую ветку '{branch}': {error}"

    try:
        client._request("POST", f"{prefix}/git/refs",
                        json={"ref": f"refs/heads/{branch}", "sha": sha})
    except Exception as error:
        # A concurrent creator may have won. No second POST and no PATCH/force.
        if _branch_http_status(error) == 422:
            try:
                return existing_result(read_ref())
            except Exception:
                pass
        return f"❌ Создание ветки '{branch}' не подтверждено: {error}. Проверь get_branch перед повтором."

    try:
        actual = read_ref()
        if actual != sha:
            raise ValueError(f"Ожидался {sha}, получен {actual}; ref не перезаписан")
    except Exception as error:
        return f"⚠️ GitHub принял создание '{branch}', но read-back не подтверждён: {error}"
    return f"✅ Ветка '{branch}' создана из '{source}'. SHA: {sha}. Read-back подтверждён."


@mcp_tool(
    name="delete_branch",
    description="Удаляет ветку",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "branch": {"type": "string"},
    },
    required=["owner", "repo", "branch"],
)
def delete_branch(client: GitHubClient, **kwargs) -> str:
    client._request(
        "DELETE",
        f"/repos/{kwargs['owner']}/{kwargs['repo']}/git/refs/heads/{kwargs['branch']}",
    )
    return f"✅ Ветка '{kwargs['branch']}' удалена"


def _compare_limit(kwargs: dict, name: str, default: int, maximum: int) -> int:
    value = kwargs.get(name, default)
    # bool is an int subclass, but not a valid integer tool argument.
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(f"{name}: требуется целое число от 0 до {maximum}")
    return value


def _bounded_compare_patch(files: list, max_bytes: int, max_lines: int):
    """One UTF-8 budget across all patches, including diff headers/newlines."""
    chunks = []
    used_bytes = used_lines = unavailable = 0
    truncated = False
    for index, file in enumerate(files):
        patch = file.get("patch")
        if not patch:
            unavailable += 1
            continue
        text = f"diff --git a/{file['filename']} b/{file['filename']}\n{patch}"
        for line in text.splitlines():
            raw = (line + "\n").encode("utf-8")
            remaining = max_bytes - used_bytes
            if used_lines >= max_lines or remaining <= 0:
                truncated = True
                break
            if len(raw) > remaining:
                # Never cut a multibyte character in half.
                chunk = raw[:remaining].decode("utf-8", errors="ignore")
                chunks.append(chunk)
                used_bytes += len(chunk.encode("utf-8"))
                used_lines += bool(chunk)
                truncated = True
                break
            chunks.append(raw.decode("utf-8"))
            used_bytes += len(raw)
            used_lines += 1
        # Continue to count unavailable patches, but no more output after truncation.
        if truncated:
            unavailable += sum(not f.get("patch") for f in files[index + 1:])
            break
    return "".join(chunks), used_bytes, used_lines, truncated, unavailable


@mcp_tool(
    name="compare_branches",
    description=(
        "Сравнивает base...head (three-dot, изменения head от merge-base, не diff двух деревьев). "
        "max_files ограничивает и список файлов, и patches. SHA и признаки усечения в metadata. "
        "include_patch=True добавляет unified diff с общим лимитом UTF-8 bytes/lines."
    ),
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "base": {"type": "string", "description": "Базовая ветка/ref"},
        "head": {"type": "string", "description": "Ветка/ref для сравнения"},
        "include_patch": {"type": "boolean", "description": "Добавить unified diff (по умолчанию false)"},
        "max_files": {"type": "integer", "minimum": 0, "maximum": 300, "default": 10,
                      "description": "Лимит файлов для summary И patches; 0 — только metadata"},
        "max_patch_bytes": {"type": "integer", "minimum": 0, "maximum": 262144, "default": 65536,
                            "description": "Общий лимит UTF-8 bytes patches, включая diff headers"},
        "max_patch_lines": {"type": "integer", "minimum": 0, "maximum": 5000, "default": 1000,
                            "description": "Общий лимит строк patches, включая diff headers"},
    },
    required=["owner", "repo", "base", "head"],
)
def compare_branches(client: GitHubClient, **kwargs) -> str:
    limit = _compare_limit(kwargs, "max_files", 10, 300)
    max_bytes = _compare_limit(kwargs, "max_patch_bytes", 65536, 262144)
    max_lines = _compare_limit(kwargs, "max_patch_lines", 1000, 5000)
    prefix = f"/repos/{kwargs['owner']}/{kwargs['repo']}"
    # Resolve each ref once, then compare immutable SHAs. Additional GETs avoid
    # guessing head SHA from a potentially truncated commits list.
    shas = {}
    for role in ("base", "head"):
        data = client._request("GET", f"{prefix}/commits/{quote(kwargs[role], safe='')}").json()
        sha = data.get("sha")
        if not isinstance(sha, str) or not sha:
            raise ValueError(f"GitHub не вернул SHA для {role}")
        shas[role] = sha
    resp = client._request("GET", f"{prefix}/compare/{shas['base']}...{shas['head']}")
    d = resp.json()
    files = d.get("files") or []
    selected = files[:limit]
    # GitHub compare returns at most 300 files, without an exact total for
    # larger comparisons. At the cap, completeness is deliberately unknown.
    files_complete = "files" in d and len(files) < 300
    total_files = len(files) if files_complete else None
    commits = d.get("commits") or []
    total_commits = d.get("total_commits")
    commits_complete = (
        isinstance(total_commits, int) and len(commits) == total_commits
        and 'rel="next"' not in resp.headers.get("Link", "")
    )
    info = {
        "base_sha": shas["base"], "head_sha": shas["head"],
        "merge_base_sha": (d.get("merge_base_commit") or {}).get("sha"),
        "total_files": total_files, "fetched_files": len(files),
        "returned_files": len(selected),
        "truncated": len(selected) < len(files) or not files_complete,
        "upstream_files_complete": files_complete,
        "total_commits": total_commits, "fetched_commits": len(commits),
        "upstream_commits_complete": commits_complete,
    }
    patch_output = None
    if kwargs.get("include_patch"):
        patch_output, byte_count, line_count, truncated, unavailable = _bounded_compare_patch(
            selected, max_bytes, max_lines
        )
        info.update({
            "patch_bytes": byte_count, "patch_lines": line_count,
            "patch_truncated": truncated, "patch_unavailable_files": unavailable,
            "patch_complete": not (truncated or unavailable or info["truncated"]),
        })
    lines = [
        f"{kwargs['base']}...{kwargs['head']}",
        f"Статус: {d.get('status')} | ahead_by={d.get('ahead_by')} behind_by={d.get('behind_by')}",
        f"Коммитов: {total_commits} | Файлов: {total_files if total_files is not None else 'unknown'}",
        "metadata: " + json.dumps(info, ensure_ascii=False, sort_keys=True),
        "Three-dot: изменения head от merge-base; ahead_by после squash не означает новые функции.",
    ]
    for file in selected:
        lines.append(f"  [{file['status']}] {file['filename']} (+{file.get('additions', 0)}/-{file.get('deletions', 0)})")
    if len(selected) < len(files):
        lines.append(f"... ещё {len(files) - len(selected)} полученных файлов не показано")
    if not files_complete:
        lines.append("GitHub: полный список файлов не подтверждён; total_files=unknown (лимит API 300).")
    if not commits_complete:
        lines.append("GitHub: список коммитов неполный или его полнота не подтверждена.")
    result = "\n".join(lines)
    if patch_output is not None:
        result += "\n\n--- patch ---\n" + patch_output
    return result


@mcp_tool(
    name="merge_branches",
    description="Мержит одну ветку в другую (без PR)",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "base": {"type": "string", "description": "Целевая ветка (куда)"},
        "head": {"type": "string", "description": "Источник (откуда)"},
        "commit_message": {"type": "string"},
    },
    required=["owner", "repo", "base", "head"],
)
def merge_branches(client: GitHubClient, **kwargs) -> str:
    payload = {"base": kwargs["base"], "head": kwargs["head"]}
    if kwargs.get("commit_message"):
        payload["commit_message"] = kwargs["commit_message"]
    resp = client._request(
        "POST", f"/repos/{kwargs['owner']}/{kwargs['repo']}/merges", json=payload
    )
    if resp.status_code == 204:
        return f"ℹ️ Ветки уже идентичны ({kwargs['base']} == {kwargs['head']})"
    d = resp.json()
    return f"✅ Merge: {kwargs['head']} -> {kwargs['base']}\nSHA: {d.get('sha', '')[:8]}\n{d.get('commit', {}).get('message', '')}"
