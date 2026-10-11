"""Commit tools: list_commits, get_commit_status."""

import json
import re
from urllib.parse import quote, urlsplit, urlunsplit

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


@mcp_tool(
    name="list_commits",
    description="Получает список коммитов репозитория (с пагинацией)",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "sha": {"type": "string", "description": "Ветка или коммит (опционально)"},
        "limit": {"type": "integer", "description": "Сколько на странице (по умолчанию 10, максимум 100)"},
        "page": {"type": "integer", "description": "Номер страницы (по умолчанию 1)"},
    },
    required=["owner", "repo"],
)
def list_commits(client: GitHubClient, owner: str, repo: str, sha: str | None = None,
                 limit: int = 10, page: int = 1) -> str:
    """List commits with pagination."""
    try:
        per_page = max(1, min(int(limit), 100))
        page = max(1, int(page))
        commits = client.list_commits(owner, repo, sha, per_page=per_page, page=page)
        if not commits:
            return f"Нет коммитов (стр. {page})"
        lines = [f"Коммиты, стр. {page}, {len(commits)} шт:"]
        for c in commits:
            sha_short = c.get("sha", "")[:7]
            msg = c.get("commit", {}).get("message", "").splitlines()[0][:80]
            lines.append(f"{sha_short} - {msg}")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Ошибка: {e}"


_STATES = ("success", "failure", "pending", "neutral", "skipped", "unknown")
_SHA = re.compile(r"[0-9a-fA-F]{40}\Z")
_SECRET = re.compile(r"(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|Bearer\s+[^\s]+)", re.I)


def _safe_text(value, limit=200):
    if not isinstance(value, str):
        return None
    return _SECRET.sub("[redacted]", value).replace("\n", " ").replace("\r", " ")[:limit]


def _safe_url(value):
    if not isinstance(value, str):
        return None
    try:
        parts = urlsplit(value)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            return None
        host = parts.hostname
        if ":" in host:
            host = "[" + host + "]"
        if parts.port:
            host += ":" + str(parts.port)
        return _safe_text(urlunsplit((parts.scheme, host, parts.path, "", "")), 512)
    except ValueError:
        return None


def _check_state(row):
    status, conclusion = row.get("status"), row.get("conclusion")
    if status in ("queued", "requested", "pending", "waiting", "in_progress"):
        return "pending" if conclusion is None else "unknown"
    if status != "completed":
        return "unknown"
    if conclusion in ("failure", "cancelled", "timed_out", "action_required", "stale", "startup_failure"):
        return "failure"
    return conclusion if conclusion in ("success", "neutral", "skipped") else "unknown"


def _read_status_source(client, base, sha, kind, max_pages):
    rows, seen = [], set()
    info = {"complete": False, "truncated": False, "pages": 0,
            "fetched_count": 0, "total_count": None, "error": None}
    endpoint = "status" if kind == "legacy_statuses" else "check-runs"
    field = "statuses" if kind == "legacy_statuses" else "check_runs"
    for page in range(1, max_pages + 1):
        params = {"per_page": 100, "page": page}
        if kind == "check_runs":
            params["filter"] = "latest"
        try:
            response = client._request("GET", f"{base}/{sha}/{endpoint}", params=params)
            payload = response.json()
        except Exception:
            info["error"] = "api_or_decode_error"
            break
        info["pages"] += 1
        if not isinstance(payload, dict):
            info["error"] = "invalid_payload"
            break
        total, batch = payload.get("total_count"), payload.get(field)
        if type(total) is not int or total < 0 or not isinstance(batch, list) or len(batch) > 100:
            info["error"] = "invalid_payload"
            break
        if kind == "legacy_statuses" and payload.get("sha") != sha:
            info["error"] = "sha_mismatch"
            break
        if info["total_count"] is not None and info["total_count"] != total:
            info["error"] = "source_changed"
            break
        info["total_count"] = total
        for row in batch:
            if not isinstance(row, dict) or type(row.get("id")) is not int or row["id"] <= 0:
                info["error"] = "invalid_row"
                break
            if row["id"] in seen:
                info["error"] = "duplicate_row"
                break
            if kind == "check_runs" and row.get("head_sha", sha) != sha:
                info["error"] = "sha_mismatch"
                break
            seen.add(row["id"])
            if kind == "legacy_statuses":
                state = row.get("state")
                item = {"id": row["id"], "context": _safe_text(row.get("context")),
                        "state": _safe_text(state), "description": _safe_text(row.get("description")),
                        "target_url": _safe_url(row.get("target_url")),
                        "aggregate_state": {"success": "success", "failure": "failure", "error": "failure", "pending": "pending"}.get(state, "unknown") if isinstance(state, str) else "unknown"}
            else:
                app = row.get("app") if isinstance(row.get("app"), dict) else {}
                item = {"id": row["id"], "name": _safe_text(row.get("name")),
                        "status": _safe_text(row.get("status")), "conclusion": _safe_text(row.get("conclusion")),
                        "head_sha": sha, "html_url": _safe_url(row.get("html_url")),
                        "app": {"id": app.get("id") if type(app.get("id")) is int else None,
                                "slug": _safe_text(app.get("slug"))},
                        "aggregate_state": _check_state(row)}
            rows.append(item)
        info["fetched_count"] = len(rows)
        if info["error"]:
            break
        more = bool(re.search(r'rel=[\"\']?next', response.headers.get("Link", "")))
        if len(rows) > total:
            info["error"] = "invalid_total"
            break
        if len(rows) == total and not more:
            info["complete"] = True
            break
        if not batch:
            info["error"] = "empty_page_before_end"
            break
        if page == max_pages:
            info["truncated"] = True
    return rows, info


@mcp_tool(
    name="get_commit_status",
    description="Агрегирует legacy statuses и check runs для SHA; не проверяет разрешение merge",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "sha": {"type": "string", "description": "SHA или ref коммита"},
        "max_pages": {"type": "integer", "description": "Лимит страниц на источник: 1–20, по умолчанию 5"},
        "max_rows": {"type": "integer", "description": "Лимит выводимых строк на источник: 0–100, по умолчанию 25"},
    },
    required=["owner", "repo", "sha"],
)
def get_commit_status(client: GitHubClient, owner: str, repo: str, sha: str,
                      max_pages: int = 5, max_rows: int = 25) -> str:
    """Read bounded, SHA-pinned status sources. Incomplete evidence never succeeds."""
    for name, value, low, high in (("max_pages", max_pages, 1, 20), ("max_rows", max_rows, 0, 100)):
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"{name} must be an integer in {low}..{high}")
    data = {"head_sha": None, "commit_url": None, "aggregate_state": "unknown", "complete": False,
            "truncated": False, "output_truncated": False, "legacy_statuses": [], "check_runs": [],
            "counts": dict.fromkeys(_STATES, 0), "sources": {},
            "neutral_skipped_policy": "non_blocking", "merge_eligibility": "not_evaluated"}
    try:
        if not all(isinstance(v, str) and v for v in (owner, repo, sha)):
            raise ValueError("invalid identity")
        base = f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/commits"
        commit = client._request("GET", f"{base}/{quote(sha, safe='')}").json()
        resolved = commit.get("sha") if isinstance(commit, dict) else None
        if not isinstance(resolved, str) or not _SHA.fullmatch(resolved):
            raise ValueError("invalid SHA")
        data["head_sha"] = resolved.lower()
        data["commit_url"] = _safe_url(commit.get("html_url"))
    except Exception:
        data["resolution_error"] = "unavailable_or_invalid_commit"
    else:
        all_rows = []
        priority = {state: rank for rank, state in enumerate(("failure", "unknown", "pending", "success", "neutral", "skipped"))}
        for kind in ("legacy_statuses", "check_runs"):
            rows, info = _read_status_source(client, base, data["head_sha"], kind, max_pages)
            data["sources"][kind] = info
            all_rows.extend(rows)
            data[kind] = sorted(rows, key=lambda r: priority[r["aggregate_state"]])[:max_rows]
            data["output_truncated"] |= len(rows) > max_rows
        for row in all_rows:
            data["counts"][row["aggregate_state"]] += 1
        data["complete"] = all(i["complete"] for i in data["sources"].values())
        data["truncated"] = data["output_truncated"] or any(i["truncated"] for i in data["sources"].values())
        if data["complete"]:
            counts = data["counts"]
            data["aggregate_state"] = ("failure" if counts["failure"] else "unknown" if counts["unknown"] else
                                       "pending" if counts["pending"] else "success" if all_rows else "no_checks")
    lines = [f"🔖 Коммит: {data['head_sha'] or 'unknown'}", f"📊 Статус: {data['aggregate_state']}",
             "metadata: " + json.dumps(data, ensure_ascii=False, separators=(",", ":")),
             "ℹ️ neutral/skipped — non-blocking; это не подтверждение запуска тестов или разрешения merge."]
    return "\n".join(lines)
