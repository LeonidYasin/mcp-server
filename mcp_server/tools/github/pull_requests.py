"""MCP tools: GitHub pull requests."""

import json
import re
from urllib.parse import quote

from mcp_server.tools.github.commits import get_commit_status, _safe_text, _safe_url, _SHA
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


def _pr_path(kwargs):
    owner, repo, number = kwargs.get("owner"), kwargs.get("repo"), kwargs.get("number")
    if (not isinstance(owner, str) or not re.fullmatch(r"[A-Za-z0-9-]+", owner)
            or not isinstance(repo, str) or repo in (".", "..")
            or not re.fullmatch(r"[A-Za-z0-9_.-]+", repo)
            or type(number) is not int or number < 1):
        raise ValueError("invalid PR identity")
    return f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/pulls/{number}"


def _full_sha(value):
    return value.lower() if isinstance(value, str) and _SHA.fullmatch(value) else None


def _pr_metadata(row):
    if not isinstance(row, dict):
        raise ValueError("invalid PR response")
    data = {key: _safe_text(row.get(key)) for key in
            ("title", "state", "mergeable_state", "created_at", "updated_at", "closed_at", "merged_at")}
    data["number"] = row.get("number") if type(row.get("number")) is int else None
    for key in ("merged", "draft", "mergeable"):
        data[key] = row.get(key) if type(row.get(key)) is bool else None
    data["merge_commit_sha"] = _full_sha(row.get("merge_commit_sha"))
    data["html_url"] = _safe_url(row.get("html_url"))
    for key in ("head", "base"):
        ref = row.get(key) if isinstance(row.get(key), dict) else {}
        repo = ref.get("repo") if isinstance(ref.get("repo"), dict) else {}
        data[key] = {"sha": _full_sha(ref.get("sha")), "ref": _safe_text(ref.get("ref")),
                     "repo": _safe_text(repo.get("full_name"))}
    data["merge_eligibility"] = "not_evaluated"
    user = row.get("user") if isinstance(row.get("user"), dict) else {}
    data["author"] = _safe_text(user.get("login"))
    for key in ("additions", "deletions", "changed_files"):
        data[key] = row.get(key) if type(row.get(key)) is int else None
    return data


def _repo_methods(client, path):
    try:
        row = client._request("GET", path.split("/pulls/")[0]).json()
        if not isinstance(row, dict):
            raise ValueError("invalid repo response")
        flags = {method: row.get(flag) if type(row.get(flag)) is bool else None
                 for method, flag in (("merge", "allow_merge_commit"),
                                      ("squash", "allow_squash_merge"), ("rebase", "allow_rebase_merge"))}
        return flags, None
    except Exception:
        return dict.fromkeys(("merge", "squash", "rebase")), "unavailable_or_invalid_repo"


def _metadata_line(data):
    return "metadata: " + json.dumps(data, ensure_ascii=False, separators=(",", ":"))


@mcp_tool(
    name="get_pull_request",
    description="Данные PR: SHA, draft, mergeable tri-state, timestamps и repo merge methods; не разрешение merge",
    parameters={"owner": {"type": "string"}, "repo": {"type": "string"},
                "number": {"type": "integer", "description": "Номер PR"}},
    required=["owner", "repo", "number"],
)
def get_pull_request(client: GitHubClient, **kwargs) -> str:
    missing = [k for k in ("owner", "repo", "number") if kwargs.get(k) is None]
    if missing:
        return f"❌ Не переданы обязательные параметры: {', '.join(missing)}"
    try:
        path = _pr_path(kwargs)
    except ValueError:
        return "❌ Invalid PR identity\n" + _metadata_line({"error": "invalid_input"})
    try:
        row = client._request("GET", path).json()
        data = _pr_metadata(row)
        if data["number"] != kwargs["number"]:
            raise ValueError("wrong PR")
    except Exception:
        return "❌ PR read unavailable\n" + _metadata_line({"error": "unavailable_or_invalid_pr"})
    methods, error = _repo_methods(client, path)
    data["merge_method_flags"] = methods
    data["allowed_merge_methods"] = [method for method, allowed in methods.items() if allowed is True]
    data["merge_methods_complete"] = all(value is not None for value in methods.values())
    data["merge_methods_error"] = error
    return (f"PR #{data['number']}: {data['title'] or ''}\n"
            f"Состояние: {data['state']} (merged={data['merged']})\n"
            f"Автор: {data['author']}\n"
            f"Ветки: {data['head']['ref']} -> {data['base']['ref']}\n"
            f"Изменений: +{data['additions']} / -{data['deletions']} в {data['changed_files']} файлах\n"
            f"URL: {data['html_url']}\n" + _metadata_line(data) + "\n\n" + (_safe_text(row.get("body"), 2000) or ""))


def _update_output(number, outcome, changes, requested=None, actual=None,
                   draft_outcome=None, draft_applied=None, error=None):
    data = {"number": number if type(number) is int else None, "outcome": outcome, "changes": changes,
            "requested_draft": requested, "actual_draft": actual,
            "draft_outcome": draft_outcome, "draft_applied": draft_applied, "error": error}
    if outcome == "updated":
        label = f"✅ PR #{number} обновлён ({'; '.join(changes)})"
    elif outcome == "no_op":
        label = f"ℹ️ PR #{number}: уже в запрошенном состоянии"
    else:
        label = f"{'⚠️' if outcome in ('partial', 'unconfirmed') else '❌'} PR #{data['number']}: {outcome}"
    return label + "\n" + _metadata_line(data)


def _draft_snapshot(row, number, node=None):
    if (not isinstance(row, dict) or type(row.get("number")) is not int
            or row["number"] != number or type(row.get("draft")) is not bool
            or type(row.get("merged")) is not bool or row.get("state") not in ("open", "closed")):
        raise ValueError("invalid PR snapshot")
    if node is not None and row.get("node_id") != node:
        raise ValueError("PR node changed")
    return row


def _transition_draft(client, path, number, requested, before):
    actual = before["draft"]
    if actual is requested:
        return "no_op", actual, False, None
    node = before.get("node_id")
    if not isinstance(node, str) or not node or len(node) > 256 or any(ord(c) < 32 for c in node):
        return "rejected", actual, False, "invalid_node_id"
    mutation = "convertPullRequestToDraft" if requested else "markPullRequestReadyForReview"
    query = ("mutation DraftTransition($pullRequestId: ID!) { " + mutation +
             "(input: {pullRequestId: $pullRequestId}) { pullRequest { id number isDraft state } } }")
    error = None
    echo_valid = False
    try:
        payload = client._request("POST", "/graphql", json={
            "query": query, "variables": {"pullRequestId": node}}).json()
        if not isinstance(payload, dict):
            error = "invalid_graphql_response"
        elif payload.get("errors"):
            error = "graphql_error"
        else:
            data = payload.get("data")
            result = data.get(mutation) if isinstance(data, dict) else None
            observed = result.get("pullRequest") if isinstance(result, dict) else None
            echo_valid = (isinstance(observed, dict) and observed.get("id") == node
                          and type(observed.get("number")) is int and observed["number"] == number
                          and observed.get("isDraft") is requested and observed.get("state") == "OPEN")
            if not echo_valid:
                error = "invalid_graphql_response"
    except Exception:
        error = "graphql_request_unconfirmed"
    # HTTP 200 is not proof. Even GraphQL errors/timeouts can have side effects.
    # Always inspect the actual PR; never retry the mutation automatically.
    try:
        after = _draft_snapshot(client._request("GET", path).json(), number, node)
        actual = after["draft"]
    except Exception:
        return "unconfirmed", None, None, error or "readback_unavailable_or_invalid"
    if after["state"] != "open" or after["merged"]:
        return "unconfirmed", actual, None, error or "pr_closed_during_transition"
    if echo_valid and error is None and actual is requested:
        return "applied", actual, True, None
    if error == "graphql_error" and actual is not requested:
        return "rejected", actual, False, error
    return "unconfirmed", actual, None, error or "readback_mismatch"


@mcp_tool(
    name="update_pull_request",
    description=("Обновляет только переданные поля PR. Draft/ready через GraphQL с обязательным read-back; "
                 "partial/unconfirmed не означает полный успех."),
    parameters={
        "owner": {"type": "string"}, "repo": {"type": "string"},
        "number": {"type": "integer", "description": "Номер PR"},
        "title": {"type": "string"}, "body": {"type": "string"},
        "state": {"type": "string", "enum": ["open", "closed"]}, "base": {"type": "string"},
        "draft": {"type": "boolean", "description": "true = draft, false = ready; GraphQL + REST read-back"},
        "reviewers": {"type": "array", "items": {"type": "string"}, "description": "GitHub-логины для ревью"},
    },
    required=["owner", "repo", "number"],
)
def update_pull_request(client: GitHubClient, **kwargs) -> str:
    missing = [k for k in ("owner", "repo", "number") if kwargs.get(k) is None]
    if missing:
        return f"❌ Не переданы обязательные параметры: {', '.join(missing)}"
    number = kwargs.get("number")
    requested = kwargs.get("draft")
    try:
        path = _pr_path(kwargs)
        if requested is not None and type(requested) is not bool:
            raise ValueError("invalid draft")
        payload = {k: kwargs[k] for k in ("title", "body", "state", "base") if kwargs.get(k) is not None}
        if any(not isinstance(value, str) for value in payload.values()):
            raise ValueError("invalid REST fields")
        if "state" in payload and payload["state"] not in ("open", "closed"):
            raise ValueError("invalid state")
        if requested is not None and payload.get("state") == "closed":
            raise ValueError("cannot close and transition draft together")
        reviewers = kwargs.get("reviewers")
        if isinstance(reviewers, str):
            reviewers = [r.strip() for r in reviewers.split(",") if r.strip()]
        if reviewers is not None and (not isinstance(reviewers, list) or len(reviewers) > 100
                or any(not isinstance(r, str) or not re.fullmatch(r"[A-Za-z0-9-]+", r) for r in reviewers)):
            raise ValueError("invalid reviewers")
    except ValueError:
        return _update_output(number, "invalid_input", [], error="invalid_update_arguments")
    if not payload and not reviewers and requested is None:
        return "ℹ️ Нечего обновлять — не передано ни одного поля."
    before = None
    actual = None
    if requested is not None:
        try:
            before = _draft_snapshot(client._request("GET", path).json(), number)
            actual = before["draft"]
        except Exception:
            return _update_output(number, "unconfirmed", [], requested, error="initial_read_unavailable_or_invalid")
        if before["state"] != "open" or before["merged"]:
            return _update_output(number, "rejected", [], requested, actual, "rejected", False, "pr_not_open")
        # Validate identity before any mixed-operation writes.
        if actual is not requested:
            node = before.get("node_id")
            if not isinstance(node, str) or not node or len(node) > 256 or any(ord(c) < 32 for c in node):
                return _update_output(number, "rejected", [], requested, actual, "rejected", False, "invalid_node_id")
    changes = []
    if payload:
        try:
            client._request("PATCH", path, json=payload)
            changes.extend(payload)
        except Exception:
            return _update_output(number, "unconfirmed", changes, requested, actual,
                                  error="rest_update_unconfirmed")
    draft_outcome = draft_applied = None
    if requested is not None:
        draft_outcome, actual, draft_applied, error = _transition_draft(client, path, number, requested, before)
        if draft_outcome == "applied":
            changes.append("draft")
        elif draft_outcome != "no_op":
            outcome = "partial" if changes else "unconfirmed" if draft_outcome == "unconfirmed" else "rejected"
            return _update_output(number, outcome, changes, requested, actual, draft_outcome, draft_applied, error)
    if reviewers:
        try:
            client._request("POST", path + "/requested_reviewers", json={"reviewers": reviewers})
            changes.append("reviewers: " + ", ".join(reviewers))
        except Exception:
            return _update_output(number, "partial" if changes else "unconfirmed", changes, requested, actual,
                                  draft_outcome, draft_applied, "reviewer_request_unconfirmed")
    return _update_output(number, "updated" if changes else "no_op", changes, requested, actual,
                          draft_outcome, draft_applied)


def _merge_output(number, outcome, message, merged=False, sha=None, **extra):
    data = {"number": number if type(number) is int else None, "outcome": outcome,
            "merged": merged, "sha": sha, "message": message, **extra}
    label = "✅" if merged is True else "⚠️" if merged is None else "❌"
    return f"{label} PR #{data['number']}: {message}\n" + _metadata_line(data)


def _snapshot_block(row, number, expected):
    data = _pr_metadata(row)
    if data["number"] != number or data["head"]["sha"] is None:
        return data, "preflight_unknown"
    if data["head"]["sha"] != expected:
        return data, "head_conflict"
    if data["merged"] is True:
        return data, "already_merged"
    if data["state"] == "closed" and data["merged"] is False:
        return data, "closed"
    if data["state"] != "open" or data["merged"] is not False or data["draft"] is None:
        return data, "preflight_unknown"
    if data["draft"]:
        return data, "draft"
    if data["mergeable"] is None:
        return data, "mergeability_unknown"
    if data["mergeable"] is False:
        return data, "not_mergeable"
    if data["mergeable_state"] not in ("clean", "has_hooks"):
        return data, "mergeability_unknown"
    return data, None


@mcp_tool(
    name="merge_pull_request",
    description="Merge после read-only preflight; обязательно expected_head_sha, без обхода protection или повторов PUT",
    parameters={
        "owner": {"type": "string"}, "repo": {"type": "string"}, "number": {"type": "integer"},
        "expected_head_sha": {"type": "string", "description": "Обязательный полный 40-hex SHA проверенного HEAD"},
        "merge_method": {"type": "string", "enum": ["merge", "squash", "rebase"], "description": "Default merge; запрещённый метод не заменяется автоматически"},
        "commit_title": {"type": "string"}, "commit_message": {"type": "string"},
    },
    required=["owner", "repo", "number", "expected_head_sha"],
)
def merge_pull_request(client: GitHubClient, **kwargs) -> str:
    missing = [k for k in ("owner", "repo", "number") if kwargs.get(k) is None]
    if missing:
        return f"❌ Не переданы обязательные параметры: {', '.join(missing)}"
    number = kwargs.get("number")
    expected = _full_sha(kwargs.get("expected_head_sha"))
    method = kwargs.get("merge_method", "merge")
    try:
        path = _pr_path(kwargs)
        if expected is None or method not in ("merge", "squash", "rebase"):
            raise ValueError("guard or method")
        if any(key in kwargs and (not isinstance(kwargs[key], str) or len(kwargs[key]) > 10000)
               for key in ("commit_title", "commit_message")):
            raise ValueError("message")
    except ValueError:
        return _merge_output(number, "invalid_input", "Valid expected_head_sha, method and PR identity required")
    evidence = {"expected_head_sha": expected, "merge_method": method, "merge_eligibility": "not_evaluated"}
    try:
        data, block = _snapshot_block(client._request("GET", path).json(), number, expected)
    except Exception:
        return _merge_output(number, "preflight_unknown", "PR read unavailable or invalid", **evidence)
    evidence["head_sha"] = data["head"]["sha"]
    if block:
        confirmed = block == "already_merged" and data["merge_commit_sha"] is not None
        return _merge_output(number, block if block != "already_merged" or confirmed else "unconfirmed",
                             block, merged=True if confirmed else None if block == "already_merged" else False,
                             sha=data["merge_commit_sha"] if confirmed else None,
                             **evidence, **({"http_status": 409} if block == "head_conflict" else {}))
    methods, error = _repo_methods(client, path)
    evidence["merge_method_flags"] = methods
    if methods[method] is not True:
        reason = "method_not_allowed" if methods[method] is False else "policy_unknown"
        return _merge_output(number, reason, reason, **evidence)
    try:
        text = get_commit_status(client, kwargs["owner"], kwargs["repo"], expected, max_rows=0)
        checks = json.loads(next(line[10:] for line in text.splitlines() if line.startswith("metadata: ")))
        valid = (checks.get("head_sha") == expected and checks.get("complete") is True
                 and checks.get("aggregate_state") in ("success", "no_checks"))
        evidence["checks"] = {"head_sha": checks.get("head_sha"), "aggregate_state": checks.get("aggregate_state"),
                              "complete": checks.get("complete"), "counts": checks.get("counts")}
    except Exception:
        valid = False
    if not valid:
        return _merge_output(number, "checks_not_ready", "Checks failed, pending, unavailable or incomplete", **evidence)
    # Re-read after potentially slow check pagination. The API SHA guard closes the final HEAD race.
    try:
        final, block = _snapshot_block(client._request("GET", path).json(), number, expected)
    except Exception:
        return _merge_output(number, "preflight_unknown", "Final PR read unavailable or invalid", **evidence)
    evidence["head_sha"] = final["head"]["sha"]
    if block:
        confirmed = block == "already_merged" and final["merge_commit_sha"] is not None
        return _merge_output(number, block if block != "already_merged" or confirmed else "unconfirmed",
                             "PR changed during preflight; inspect before another request",
                             merged=True if confirmed else None if block == "already_merged" else False,
                             sha=final["merge_commit_sha"] if confirmed else None, **evidence,
                             **({"http_status": 409} if block == "head_conflict" else {}))
    payload = {"sha": expected, "merge_method": method}
    for key in ("commit_title", "commit_message"):
        if key in kwargs:
            payload[key] = kwargs[key]
    try:
        response = client._request("PUT", path + "/merge", json=payload)
        result = response.json()
    except Exception as error:
        # Never reflect raw bodies/headers; classify only explicit HTTP refusal codes.
        match = re.match(r"^(?:Request failed: )*HTTP error (401|403|404|405|409|422)\b", str(error))
        if match:
            status = int(match.group(1))
            return _merge_output(number, "head_conflict" if status == 409 else "rejected", "GitHub refused merge",
                                 **evidence, http_status=status)
        return _merge_output(number, "unconfirmed", "Merge result unknown; inspect PR before any retry", merged=None, **evidence)
    if isinstance(result, dict) and result.get("merged") is False:
        return _merge_output(number, "rejected", _safe_text(result.get("message")) or "GitHub refused merge", **evidence)
    result_sha = _full_sha(result.get("sha")) if isinstance(result, dict) else None
    if isinstance(result, dict) and result.get("merged") is True and result_sha:
        return _merge_output(number, "merged", _safe_text(result.get("message")) or "Merged", merged=True, sha=result_sha, **evidence)
    return _merge_output(number, "unconfirmed", "Invalid merge response; inspect PR before any retry", merged=None, **evidence)


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
    missing = [k for k in ("owner", "repo", "number") if kwargs.get(k) is None]
    if missing:
        return f"❌ Не переданы обязательные параметры: {', '.join(missing)}"
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
