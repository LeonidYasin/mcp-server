"""MCP tools: web fetch and search (no API key required)."""

import re

import httpx

from mcp_server.core.registry import mcp_tool

_UA = "Mozilla/5.0 (compatible; mcp-github-server/0.5)"


def _strip_html(html: str) -> str:
    """Very small HTML-to-text reducer (no external deps)."""
    # drop script/style blocks entirely
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.S | re.I)
    # turn <br> and block ends into newlines
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    html = re.sub(r"</(p|div|li|h[1-6]|tr)>\s*", "\n", html, flags=re.I)
    # strip all remaining tags
    html = re.sub(r"<[^>]+>", "", html)
    # decode a handful of entities
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '\"'), ("&#39;", "'")):
        html = html.replace(a, b)
    # collapse whitespace
    html = re.sub(r"[ \t]+", " ", html)
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()


@mcp_tool(
    name="web_fetch",
    description="Загружает URL и возвращает текст страницы (HTML без тегов)",
    parameters={
        "url": {"type": "string", "description": "URL для загрузки"},
        "raw": {"type": "boolean", "description": "Вернуть сырой HTML вместо текста"},
        "max_chars": {"type": "integer", "description": "Лимит символов (по умолчанию 8000)"},
    },
    required=["url"],
)
def web_fetch(client=None, **kwargs) -> str:
    max_chars = int(kwargs.get("max_chars", 8000))
    with httpx.Client(timeout=30.0, follow_redirects=True, headers={"User-Agent": _UA}) as c:
        resp = c.get(kwargs["url"])
        resp.raise_for_status()
        body = resp.text
    if not kwargs.get("raw"):
        body = _strip_html(body)
    if len(body) > max_chars:
        body = body[:max_chars] + f"\n\n[...обрезано, всего {len(body)} символов]"
    return body


@mcp_tool(
    name="web_search",
    description="Поиск в вебе через DuckDuckGo (HTML, без API-ключа)",
    parameters={
        "query": {"type": "string", "description": "Поисковый запрос"},
        "limit": {"type": "integer", "description": "Сколько результатов (по умолчанию 10)"},
    },
    required=["query"],
)
def web_search(client=None, **kwargs) -> str:
    limit = int(kwargs.get("limit", 10))
    with httpx.Client(timeout=30.0, follow_redirects=True, headers={"User-Agent": _UA}) as c:
        resp = c.post(
            "https://html.duckduckgo.com/html/",
            data={"q": kwargs["query"]},
        )
        resp.raise_for_status()
        html = resp.text

    # each result: <a class="result__a" href="...">Title</a> ... <a class="result__snippet">Snippet</a>
    results = []
    blocks = re.findall(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>(.*?)(?=<a[^>]+class="result__a"|\Z)',
        html,
        flags=re.S | re.I,
    )
    for href, title_html, tail in blocks[:limit]:
        title = _strip_html(title_html)
        snip_match = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', tail, flags=re.S | re.I)
        snippet = _strip_html(snip_match.group(1)) if snip_match else ""
        # DuckDuckGo wraps hrefs: /l/?uddg=<urlencoded>
        m = re.search(r"uddg=([^&]+)", href)
        if m:
            from urllib.parse import unquote
            href = unquote(m.group(1))
        results.append(f"• {title}\n  {href}\n  {snippet}")
    if not results:
        return "Ничего не найдено (или DDG изменил разметку)"
    return "\n\n".join(results)
