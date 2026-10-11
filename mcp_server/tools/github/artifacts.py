"""Bounded artifact lookup and sensitive, validated download capability resolution."""
import json
import re
from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient
from mcp_server.tools.github.commits import _safe_text


def _positive(value):
    return type(value) is int and value > 0


def _result(outcome, **extra):
    data = {"outcome": outcome, "download_url": None, "url_expires_at": None,
            "requires_github_authorization": None, "sensitive_download_url": False, **extra}
    return "📦 Artifact: " + outcome + "\nmetadata: " + json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _lookup(client, path, name, max_pages):
    fetched = 0
    total = None
    matches = []
    seen = set()
    for page in range(1, max_pages + 1):
        response = client._request("GET", path, params={"name": name, "per_page": 100, "page": page})
        data = response.json()
        if not isinstance(data, dict) or type(data.get("total_count")) is not int or data["total_count"] < 0:
            raise ValueError("invalid lookup payload")
        if total is not None and total != data["total_count"]:
            raise ValueError("lookup changed")
        total = data["total_count"]
        rows = data.get("artifacts")
        if not isinstance(rows, list) or len(rows) > 100:
            raise ValueError("invalid lookup rows")
        for row in rows:
            if not isinstance(row, dict) or not _positive(row.get("id")) or not isinstance(row.get("name"), str):
                raise ValueError("invalid artifact row")
            if row["id"] in seen:
                raise ValueError("duplicate artifact row")
            seen.add(row["id"])
            if row["name"] == name:
                matches.append(row)
        fetched += len(rows)
        if fetched > total:
            raise ValueError("invalid total")
        more = bool(re.search(r'rel=["\']?next', response.headers.get("Link", "")))
        if fetched == total and not more:
            return matches, True
        if not rows:
            raise ValueError("empty page before end")
    return matches, False


@mcp_tool(
    name="download_artifact",
    description="Разрешает 302 GitHub в проверенную краткоживущую ZIP-ссылку; PAT не нужен на CDN. URL чувствительный; файл не скачивает.",
    parameters={
        "owner": {"type": "string"}, "repo": {"type": "string"},
        "artifact_id": {"type": "integer", "description": "Точный ID; имеет приоритет над name"},
        "name": {"type": "string", "description": "Точное имя, обязательно вместе с run_id"},
        "run_id": {"type": "integer", "description": "ID запуска для поиска по name"},
        "max_pages": {"type": "integer", "description": "Лимит lookup страниц 1–20, default 5; по 100 записей"},
    },
    required=["owner", "repo"],
)
def download_artifact(client: GitHubClient, **kwargs) -> str:
    owner, repo = kwargs.get("owner"), kwargs.get("repo")
    artifact_id, name, run_id = kwargs.get("artifact_id"), kwargs.get("name"), kwargs.get("run_id")
    max_pages = kwargs.get("max_pages", 5)
    if (not isinstance(owner, str) or not re.fullmatch(r"[A-Za-z0-9-]+", owner)
            or not isinstance(repo, str) or repo in (".", "..") or not re.fullmatch(r"[A-Za-z0-9_.-]+", repo)
            or type(max_pages) is not int or not 1 <= max_pages <= 20
            or (artifact_id is not None and not _positive(artifact_id))
            or (run_id is not None and not _positive(run_id))
            or (artifact_id is None and (not isinstance(name, str) or not name or not _positive(run_id)))):
        return _result("invalid_input", error="artifact_id_or_exact_name_and_run_required")
    root = f"/repos/{owner}/{repo}/actions"
    try:
        if artifact_id is None:
            matches, complete = _lookup(client, f"{root}/runs/{run_id}/artifacts", name, max_pages)
            ids = [row["id"] for row in matches]
            if not complete:
                return _result("lookup_incomplete", lookup_complete=False, candidate_ids=ids[:20],
                               candidates_truncated=len(ids) > 20)
            if not matches:
                return _result("not_found", lookup_complete=True)
            if len(matches) > 1:
                return _result("ambiguous", lookup_complete=True, candidate_ids=ids[:20],
                               candidates_truncated=len(ids) > 20)
            art = matches[0]
            artifact_id = art["id"]
        else:
            art = client._request("GET", f"{root}/artifacts/{artifact_id}").json()
        if (not isinstance(art, dict) or type(art.get("id")) is not int or art["id"] != artifact_id
                or not isinstance(art.get("name"), str) or not art["name"]
                or type(art.get("expired")) is not bool or type(art.get("size_in_bytes")) is not int
                or art["size_in_bytes"] < 0):
            raise ValueError("invalid artifact metadata")
        workflow = art.get("workflow_run")
        if run_id is not None and (not isinstance(workflow, dict) or workflow.get("id") != run_id):
            raise ValueError("foreign run")
        info = {"artifact_id": artifact_id, "name": _safe_text(art["name"]), "size_in_bytes": art["size_in_bytes"],
                "created_at": _safe_text(art.get("created_at")), "artifact_expires_at": _safe_text(art.get("expires_at")),
                "expired": art["expired"], "lookup_complete": True}
        if art["expired"]:
            return _result("expired", **info)
        # Never trust archive_download_url from metadata as a destination.
        resolved = client.resolve_artifact_download(owner, repo, artifact_id)
        if not isinstance(resolved, dict) or resolved.get("outcome") != "resolved":
            outcome = resolved.get("outcome", "unknown") if isinstance(resolved, dict) else "unknown"
            status = resolved.get("http_status") if isinstance(resolved, dict) else None
            return _result(outcome, **info, http_status=status, error="download_not_resolved")
        return _result("resolved", **info, download_url=resolved["download_url"], http_status=302,
                       requires_github_authorization=False, sensitive_download_url=True)
    except Exception:
        return _result("unknown", artifact_id=artifact_id, lookup_complete=False,
                       error="metadata_or_lookup_unavailable_or_invalid")
