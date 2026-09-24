"""MCP tools: GitHub pull requests."""

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


@mcp_tool(
    name="create_pull_request",
    description="Создаёт pull request в репозитории",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "title": {"type": "string", "description": "Заголовок PR"},
        "head": {"type": "string", "description": "Ветка-источник"},
        "base": {"type": "string", "description": "Целевая ветка"},
        "body": {"type": "string", "description": "Описание PR"},
        "draft": {"type": "boolean", "description": "Создать как draft"},
    },
    required=["owner", "repo", "title", "head", "base"],
)
def create_pull_request(client: GitHubClient, **kwargs) -> str:
    payload = {
        "title": kwargs["title"],
        "head": kwargs["head"],
        "base": kwargs["base"],
    }
    if kwargs.get("body"):
        payload["body"] = kwargs["body"]
    if kwargs.get("draft") is not None:
        payload["draft"] = bool(kwargs["draft"])
    resp = client._request(
        "POST", f"/repos/{kwargs['owner']}/{kwargs['repo']}/pulls", json=payload
    )
    data = resp.json()
    return f"✅ PR #{data['number']} создан: {data['html_url']}"


@mcp_tool(
    name="list_pull_requests",
    description="Список pull requests репозитория",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "state": {"type": "string", "description": "open|closed|all (по умолчанию open)"},
        "limit": {"type": "integer", "description": "Сколько вернуть (по умолчанию 20)"},
    },
    required=["owner", "repo"],
)
def list_pull_requests(client: GitHubClient, **kwargs) -> str:
    state = kwargs.get("state", "open")
    limit = int(kwargs.get("limit", 20))
    resp = client._request(
        "GET",
        f"/repos/{kwargs['owner']}/{kwargs['repo']}/pulls",
        params={"state": state, "per_page": min(limit, 100)},
    )
    items = resp.json()
    if not items:
        return f"PR ({state}): нет"
    lines = [f"PR ({state}), всего {len(items)}:"]
    for pr in items:
        lines.append(
            f"  #{pr['number']} [{pr['state']}] {pr['title']} — {pr['html_url']}"
        )
    return "\n".join(lines)


@mcp_tool(
    name="get_pull_request",
    description="Детали pull request",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "number": {"type": "integer", "description": "Номер PR"},
    },
    required=["owner", "repo", "number"],
)
def get_pull_request(client: GitHubClient, **kwargs) -> str:
    resp = client._request(
        "GET", f"/repos/{kwargs['owner']}/{kwargs['repo']}/pulls/{kwargs['number']}"
    )
    pr = resp.json()
    return (
        f"PR #{pr['number']}: {pr['title']}\n"
        f"Состояние: {pr['state']} (merged={pr.get('merged')})\n"
        f"Автор: {pr['user']['login']}\n"
        f"Ветки: {pr['head']['ref']} -> {pr['base']['ref']}\n"
        f"Изменений: +{pr.get('additions', 0)} / -{pr.get('deletions', 0)} в {pr.get('changed_files', 0)} файлах\n"
        f"URL: {pr['html_url']}\n\n"
        f"{(pr.get('body') or '')[:2000]}"
    )


@mcp_tool(
    name="merge_pull_request",
    description="Мержит pull request",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "number": {"type": "integer"},
        "merge_method": {"type": "string", "description": "merge|squash|rebase"},
        "commit_title": {"type": "string"},
    },
    required=["owner", "repo", "number"],
)
def merge_pull_request(client: GitHubClient, **kwargs) -> str:
    payload = {}
    if kwargs.get("merge_method"):
        payload["merge_method"] = kwargs["merge_method"]
    if kwargs.get("commit_title"):
        payload["commit_title"] = kwargs["commit_title"]
    resp = client._request(
        "PUT",
        f"/repos/{kwargs['owner']}/{kwargs['repo']}/pulls/{kwargs['number']}/merge",
        json=payload,
    )
    data = resp.json()
    if data.get("merged"):
        return f"✅ PR #{kwargs['number']} смержен: {data.get('sha', '')}"
    return f"❌ Не удалось смержить: {data.get('message', 'unknown')}"


@mcp_tool(
    name="close_pull_request",
    description="Закрывает pull request без мержа",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "number": {"type": "integer"},
    },
    required=["owner", "repo", "number"],
)
def close_pull_request(client: GitHubClient, **kwargs) -> str:
    client._request(
        "PATCH",
        f"/repos/{kwargs['owner']}/{kwargs['repo']}/pulls/{kwargs['number']}",
        json={"state": "closed"},
    )
    return f"✅ PR #{kwargs['number']} закрыт"


@mcp_tool(
    name="add_pr_comment",
    description="Добавляет комментарий к pull request или issue",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "number": {"type": "integer", "description": "Номер PR/issue"},
        "body": {"type": "string", "description": "Текст комментария"},
    },
    required=["owner", "repo", "number", "body"],
)
def add_pr_comment(client: GitHubClient, **kwargs) -> str:
    resp = client._request(
        "POST",
        f"/repos/{kwargs['owner']}/{kwargs['repo']}/issues/{kwargs['number']}/comments",
        json={"body": kwargs["body"]},
    )
    return f"✅ Комментарий добавлен: {resp.json().get('html_url', '')}"


@mcp_tool(
    name="request_pr_review",
    description="Запрашивает ревьюеров на pull request",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "number": {"type": "integer"},
        "reviewers": {"type": "array", "items": {"type": "string"}, "description": "GitHub-логины"},
    },
    required=["owner", "repo", "number", "reviewers"],
)
def request_pr_review(client: GitHubClient, **kwargs) -> str:
    reviewers = kwargs["reviewers"]
    if isinstance(reviewers, str):
        reviewers = [r.strip() for r in reviewers.split(",") if r.strip()]
    client._request(
        "POST",
        f"/repos/{kwargs['owner']}/{kwargs['repo']}/pulls/{kwargs['number']}/requested_reviewers",
        json={"reviewers": reviewers},
    )
    return f"✅ Запрошено ревью у: {', '.join(reviewers)}"
