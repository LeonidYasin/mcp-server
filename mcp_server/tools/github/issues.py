"""MCP tools: GitHub issues."""

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


@mcp_tool(
    name="create_issue",
    description="Создаёт issue в репозитории",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "title": {"type": "string", "description": "Заголовок"},
        "body": {"type": "string", "description": "Описание"},
        "labels": {"type": "array", "items": {"type": "string"}, "description": "Метки"},
        "assignees": {"type": "array", "items": {"type": "string"}, "description": "Исполнители"},
    },
    required=["owner", "repo", "title"],
)
def create_issue(client: GitHubClient, **kwargs) -> str:
    payload = {"title": kwargs["title"]}
    if kwargs.get("body"):
        payload["body"] = kwargs["body"]
    if kwargs.get("labels"):
        payload["labels"] = kwargs["labels"]
    if kwargs.get("assignees"):
        payload["assignees"] = kwargs["assignees"]
    resp = client._request(
        "POST", f"/repos/{kwargs['owner']}/{kwargs['repo']}/issues", json=payload
    )
    data = resp.json()
    return f"✅ Issue #{data['number']} создан: {data['html_url']}"


@mcp_tool(
    name="list_issues",
    description="Список issues репозитория",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "state": {"type": "string", "description": "open|closed|all"},
        "labels": {"type": "string", "description": "Метки через запятую"},
        "limit": {"type": "integer"},
    },
    required=["owner", "repo"],
)
def list_issues(client: GitHubClient, **kwargs) -> str:
    params = {
        "state": kwargs.get("state", "open"),
        "per_page": min(int(kwargs.get("limit", 20)), 100),
    }
    if kwargs.get("labels"):
        params["labels"] = kwargs["labels"]
    resp = client._request(
        "GET", f"/repos/{kwargs['owner']}/{kwargs['repo']}/issues", params=params
    )
    items = [i for i in resp.json() if "pull_request" not in i]
    if not items:
        return "Issues: нет"
    lines = [f"Issues ({params['state']}), всего {len(items)}:"]
    for it in items:
        labels = ",".join(l["name"] for l in it.get("labels", []))
        lines.append(f"  #{it['number']} [{it['state']}] {it['title']} {('#'+labels) if labels else ''}")
    return "\n".join(lines)


@mcp_tool(
    name="get_issue",
    description="Детали issue",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "number": {"type": "integer"},
    },
    required=["owner", "repo", "number"],
)
def get_issue(client: GitHubClient, **kwargs) -> str:
    resp = client._request(
        "GET", f"/repos/{kwargs['owner']}/{kwargs['repo']}/issues/{kwargs['number']}"
    )
    it = resp.json()
    labels = ", ".join(l["name"] for l in it.get("labels", []))
    return (
        f"Issue #{it['number']}: {it['title']}\n"
        f"Состояние: {it['state']}\n"
        f"Автор: {it['user']['login']}\n"
        f"Метки: {labels or '-'}\n"
        f"URL: {it['html_url']}\n\n"
        f"{(it.get('body') or '')[:2000]}"
    )


@mcp_tool(
    name="close_issue",
    description="Закрывает issue",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "number": {"type": "integer"},
        "reason": {"type": "string", "description": "completed|not_planned"},
    },
    required=["owner", "repo", "number"],
)
def close_issue(client: GitHubClient, **kwargs) -> str:
    payload = {"state": "closed"}
    if kwargs.get("reason"):
        payload["state_reason"] = kwargs["reason"]
    client._request(
        "PATCH",
        f"/repos/{kwargs['owner']}/{kwargs['repo']}/issues/{kwargs['number']}",
        json=payload,
    )
    return f"✅ Issue #{kwargs['number']} закрыт"


@mcp_tool(
    name="add_issue_comment",
    description="Добавляет комментарий к issue",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "number": {"type": "integer"},
        "body": {"type": "string"},
    },
    required=["owner", "repo", "number", "body"],
)
def add_issue_comment(client: GitHubClient, **kwargs) -> str:
    resp = client._request(
        "POST",
        f"/repos/{kwargs['owner']}/{kwargs['repo']}/issues/{kwargs['number']}/comments",
        json={"body": kwargs["body"]},
    )
    return f"✅ Комментарий: {resp.json().get('html_url', '')}"


@mcp_tool(
    name="add_labels",
    description="Добавляет метки к issue/PR",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "number": {"type": "integer"},
        "labels": {"type": "array", "items": {"type": "string"}},
    },
    required=["owner", "repo", "number", "labels"],
)
def add_labels(client: GitHubClient, **kwargs) -> str:
    client._request(
        "POST",
        f"/repos/{kwargs['owner']}/{kwargs['repo']}/issues/{kwargs['number']}/labels",
        json={"labels": kwargs["labels"]},
    )
    return f"✅ Метки добавлены: {', '.join(kwargs['labels'])}"
