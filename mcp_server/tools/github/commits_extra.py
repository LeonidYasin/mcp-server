"""MCP tools: extra commit / file inspection."""

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


@mcp_tool(
    name="get_commit_diff",
    description="Unified diff конкретного коммита",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "sha": {"type": "string", "description": "SHA коммита"},
        "max_files": {"type": "integer", "description": "Сколько файлов показать (по умолчанию 20)"},
    },
    required=["owner", "repo", "sha"],
)
def get_commit_diff(client: GitHubClient, **kwargs) -> str:
    resp = client._request(
        "GET",
        f"{GitHubClient.BASE_URL}/repos/{kwargs['owner']}/{kwargs['repo']}/commits/{kwargs['sha']}",
        headers={"Accept": "application/vnd.github.v3.diff"},
    )
    diff = resp.text
    limit = int(kwargs.get("max_files", 20))
    # limit by number of "diff --git" blocks
    parts = diff.split("diff --git ")
    if len(parts) > limit + 1:
        diff = "diff --git ".join(parts[: limit + 1]) + f"\n\n[...ещё {len(parts) - limit - 1} файлов]"
    return diff


@mcp_tool(
    name="list_directory",
    description="Список файлов в директории репозитория (по пути)",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "path": {"type": "string", "description": "Путь директории (пусто = корень)"},
        "ref": {"type": "string", "description": "Ветка/коммит (по умолчанию main)"},
    },
    required=["owner", "repo"],
)
def list_directory(client: GitHubClient, **kwargs) -> str:
    path = (kwargs.get("path") or "").strip("/")
    ref = kwargs.get("ref", "main")
    url = f"{GitHubClient.BASE_URL}/repos/{kwargs['owner']}/{kwargs['repo']}/contents/{path}"
    resp = client._request("GET", url, params={"ref": ref})
    items = resp.json()
    if isinstance(items, dict):
        return f"Не директория или не найдено: {items.get('message', '')}"
    lines = [f"{path or '/'} @ {ref} — {len(items)} элементов:"]
    for it in items:
        icon = "📁" if it["type"] == "dir" else "📄"
        lines.append(f"  {icon} {it['name']} ({it.get('size', '-')} b)")
    return "\n".join(lines)


@mcp_tool(
    name="get_file_blame",
    description="Показывает, кто последний менял строки файла (через GitHub API: коммиты по файлу)",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "path": {"type": "string"},
        "ref": {"type": "string", "description": "Ветка/коммит (по умолчанию main)"},
        "limit": {"type": "integer", "description": "Сколько коммитов (по умолчанию 20)"},
    },
    required=["owner", "repo", "path"],
)
def get_file_blame(client: GitHubClient, **kwargs) -> str:
    resp = client._request(
        "GET",
        f"{GitHubClient.BASE_URL}/repos/{kwargs['owner']}/{kwargs['repo']}/commits",
        params={
            "path": kwargs["path"],
            "sha": kwargs.get("ref", "main"),
            "per_page": min(int(kwargs.get("limit", 20)), 100),
        },
    )
    commits = resp.json()
    if not isinstance(commits, list) or not commits:
        return "Коммитов по файлу не найдено"
    lines = [f"История {kwargs['path']} ({len(commits)} коммитов):"]
    for c in commits:
        author = (c.get("commit", {}).get("author") or {}).get("name", "?")
        date = (c.get("commit", {}).get("author") or {}).get("date", "?")
        msg = (c.get("commit", {}).get("message") or "").splitlines()[0]
        lines.append(f"  {c['sha'][:8]} {date} {author}: {msg}")
    return "\n".join(lines)
