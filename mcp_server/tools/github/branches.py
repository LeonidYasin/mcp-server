"""MCP tools: GitHub branches."""

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


@mcp_tool(
    name="compare_branches",
    description=(
        "Сравнивает две ветки (base...head): коммиты и файлы. "
        "include_patch=True добавляет unified diff по изменённым файлам."
    ),
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "base": {"type": "string", "description": "Базовая ветка"},
        "head": {"type": "string", "description": "Ветка для сравнения"},
        "include_patch": {"type": "boolean", "description": "Добавить unified diff (по умолчанию false)"},
        "max_files": {"type": "integer", "description": "Сколько файлов показать в диффе (по умолчанию 10)"},
    },
    required=["owner", "repo", "base", "head"],
)
def compare_branches(client: GitHubClient, **kwargs) -> str:
    resp = client._request(
        "GET",
        f"/repos/{kwargs['owner']}/{kwargs['repo']}/compare/{kwargs['base']}...{kwargs['head']}",
    )
    d = resp.json()
    lines = [
        f"{kwargs['base']}...{kwargs['head']}",
        f"Статус: {d.get('status')} | ahead_by={d.get('ahead_by')} behind_by={d.get('behind_by')}",
        f"Коммитов: {d.get('total_commits')} | Файлов: {len(d.get('files', []))}",
    ]
    files = d.get("files", [])
    for f in files[:30]:
        lines.append(f"  [{f['status']}] {f['filename']} (+{f.get('additions', 0)}/-{f.get('deletions', 0)})")

    if kwargs.get("include_patch"):
        limit = max(int(kwargs.get("max_files", 10)), 1)
        lines.append("")
        lines.append("--- patch ---")
        for f in files[:limit]:
            patch = f.get("patch")
            if not patch:
                continue
            lines.append(f"diff --git a/{f['filename']} b/{f['filename']}")
            lines.append(patch)
        if len(files) > limit:
            lines.append(f"... ещё {len(files) - limit} файлов не показано")

    return "\n".join(lines)


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
