"""MCP tools: GitHub branches."""

import json
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


@mcp_tool(
    name="create_branch",
    description=(
        "Создаёт новую ветку от указанного ref (по умолчанию — main). "
        "Идемпотентен: если ветка уже существует — вернёт её SHA без ошибки."
    ),
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "branch": {"type": "string", "description": "Имя новой ветки"},
        "from_branch": {"type": "string", "description": "Источник (по умолчанию main)"},
    },
    required=["owner", "repo", "branch"],
)
def create_branch(client: GitHubClient, **kwargs) -> str:
    owner, repo, branch = kwargs["owner"], kwargs["repo"], kwargs["branch"]
    from_branch = kwargs.get("from_branch") or "main"

    # 0. Если ветка уже есть — не ошибка, а «уже существует» + SHA.
    try:
        existing = client._request(
            "GET", f"/repos/{owner}/{repo}/git/ref/heads/{branch}"
        ).json()
        sha = existing["object"]["sha"]
        return f"ℹ️ Ветка '{branch}' уже существует ({sha[:8]})"
    except Exception:
        pass

    # 1. SHA источника.
    try:
        ref_resp = client._request(
            "GET", f"/repos/{owner}/{repo}/git/ref/heads/{from_branch}"
        )
        sha = ref_resp.json()["object"]["sha"]
    except Exception as e:
        return (
            f"❌ Не удалось получить '{from_branch}' в {owner}/{repo}: {e}\n"
            f"   Проверь имя исходной ветки (list_branches) — часто это main, но бывает master."
        )

    # 2. Создаём ref.
    try:
        client._request(
            "POST",
            f"/repos/{owner}/{repo}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": sha},
        )
    except Exception as e:
        return f"❌ Не удалось создать ветку '{branch}': {e}"

    return f"✅ Ветка '{branch}' создана из '{from_branch}' ({sha[:8]})"


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
