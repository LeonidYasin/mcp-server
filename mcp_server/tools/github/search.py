"""MCP tools: GitHub search (code)."""

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
