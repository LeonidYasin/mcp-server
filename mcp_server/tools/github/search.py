"""MCP tools: GitHub search (code, commits, issues, repositories)."""

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


@mcp_tool(
    name="search_code",
    description=(
        "Ищет код по всему репозиторию/организации через GitHub Code Search. "
        "В отличие от grep_file (один файл), ищет везде сразу. "
        "Поддерживает квалификаторы GitHub: repo:, org:, user:, language:, "
        "path:, filename:, extension:, in:file, in:path."
    ),
    parameters={
        "query": {"type": "string", "description": "Поисковый запрос (синтаксис GitHub code search)"},
        "limit": {"type": "integer", "description": "Сколько результатов (по умолчанию 20, максимум 100)"},
    },
    required=["query"],
)
def search_code(client: GitHubClient, **kwargs) -> str:
    query = (kwargs.get("query") or "").strip()
    if not query:
        return "❌ Пустой query. Пример: 'WithContext language:go org:github'"
    limit = max(1, min(int(kwargs.get("limit", 20)), 100))

    try:
        resp = client._request(
            "GET",
            f"{GitHubClient.BASE_URL}/search/code",
            params={"q": query, "per_page": limit},
            headers={"Accept": "application/vnd.github+json"},
        )
    except Exception as e:
        return (
            f"❌ Code search не удался: {e}\n"
            f"   Подсказка: GitHub Code Search требует авторизации и иногда "
            f"ограничен по тарифу. Для точечного поиска в одном файле — grep_file."
        )

    data = resp.json()
    items = data.get("items", [])
    total = data.get("total_count", 0)
    if not items:
        return f"Ничего не найдено по запросу: {query}"

    lines = [f"Найдено {total}, показаны первые {len(items)}:"]
    for it in items:
        repo = (it.get("repository") or {}).get("full_name", "?")
        path = it.get("path", "?")
        lines.append(f"  {repo} :: {path}")
        for m in (it.get("text_matches") or [])[:2]:
            snippet = (m.get("fragment") or "").strip().replace("\n", " ")
            if snippet:
                lines.append(f"      {snippet[:200]}")
    return "\n".join(lines)


def _search(client: GitHubClient, endpoint: str, query: str, limit: int, kind: str):
    """Общий helper для GitHub Search API. Возвращает (items, total) либо строку-ошибку."""
    query = (query or "").strip()
    if not query:
        return f"❌ Пустой query для {kind}."
    limit = max(1, min(int(limit), 100))
    try:
        resp = client._request(
            "GET",
            f"{GitHubClient.BASE_URL}{endpoint}",
            params={"q": query, "per_page": limit},
            headers={"Accept": "application/vnd.github+json"},
        )
    except Exception as e:
        return (
            f"❌ {kind} search не удался: {e}\n"
            f"   Подсказка: GitHub Search API на бесплатном тарифе ограничен "
            f"~10 запросами/мин — подожди минуту и повтори."
        )
    data = resp.json()
    return data.get("items", []), data.get("total_count", 0)


@mcp_tool(
    name="search_commits",
    description="Поиск коммитов через GitHub Search (repo:, author:, committer-date:, merge: и т.д.)",
    parameters={
        "query": {"type": "string", "description": "Запрос (синтаксис GitHub commit search)"},
        "limit": {"type": "integer", "description": "Сколько результатов (по умолчанию 20, максимум 100)"},
    },
    required=["query"],
)
def search_commits(client: GitHubClient, **kwargs) -> str:
    res = _search(client, "/search/commits", kwargs.get("query"), kwargs.get("limit", 20), "commits")
    if isinstance(res, str):
        return res
    items, total = res
    if not items:
        return f"Ничего не найдено (commits): {kwargs.get('query')}"
    lines = [f"Коммитов найдено {total}, показаны первые {len(items)}:"]
    for it in items:
        repo = (it.get("repository") or {}).get("full_name", "?")
        sha = (it.get("sha") or "")[:7]
        msg = (it.get("commit", {}).get("message") or "").splitlines()[0][:80]
        lines.append(f"  {repo} {sha} — {msg}")
    return "\n".join(lines)


@mcp_tool(
    name="search_issues",
    description="Поиск issues и PR через GitHub Search (repo:, is:issue, is:pr, label:, state:, author:)",
    parameters={
        "query": {"type": "string", "description": "Запрос (синтаксис GitHub issue search)"},
        "limit": {"type": "integer", "description": "Сколько результатов (по умолчанию 20, максимум 100)"},
    },
    required=["query"],
)
def search_issues(client: GitHubClient, **kwargs) -> str:
    res = _search(client, "/search/issues", kwargs.get("query"), kwargs.get("limit", 20), "issues")
    if isinstance(res, str):
        return res
    items, total = res
    if not items:
        return f"Ничего не найдено (issues): {kwargs.get('query')}"
    lines = [f"Issues/PR найдено {total}, показаны первые {len(items)}:"]
    for it in items:
        kind = "PR" if "pull_request" in it else "issue"
        repo = (it.get("repository_url") or "").replace("https://api.github.com/repos/", "")
        lines.append(f"  [{kind}] {repo} #{it['number']} [{it['state']}] {it['title']}")
    return "\n".join(lines)


@mcp_tool(
    name="search_repositories",
    description="Поиск репозиториев через GitHub Search (language:, stars:, topic:, org:, user:)",
    parameters={
        "query": {"type": "string", "description": "Запрос (синтаксис GitHub repo search)"},
        "limit": {"type": "integer", "description": "Сколько результатов (по умолчанию 20, максимум 100)"},
    },
    required=["query"],
)
def search_repositories(client: GitHubClient, **kwargs) -> str:
    res = _search(client, "/search/repositories", kwargs.get("query"), kwargs.get("limit", 20), "repositories")
    if isinstance(res, str):
        return res
    items, total = res
    if not items:
        return f"Ничего не найдено (repositories): {kwargs.get('query')}"
    lines = [f"Репозиториев найдено {total}, показаны первые {len(items)}:"]
    for it in items:
        desc = (it.get("description") or "")[:100]
        lines.append(f"  {it['full_name']} ⭐{it.get('stargazers_count', 0)} — {desc}")
    return "\n".join(lines)
