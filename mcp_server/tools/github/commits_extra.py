"""MCP tools: extra commit / file inspection."""

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


def _branch_hint(owner: str, repo: str, ref: str, err: Exception) -> str:
    """Build a friendly message when a ref/branch does not exist."""
    return (
        f"❌ Ветка/ref '{ref}' не найдена в {owner}/{repo}.\n"
        f"   GitHub: {err}\n"
        f"   Подсказка: вызови list_branches(owner='{owner}', repo='{repo}'), "
        f"чтобы узнать имя дефолтной ветки (часто master, а не main)."
    )


def _resolve_sha(client: GitHubClient, owner: str, repo: str, ref: str):
    """Короткий SHA/ветка → полный SHA. Возвращает (sha, error)."""
    ref = (ref or "").strip()
    if not ref:
        return None, "❌ Пустой sha/ref."
    # Уже полный SHA?
    if len(ref) == 40 and all(c in "0123456789abcdef" for c in ref.lower()):
        return ref, None
    try:
        resp = client._request("GET", f"/repos/{owner}/{repo}/commits/{ref}")
        return resp.json().get("sha"), None
    except Exception as exc:
        return None, _branch_hint(owner, repo, ref, exc)


@mcp_tool(
    name="get_commit_diff",
    description="Unified diff конкретного коммита (короткий SHA нормализуется в полный)",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "sha": {"type": "string", "description": "SHA коммита (можно короткий) или ветка"},
        "max_files": {"type": "integer", "description": "Сколько файлов показать (по умолчанию 20)"},
    },
    required=["owner", "repo", "sha"],
)
def get_commit_diff(client: GitHubClient, **kwargs) -> str:
    owner, repo, ref = kwargs["owner"], kwargs["repo"], kwargs["sha"]
    full_sha, err = _resolve_sha(client, owner, repo, ref)
    if err:
        return err
    try:
        resp = client._request(
            "GET",
            f"{GitHubClient.BASE_URL}/repos/{owner}/{repo}/commits/{full_sha}",
            headers={"Accept": "application/vnd.github.v3.diff"},
        )
    except Exception as exc:
        return _branch_hint(owner, repo, ref, exc)
    diff = resp.text
    limit = int(kwargs.get("max_files", 20))
    parts = diff.split("diff --git ")
    header = f"# {ref[:12]} → {full_sha[:12]}\n" if full_sha[:12] != ref[:12] else ""
    if len(parts) > limit + 1:
        diff = "diff --git ".join(parts[: limit + 1]) + f"\n\n[...ещё {len(parts) - limit - 1} файлов]"
    return header + diff


@mcp_tool(
    name="list_directory",
    description="Список файлов в директории репозитория (по пути)",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "path": {"type": "string", "description": "Путь директории (пусто = корень)"},
        "ref": {"type": "string", "description": "Ветка/коммит (по умолчанию — дефолтная ветка репо)"},
    },
    required=["owner", "repo"],
)
def list_directory(client: GitHubClient, **kwargs) -> str:
    path = (kwargs.get("path") or "").strip("/")
    ref = (kwargs.get("ref") or "").strip()
    url = f"{GitHubClient.BASE_URL}/repos/{kwargs['owner']}/{kwargs['repo']}/contents/{path}"
    params = {"ref": ref} if ref else None
    try:
        resp = client._request("GET", url, params=params)
    except Exception as exc:
        if ref:
            return _branch_hint(kwargs["owner"], kwargs["repo"], ref, exc)
        return (
            f"❌ Не удалось прочитать {kwargs['owner']}/{kwargs['repo']}/{path or ''}: {exc}\n"
            f"   Подсказка: проверь owner/repo или вызови list_branches."
        )
    items = resp.json()
    if isinstance(items, dict):
        return f"Не директория или не найдено: {items.get('message', '')}"
    where = path or "/"
    where += f" @ {ref}" if ref else " @ default branch"
    lines = [f"{where} — {len(items)} элементов:"]
    for it in items:
        icon = "📁" if it["type"] == "dir" else "📄"
        lines.append(f"  {icon} {it['name']} ({it.get('size', '-')} b)")
    return "\n".join(lines)


@mcp_tool(
    name="get_repo_tree",
    description=(
        "Возвращает ВСЁ дерево репозитория одним вызовом (рекурсивно). "
        "Использует Git Trees API с recursive=1 — надёжнее, чем обход "
        "list_directory по каталогам, и не теряет файлы при неполном листинге."
    ),
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "ref": {"type": "string", "description": "Ветка/коммит (по умолчанию — дефолтная ветка репо)"},
        "path_prefix": {"type": "string", "description": "Показать только пути с этим префиксом"},
        "blobs_only": {"type": "boolean", "description": "Только файлы, без каталогов (по умолчанию true)"},
        "max_entries": {"type": "integer", "description": "Ограничение на число строк (по умолчанию 2000)"},
    },
    required=["owner", "repo"],
)
def get_repo_tree(client: GitHubClient, **kwargs) -> str:
    ref = (kwargs.get("ref") or "").strip()
    prefix = (kwargs.get("path_prefix") or "").strip("/")
    blobs_only = kwargs.get("blobs_only", True)
    max_entries = max(int(kwargs.get("max_entries", 2000)), 1)

    if not ref:
        try:
            info = client._request(
                "GET", f"/repos/{kwargs['owner']}/{kwargs['repo']}"
            ).json()
            ref = info.get("default_branch") or "main"
        except Exception as exc:
            return f"❌ Не удалось определить дефолтную ветку: {exc}"

    try:
        resp = client._request(
            "GET",
            f"/repos/{kwargs['owner']}/{kwargs['repo']}/git/trees/{ref}",
            params={"recursive": "1"},
        )
    except Exception as exc:
        return _branch_hint(kwargs["owner"], kwargs["repo"], ref, exc)

    data = resp.json()
    tree = data.get("tree", [])
    truncated = data.get("truncated", False)

    rows = []
    for it in tree:
        p = it.get("path", "")
        if blobs_only and it.get("type") != "blob":
            continue
        if prefix and not p.startswith(prefix):
            continue
        rows.append((p, it.get("type"), it.get("size")))

    shown = rows[:max_entries]
    header = (
        f"Дерево {kwargs['owner']}/{kwargs['repo']} @ {ref} — "
        f"{len(rows)} элементов" + (f" (показаны первые {len(shown)})" if len(rows) > len(shown) else "")
    )
    if truncated:
        header += "\n⚠️ GitHub пометил дерево как truncated (очень большой репо) — часть путей может отсутствовать."
    lines = [header]
    for p, t, size in shown:
        icon = "📄" if t == "blob" else "📁"
        lines.append(f"  {icon} {p}" + (f" ({size} b)" if size is not None else ""))
    return "\n".join(lines)


@mcp_tool(
    name="get_file_blame",
    description="Показывает, кто последний менял строки файла (через GitHub API: коммиты по файлу)",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "path": {"type": "string"},
        "ref": {"type": "string", "description": "Ветка/коммит (по умолчанию — дефолтная ветка репо)"},
        "limit": {"type": "integer", "description": "Сколько коммитов (по умолчанию 20)"},
    },
    required=["owner", "repo", "path"],
)
def get_file_blame(client: GitHubClient, **kwargs) -> str:
    ref = (kwargs.get("ref") or "").strip()
    params = {
        "path": kwargs["path"],
        "per_page": min(int(kwargs.get("limit", 20)), 100),
    }
    if ref:
        params["sha"] = ref
    try:
        resp = client._request(
            "GET",
            f"{GitHubClient.BASE_URL}/repos/{kwargs['owner']}/{kwargs['repo']}/commits",
            params=params,
        )
    except Exception as exc:
        if ref:
            return _branch_hint(kwargs["owner"], kwargs["repo"], ref, exc)
        return f"❌ Не удалось получить историю {kwargs['path']}: {exc}"
    commits = resp.json()
    if not isinstance(commits, list) or not commits:
        return f"История пуста: {kwargs['path']}"
    lines = [f"История {kwargs['path']} ({len(commits)} коммитов):"]
    for c in commits:
        sha_short = c.get("sha", "")[:7]
        commit = c.get("commit", {})
        author = (commit.get("author") or {}).get("name", "?")
        date = (commit.get("author") or {}).get("date", "")[:10]
        msg = (commit.get("message") or "").splitlines()[0][:70]
        lines.append(f"  {sha_short} {date} {author}: {msg}")
    return "\n".join(lines)
