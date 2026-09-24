"""MCP tools: repository info and stats."""

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


@mcp_tool(
    name="get_repo_info",
    description="Основная информация о репозитории",
    parameters={"owner": {"type": "string"}, "repo": {"type": "string"}},
    required=["owner", "repo"],
)
def get_repo_info(client: GitHubClient, **kwargs) -> str:
    d = client._request("GET", f"/repos/{kwargs['owner']}/{kwargs['repo']}").json()
    return (
        f"{d['full_name']}\n"
        f"Описание: {d.get('description') or '-'}\n"
        f"Язык: {d.get('language')}\n"
        f"⭐ {d.get('stargazers_count')} | 🍴 {d.get('forks_count')} | 👁 {d.get('watchers_count')}\n"
        f"Issues: {d.get('open_issues_count')} | Ветка по умолчанию: {d.get('default_branch')}\n"
        f"Приватный: {d.get('private')} | Архив: {d.get('archived')}\n"
        f"Создан: {d.get('created_at')} | Обновлён: {d.get('updated_at')}\n"
        f"URL: {d['html_url']}"
    )


@mcp_tool(
    name="get_repo_topics",
    description="Топики репозитория",
    parameters={"owner": {"type": "string"}, "repo": {"type": "string"}},
    required=["owner", "repo"],
)
def get_repo_topics(client: GitHubClient, **kwargs) -> str:
    d = client._request(
        "GET",
        f"/repos/{kwargs['owner']}/{kwargs['repo']}/topics",
        headers={"Accept": "application/vnd.github.mercy-preview+json"},
    ).json()
    names = d.get("names", [])
    return f"Топики ({len(names)}): {', '.join(names) if names else '—'}"


@mcp_tool(
    name="get_repo_languages",
    description="Разбивка репозитория по языкам (в байтах)",
    parameters={"owner": {"type": "string"}, "repo": {"type": "string"}},
    required=["owner", "repo"],
)
def get_repo_languages(client: GitHubClient, **kwargs) -> str:
    d = client._request(
        "GET", f"/repos/{kwargs['owner']}/{kwargs['repo']}/languages"
    ).json()
    if not d:
        return "Языки не определены"
    total = sum(d.values())
    lines = ["Языки:"]
    for lang, size in sorted(d.items(), key=lambda x: -x[1]):
        pct = (size / total * 100) if total else 0
        lines.append(f"  {lang}: {pct:.1f}% ({size} bytes)")
    return "\n".join(lines)


@mcp_tool(
    name="list_repo_contributors",
    description="Контрибьюторы репозитория (по числу коммитов)",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "limit": {"type": "integer", "description": "Сколько вернуть (по умолчанию 20)"},
    },
    required=["owner", "repo"],
)
def list_repo_contributors(client: GitHubClient, **kwargs) -> str:
    resp = client._request(
        "GET",
        f"/repos/{kwargs['owner']}/{kwargs['repo']}/contributors",
        params={"per_page": min(int(kwargs.get("limit", 20)), 100)},
    )
    items = resp.json()
    if not isinstance(items, list) or not items:
        return "Контрибьюторов нет"
    lines = [f"Контрибьюторы ({len(items)}):"]
    for c in items:
        lines.append(f"  {c['login']}: {c.get('contributions')} коммитов")
    return "\n".join(lines)
