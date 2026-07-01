"""MCP tools: file operations (create, read, delete)."""

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


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
    description="Получает содержимое файла из репозитория",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "path": {"type": "string", "description": "Путь к файлу"},
        "ref": {"type": "string", "description": "Git ref (ветка, тег, коммит)"},
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
    if "content" in data:
        try:
            return base64.b64decode(data["content"]).decode("utf-8")
        except Exception:
            return f"[Binary: {data.get('size', '?')} bytes]"
    return json.dumps(data, indent=2, ensure_ascii=False)


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
