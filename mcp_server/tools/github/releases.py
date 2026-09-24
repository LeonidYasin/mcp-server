"""MCP tools: GitHub releases."""

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


@mcp_tool(
    name="list_releases",
    description="Список релизов репозитория",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "limit": {"type": "integer", "description": "Сколько вернуть (по умолчанию 10)"},
    },
    required=["owner", "repo"],
)
def list_releases(client: GitHubClient, **kwargs) -> str:
    resp = client._request(
        "GET",
        f"/repos/{kwargs['owner']}/{kwargs['repo']}/releases",
        params={"per_page": min(int(kwargs.get("limit", 10)), 100)},
    )
    items = resp.json()
    if not items:
        return "Релизов нет"
    lines = [f"Релизы ({len(items)}):"]
    for r in items:
        lines.append(
            f"  {r['tag_name']} — {r.get('name') or ''} "
            f"({'draft' if r.get('draft') else 'published'}, {r.get('published_at') or '-'})"
        )
    return "\n".join(lines)


@mcp_tool(
    name="create_release",
    description="Создаёт релиз",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "tag_name": {"type": "string", "description": "Тег (например v1.0.0)"},
        "name": {"type": "string", "description": "Название релиза"},
        "body": {"type": "string", "description": "Описание"},
        "target_commitish": {"type": "string", "description": "Ветка/коммит (по умолчанию main)"},
        "draft": {"type": "boolean"},
        "prerelease": {"type": "boolean"},
    },
    required=["owner", "repo", "tag_name"],
)
def create_release(client: GitHubClient, **kwargs) -> str:
    payload = {"tag_name": kwargs["tag_name"]}
    for k in ("name", "body", "target_commitish"):
        if kwargs.get(k):
            payload[k] = kwargs[k]
    if kwargs.get("draft") is not None:
        payload["draft"] = bool(kwargs["draft"])
    if kwargs.get("prerelease") is not None:
        payload["prerelease"] = bool(kwargs["prerelease"])
    resp = client._request(
        "POST", f"/repos/{kwargs['owner']}/{kwargs['repo']}/releases", json=payload
    )
    data = resp.json()
    return f"✅ Релиз {data['tag_name']} создан: {data['html_url']}"


@mcp_tool(
    name="get_latest_release",
    description="Последний опубликованный релиз",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
    },
    required=["owner", "repo"],
)
def get_latest_release(client: GitHubClient, **kwargs) -> str:
    resp = client._request(
        "GET", f"/repos/{kwargs['owner']}/{kwargs['repo']}/releases/latest"
    )
    r = resp.json()
    return (
        f"{r['tag_name']} — {r.get('name') or ''}\n"
        f"Опубликован: {r.get('published_at')}\n"
        f"URL: {r['html_url']}\n\n"
        f"{(r.get('body') or '')[:2000]}"
    )
