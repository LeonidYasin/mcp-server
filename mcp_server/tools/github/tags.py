"""MCP tools: GitHub tags."""

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


@mcp_tool(
    name="list_tags",
    description="Список git-тегов репозитория",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "limit": {"type": "integer"},
    },
    required=["owner", "repo"],
)
def list_tags(client: GitHubClient, **kwargs) -> str:
    resp = client._request(
        "GET",
        f"/repos/{kwargs['owner']}/{kwargs['repo']}/tags",
        params={"per_page": min(int(kwargs.get("limit", 30)), 100)},
    )
    items = resp.json()
    if not items:
        return "Тегов нет"
    lines = [f"Теги ({len(items)}):"]
    for t in items:
        lines.append(f"  {t['name']} -> {t['commit']['sha'][:8]}")
    return "\n".join(lines)


@mcp_tool(
    name="create_tag",
    description="Создаёт git-тег (annotated)",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "tag": {"type": "string", "description": "Имя тега"},
        "message": {"type": "string", "description": "Сообщение аннотации"},
        "sha": {"type": "string", "description": "Коммит (по умолчанию HEAD целевой ветки)"},
        "branch": {"type": "string", "description": "Ветка для HEAD, если sha не задан"},
    },
    required=["owner", "repo", "tag"],
)
def create_tag(client: GitHubClient, **kwargs) -> str:
    sha = kwargs.get("sha")
    if not sha:
        branch = kwargs.get("branch", "main")
        ref = client._request(
            "GET", f"/repos/{kwargs['owner']}/{kwargs['repo']}/git/ref/heads/{branch}"
        ).json()
        sha = ref["object"]["sha"]
    payload = {
        "tag": kwargs["tag"],
        "message": kwargs.get("message", kwargs["tag"]),
        "object": sha,
        "type": "commit",
    }
    tag_obj = client._request(
        "POST", f"/repos/{kwargs['owner']}/{kwargs['repo']}/git/tags", json=payload
    ).json()
    client._request(
        "POST",
        f"/repos/{kwargs['owner']}/{kwargs['repo']}/git/refs",
        json={"ref": f"refs/tags/{kwargs['tag']}", "sha": tag_obj["sha"]},
    )
    return f"✅ Тег {kwargs['tag']} создан на {sha[:8]}"
