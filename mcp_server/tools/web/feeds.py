"""MCP tools: feeds and HTML conversion."""

import re
import xml.etree.ElementTree as ET

import httpx

from mcp_server.core.registry import mcp_tool

_UA = "Mozilla/5.0 (compatible; mcp-github-server/0.5)"


def _text(el):
    return (el.text or "").strip() if el is not None else ""


@mcp_tool(
    name="rss_read",
    description="Читает RSS/Atom-фид и возвращает список записей",
    parameters={
        "url": {"type": "string", "description": "URL фида"},
        "limit": {"type": "integer", "description": "Сколько записей (по умолчанию 15)"},
    },
    required=["url"],
)
def rss_read(client=None, **kwargs) -> str:
    limit = int(kwargs.get("limit", 15))
    with httpx.Client(timeout=30.0, follow_redirects=True, headers={"User-Agent": _UA}) as c:
        resp = c.get(kwargs["url"])
        resp.raise_for_status()
        raw = resp.content
    root = ET.fromstring(raw)

    items = []
    # RSS 2.0
    for it in root.iter("item"):
        title = _text(it.find("title"))
        link = _text(it.find("link"))
        date = _text(it.find("pubDate"))
        items.append((title, link, date))
    # Atom
    if not items:
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for e in root.findall("a:entry", ns):
            title = _text(e.find("a:title", ns))
            link_el = e.find("a:link", ns)
            link = link_el.get("href") if link_el is not None else ""
            date = _text(e.find("a:updated", ns)) or _text(e.find("a:published", ns))
            items.append((title, link, date))

    if not items:
        return "Записей не найдено (не RSS/Atom?)"
    lines = [f"Записей: {min(len(items), limit)}"]
    for title, link, date in items[:limit]:
        lines.append(f"• {title}\n  {link}\n  {date}")
    return "\n".join(lines)


@mcp_tool(
    name="html_to_markdown",
    description="Грубое преобразование HTML в Markdown (без внешних зависимостей)",
    parameters={
        "html": {"type": "string", "description": "HTML-строка"},
        "max_chars": {"type": "integer", "description": "Лимит символов (по умолчанию 20000)"},
    },
    required=["html"],
)
def html_to_markdown(client=None, **kwargs) -> str:
    html = kwargs["html"]
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.S | re.I)

    # headings
    for i in range(1, 7):
        html = re.sub(
            rf"<h{i}[^>]*>(.*?)</h{i}>",
            lambda m: "\n" + "#" * i + " " + m.group(1) + "\n",
            html,
            flags=re.S | re.I,
        )
    # links
    html = re.sub(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', r"[\2](\1)", html, flags=re.S | re.I)
    # bold / italic
    html = re.sub(r"<(b|strong)>(.*?)</\1>", r"**\2**", html, flags=re.S | re.I)
    html = re.sub(r"<(i|em)>(.*?)</\1>", r"*\2*", html, flags=re.S | re.I)
    # code
    html = re.sub(r"<code[^>]*>(.*?)</code>", r"`\1`", html, flags=re.S | re.I)
    html = re.sub(r"<pre[^>]*>(.*?)</pre>", lambda m: "\n```\n" + m.group(1) + "\n```\n", html, flags=re.S | re.I)
    # lists
    html = re.sub(r"<li[^>]*>(.*?)</li>", lambda m: "- " + m.group(1).strip() + "\n", html, flags=re.S | re.I)
    # paragraphs / breaks
    html = re.sub(r"</p>\s*", "\n\n", html, flags=re.I)
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    # strip remaining tags
    html = re.sub(r"<[^>]+>", "", html)
    # entities
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")):
        html = html.replace(a, b)
    html = re.sub(r"\n{3,}", "\n\n", html).strip()

    limit = int(kwargs.get("max_chars", 20000))
    if len(html) > limit:
        total = len(html)
        html = html[:limit] + "\n\n[...обрезано, всего " + str(total) + "]"
    return html
