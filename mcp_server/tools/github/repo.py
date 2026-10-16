"""MCP tools: repository info and stats."""

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


@mcp_tool(
    name="get_repo_info",
    description="Информация о репозитории; mode=public_evidence: bounded anonymous SHA-pinned excerpts, optional fork comparison; not runtime validation.",
    parameters={
        "owner": {"type": "string"}, "repo": {"type": "string"},
        "mode": {"type": "string", "enum": ["legacy", "public_evidence"],
                 "description": "Default legacy preserves authenticated text; public_evidence returns bounded JSON text."},
        "ref": {"type": "string", "description": "public_evidence only: branch/tag/SHA, pinned before file reads; default default_branch."},
        "file_selection": {"type": "string", "enum": ["explicit", "auto"],
            "description": "public_evidence only: explicit(default) requires evidence_files; auto forbids evidence_files and selects <=6 files by explained path heuristics, not verified relevance."},
        "evidence_files": {"type": "array", "minItems": 1, "maxItems": 6,
            "description": "public_evidence only: explicit selected files, not discovery or arbitrary URL fetch.",
            "items": {"type": "object", "additionalProperties": False, "required": ["path"],
                      "properties": {"path": {"type": "string"},
                          "start_line": {"type": "integer", "minimum": 1, "maximum": 1000000},
                          "max_lines": {"type": "integer", "minimum": 1, "maximum": 100}}}},
        "compare_parent": {"type": "boolean", "description": "public_evidence only: explicitly observe fork parent default-branch comparison (no patch); default false."},
    },
    required=["owner", "repo"],
)
def get_repo_info(client: GitHubClient, **kwargs) -> str:
    mode = kwargs.pop("mode", "legacy")
    if mode == "public_evidence":
        from mcp_server.tools.github.repository_evidence import observe
        return observe(client, **kwargs)
    if mode != "legacy" or set(kwargs) - {"owner", "repo"}:
        import json
        return json.dumps({"state": "invalid_input", "error": "unsupported_mode_or_arguments"})
    d = client._request("GET", f"/repos/{kwargs['owner']}/{kwargs['repo']}").json()
    size_kb = d.get("size", 0)
    visibility = d.get("visibility") or ("private" if d.get("private") else "public")
    return (
        f"{d['full_name']}\n"
        f"Описание: {d.get('description') or '-'}\n"
        f"Язык: {d.get('language')}\n"
        f"Видимость: {visibility} | Архив: {d.get('archived')} | Fork: {d.get('fork')}\n"
        f"⭐ {d.get('stargazers_count')} | 🍴 {d.get('forks_count')} | 👁 {d.get('watchers_count')}\n"
        f"Issues: {d.get('open_issues_count')} | Ветка по умолчанию: {d.get('default_branch')}\n"
        f"Размер: {size_kb} KB (~{size_kb / 1024:.1f} MB)\n"
        f"Создан: {d.get('created_at')}\n"
        f"Обновлён: {d.get('updated_at')} | Push: {d.get('pushed_at')}\n"
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
    description="Контрибьюторы репозитория (по числу коммитов, с пагинацией и опцией anon)",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "limit": {"type": "integer", "description": "Сколько вернуть на странице (по умолчанию 20, максимум 100)"},
        "page": {"type": "integer", "description": "Номер страницы (по умолчанию 1)"},
        "anon": {"type": "boolean", "description": "Включать анонимных контрибьюторов (по умолчанию false)"},
    },
    required=["owner", "repo"],
)
def list_repo_contributors(client: GitHubClient, **kwargs) -> str:
    limit = max(1, min(int(kwargs.get("limit", 20)), 100))
    page = max(1, int(kwargs.get("page", 1)))
    params = {"per_page": limit, "page": page}
    if kwargs.get("anon"):
        params["anon"] = "1"
    resp = client._request(
        "GET",
        f"/repos/{kwargs['owner']}/{kwargs['repo']}/contributors",
        params=params,
    )
    items = resp.json()
    if not isinstance(items, list) or not items:
        return f"Контрибьюторов нет (стр. {page})"
    lines = [f"Контрибьюторы (стр. {page}, {len(items)}):"]
    for c in items:
        login = c.get("login") or (c.get("name") or "anonymous")
        lines.append(f"  {login}: {c.get('contributions')} коммитов")
    return "\n".join(lines)
