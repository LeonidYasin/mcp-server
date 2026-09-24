"""MCP tools: GitHub Gists."""

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


@mcp_tool(
    name="create_gist",
    description="Создаёт gist (публичный или секретный)",
    parameters={
        "filename": {"type": "string", "description": "Имя файла в gist"},
        "content": {"type": "string", "description": "Содержимое"},
        "description": {"type": "string"},
        "public": {"type": "boolean", "description": "Публичный (по умолчанию false)"},
    },
    required=["filename", "content"],
)
def create_gist(client: GitHubClient, **kwargs) -> str:
    payload = {
        "files": {kwargs["filename"]: {"content": kwargs["content"]}},
        "public": bool(kwargs.get("public", False)),
    }
    if kwargs.get("description"):
        payload["description"] = kwargs["description"]
    resp = client._request("POST", "/gists", json=payload)
    d = resp.json()
    return f"✅ Gist создан: {d['html_url']} (id={d['id']})"


@mcp_tool(
    name="list_gists",
    description="Список gist текущего пользователя",
    parameters={"limit": {"type": "integer", "description": "Сколько вернуть (по умолчанию 20)"}},
    required=[],
)
def list_gists(client: GitHubClient, **kwargs) -> str:
    resp = client._request(
        "GET", "/gists", params={"per_page": min(int(kwargs.get("limit", 20)), 100)}
    )
    items = resp.json()
    if not items:
        return "Gist'ов нет"
    lines = [f"Gist'ы ({len(items)}):"]
    for g in items:
        files = ", ".join(g.get("files", {}).keys())
        lines.append(f"  {g['id']} [{'pub' if g.get('public') else 'sec'}] {files} — {g['html_url']}")
    return "\n".join(lines)


@mcp_tool(
    name="get_gist",
    description="Получает gist по id (содержимое файлов)",
    parameters={"gist_id": {"type": "string"}},
    required=["gist_id"],
)
def get_gist(client: GitHubClient, **kwargs) -> str:
    resp = client._request("GET", f"/gists/{kwargs['gist_id']}")
    g = resp.json()
    lines = [f"Gist {g['id']}: {g.get('description') or ''}", f"URL: {g['html_url']}", ""]
    for name, f in g.get("files", {}).items():
        lines.append(f"--- {name} ---")
        lines.append((f.get("content") or "")[:4000])
    return "\n".join(lines)


@mcp_tool(
    name="update_gist",
    description="Обновляет gist (добавляет/меняет файл)",
    parameters={
        "gist_id": {"type": "string"},
        "filename": {"type": "string"},
        "content": {"type": "string"},
        "description": {"type": "string"},
    },
    required=["gist_id", "filename", "content"],
)
def update_gist(client: GitHubClient, **kwargs) -> str:
    payload = {"files": {kwargs["filename"]: {"content": kwargs["content"]}}}
    if kwargs.get("description"):
        payload["description"] = kwargs["description"]
    resp = client._request("PATCH", f"/gists/{kwargs['gist_id']}", json=payload)
    d = resp.json()
    return f"✅ Gist обновлён: {d['html_url']}"
