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
    description="Список pull requests репозитория (с пагинацией)",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "state": {"type": "string", "description": "open|closed|all (по умолчанию open)"},
        "limit": {"type": "integer", "description": "Сколько вернуть на странице (по умолчанию 20, максимум 100)"},
        "page": {"type": "integer", "description": "Номер страницы (по умолчанию 1)"},
    },
    required=["owner", "repo"],
)
def list_pull_requests(client: GitHubClient, **kwargs) -> str:
    state = kwargs.get("state", "open")
    limit = max(1, min(int(kwargs.get("limit", 20)), 100))
    page = max(1, int(kwargs.get("page", 1)))
    resp = client._request(
        "GET",
        f"/repos/{kwargs['owner']}/{kwargs['repo']}/pulls",
        params={"state": state, "per_page": limit, "page": page},
    )
    items = resp.json()
    if not items:
        return f"PR ({state}, стр. {page}): нет"
    lines = [f"PR ({state}), стр. {page}, всего {len(items)}:"]
    for pr in items:
        lines.append(f"  #{pr['number']} [{pr['state']}] {pr['title']} — {pr['html_url']}")
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
    name="update_pull_request",
    description=(
        "Обновляет существующий PR: title, body, state, base, draft, reviewers. "
        "Передавай только те поля, которые нужно изменить."
    ),
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "number": {"type": "integer", "description": "Номер PR"},
        "title": {"type": "string"},
        "body": {"type": "string"},
        "state": {"type": "string", "description": "open|closed"},
        "base": {"type": "string", "description": "Новая целевая ветка"},
        "draft": {"type": "boolean", "description": "true = draft, false = ready"},
        "reviewers": {"type": "array", "items": {"type": "string"}, "description": "GitHub-логины для ревью"},
    },
    required=["owner", "repo", "number"],
)
def update_pull_request(client: GitHubClient, **kwargs) -> str:
    owner, repo, number = kwargs["owner"], kwargs["repo"], kwargs["number"]
    payload = {}
    for k in ("title", "body", "state", "base"):
        if kwargs.get(k) is not None:
            payload[k] = kwargs[k]
    if kwargs.get("draft") is not None:
        payload["draft"] = bool(kwargs["draft"])

    changes = []
    if payload:
        try:
            client._request(
                "PATCH", f"/repos/{owner}/{repo}/pulls/{number}", json=payload
            )
            changes.append(", ".join(payload.keys()))
        except Exception as e:
            return f"❌ Не удалось обновить PR #{number}: {e}"

    reviewers = kwargs.get("reviewers")
    if reviewers:
        if isinstance(reviewers, str):
            reviewers = [r.strip() for r in reviewers.split(",") if r.strip()]
        try:
            client._request(
                "POST",
                f"/repos/{owner}/{repo}/pulls/{number}/requested_reviewers",
                json={"reviewers": reviewers},
            )
            changes.append(f"reviewers: {', '.join(reviewers)}")
        except Exception as e:
            return f"⚠️ PR обновлён, но ревьюеры не назначены: {e}"

    if not changes:
        return "ℹ️ Нечего обновлять — не передано ни одного поля."
    return f"✅ PR #{number} обновлён ({'; '.join(changes)})"


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
    return f"✅ Комментарий: {resp.json().get('html_url', '')}"


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
    client._request(
        "POST",
        f"/repos/{kwargs['owner']}/{kwargs['repo']}/pulls/{kwargs['number']}/requested_reviewers",
        json={"reviewers": kwargs["reviewers"]},
    )
    return f"✅ Ревьюеры запрошены: {', '.join(kwargs['reviewers'])}"


def _toggle_review_thread(client: GitHubClient, thread_id: str, resolve: bool) -> str:
    """Resolve/unresolve review thread via GraphQL (REST API has no such endpoint)."""
    tid = (thread_id or "").strip()
    if not tid:
        return "❌ Пустой thread_id. Нужен node ID вида 'PRRT_kwDO...'."
    mutation = "resolveReviewThread" if resolve else "unresolveReviewThread"
    query = (
        f'mutation {{ {mutation}(input: {{threadId: "{tid}"}}) '
        f'{{ thread {{ id isResolved }} }} }}'
    )
    try:
        resp = client._request(
            "POST",
            f"{GitHubClient.BASE_URL}/graphql",
            json={"query": query},
        )
    except Exception as exc:
        return f"❌ Не удалось {'закрыть' if resolve else 'открыть'} thread {tid}: {exc}"
    data = resp.json()
    if data.get("errors"):
        msgs = "; ".join(e.get("message", "") for e in data["errors"])
        return f"❌ GraphQL error: {msgs}"
    thread = ((data.get("data") or {}).get(mutation) or {}).get("thread") or {}
    state = "закрыт ✅" if thread.get("isResolved") else "открыт ↩️"
    return f"Thread {tid}: {state}"


@mcp_tool(
    name="resolve_review_thread",
    description=(
        "Закрывает (resolve) review-thread по его node_id. "
        "GitHub не даёт это через REST — используется GraphQL resolveReviewThread. "
        "thread_id — node ID вида 'PRRT_kwDO...'."
    ),
    parameters={
        "thread_id": {"type": "string", "description": "Node ID review-thread (PRRT_...)"},
    },
    required=["thread_id"],
)
def resolve_review_thread(client: GitHubClient, **kwargs) -> str:
    return _toggle_review_thread(client, kwargs["thread_id"], resolve=True)


@mcp_tool(
    name="unresolve_review_thread",
    description="Снова открывает (unresolve) review-thread по его node_id (GraphQL unresolveReviewThread).",
    parameters={
        "thread_id": {"type": "string", "description": "Node ID review-thread (PRRT_...)"},
    },
    required=["thread_id"],
)
def unresolve_review_thread(client: GitHubClient, **kwargs) -> str:
    return _toggle_review_thread(client, kwargs["thread_id"], resolve=False)


@mcp_tool(
    name="get_review_threads",
    description=(
        "Возвращает review-threads PR (GraphQL reviewThreads): node_id (для "
        "resolve_review_thread), isResolved, isOutdated, path, line и первый "
        "комментарий. Используй id из вывода как thread_id."
    ),
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "number": {"type": "integer", "description": "Номер PR"},
        "only_unresolved": {"type": "boolean", "description": "Только незакрытые (по умолчанию false)"},
        "limit": {"type": "integer", "description": "Сколько тредов (по умолчанию 50, максимум 100)"},
    },
    required=["owner", "repo", "number"],
)
def get_review_threads(client: GitHubClient, **kwargs) -> str:
    owner, repo, number = kwargs["owner"], kwargs["repo"], kwargs["number"]
    limit = max(1, min(int(kwargs.get("limit", 50)), 100))
    only_unresolved = bool(kwargs.get("only_unresolved", False))
    query = (
        'query($owner:String!,$repo:String!,$number:Int!,$first:Int!){'
        ' repository(owner:$owner,name:$repo){'
        '  pullRequest(number:$number){'
        '   reviewThreads(first:$first){'
        '    nodes{ id isResolved isOutdated path line'
        '     comments(first:1){ nodes{ author{login} body } } }'
        '   } } } }'
    )
    try:
        resp = client._request(
            "POST",
            f"{GitHubClient.BASE_URL}/graphql",
            json={"query": query, "variables": {
                "owner": owner, "repo": repo, "number": int(number), "first": limit,
            }},
        )
    except Exception as exc:
        return f"❌ Не удалось получить review-threads PR #{number}: {exc}"
    data = resp.json()
    if data.get("errors"):
        msgs = "; ".join(e.get("message", "") for e in data["errors"])
        return f"❌ GraphQL error: {msgs}"
    pr = (((data.get("data") or {}).get("repository") or {}).get("pullRequest") or {})
    nodes = ((pr.get("reviewThreads") or {}).get("nodes") or [])
    if only_unresolved:
        nodes = [n for n in nodes if not n.get("isResolved")]
    if not nodes:
        return f"PR #{number}: review-threads нет" + (" (незакрытых)" if only_unresolved else "")
    lines = [f"PR #{number}: review-threads — {len(nodes)}:"]
    for n in nodes:
        state = "✅ resolved" if n.get("isResolved") else "🔴 open"
        loc = f"{n.get('path', '?')}:{n.get('line', '?')}"
        lines.append(f"  [{state}] {loc}  id={n.get('id')}")
        first = ((n.get("comments") or {}).get("nodes") or [{}])[0]
        if first:
            author = ((first.get("author") or {}).get("login")) or "?"
            body = (first.get("body") or "").splitlines()[0][:100]
            lines.append(f"      {author}: {body}")
    return "\n".join(lines)
