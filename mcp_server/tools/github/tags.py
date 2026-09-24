"""MCP tools: GitHub tags."""

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


@mcp_tool(
    name="list_tags",
    description="Список git-тегов репозитория (с пагинацией)",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "limit": {"type": "integer", "description": "Сколько вернуть на странице (по умолчанию 30, максимум 100)"},
        "page": {"type": "integer", "description": "Номер страницы (по умолчанию 1)"},
    },
    required=["owner", "repo"],
)
def list_tags(client: GitHubClient, **kwargs) -> str:
    page = max(int(kwargs.get("page", 1) or 1), 1)
    per_page = min(int(kwargs.get("limit", 30)), 100)
    resp = client._request(
        "GET",
        f"/repos/{kwargs['owner']}/{kwargs['repo']}/tags",
        params={"per_page": per_page, "page": page},
    )
    items = resp.json()
    if not items:
        return f"Тегов нет (страница {page})"
    lines = [f"Теги ({len(items)}) — страница {page}:"]
    for t in items:
        lines.append(f"  {t['name']} -> {t['commit']['sha'][:8]}")
    if len(items) == per_page:
        lines.append(f"... возможно, есть ещё — вызови с page={page + 1}")
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


@mcp_tool(
    name="delete_tag",
    description="Удаляет git-тег по имени",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "tag": {"type": "string", "description": "Имя тега"},
    },
    required=["owner", "repo", "tag"],
)
def delete_tag(client: GitHubClient, **kwargs) -> str:
    tag = kwargs["tag"]
    try:
        client._request(
            "DELETE",
            f"/repos/{kwargs['owner']}/{kwargs['repo']}/git/refs/tags/{tag}",
        )
    except Exception as e:
        return (
            f"❌ Не удалось удалить тег '{tag}' в {kwargs['owner']}/{kwargs['repo']}: {e}\n"
            f"   Проверь имя тега (list_tags)."
        )
    return f"✅ Тег '{tag}' удалён"
