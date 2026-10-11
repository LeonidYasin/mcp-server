"""MCP tools: GitHub Actions control."""

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


@mcp_tool(
    name="list_workflows",
    description="Список workflows репозитория (с пагинацией)",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "limit": {"type": "integer", "description": "Сколько на странице (по умолчанию 30, максимум 100)"},
        "page": {"type": "integer", "description": "Номер страницы (по умолчанию 1)"},
    },
    required=["owner", "repo"],
)
def list_workflows(client: GitHubClient, **kwargs) -> str:
    limit = max(1, min(int(kwargs.get("limit", 30)), 100))
    page = max(1, int(kwargs.get("page", 1)))
    resp = client._request(
        "GET",
        f"/repos/{kwargs['owner']}/{kwargs['repo']}/actions/workflows",
        params={"per_page": limit, "page": page},
    )
    data = resp.json()
    items = data.get("workflows", [])
    total = data.get("total_count", len(items))
    if not items:
        return f"Workflows (стр. {page}): нет"
    lines = [f"Workflows (стр. {page}, всего {total}, показано {len(items)}):"]
    for w in items:
        lines.append(f"  [{w['state']}] {w['name']} — {w['path']} (id={w['id']})")
    return "\n".join(lines)


@mcp_tool(
    name="dispatch_workflow",
    description="Запускает workflow вручную (workflow_dispatch)",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "workflow_id": {"type": "string", "description": "Имя файла или ID workflow (напр. build.yml)"},
        "ref": {"type": "string", "description": "Ветка (по умолчанию main)"},
        "inputs": {"type": "object", "description": "Входные параметры workflow"},
    },
    required=["owner", "repo", "workflow_id"],
)
def dispatch_workflow(client: GitHubClient, **kwargs) -> str:
    payload = {"ref": kwargs.get("ref", "main")}
    if kwargs.get("inputs"):
        payload["inputs"] = kwargs["inputs"]
    client._request(
        "POST",
        f"/repos/{kwargs['owner']}/{kwargs['repo']}/actions/workflows/{kwargs['workflow_id']}/dispatches",
        json=payload,
    )
    return f"✅ Workflow '{kwargs['workflow_id']}' запущен на {payload['ref']}"


@mcp_tool(
    name="rerun_workflow",
    description="Перезапускает workflow run",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "run_id": {"type": "integer"},
        "failed_only": {"type": "boolean", "description": "Только упавшие jobs"},
    },
    required=["owner", "repo", "run_id"],
)
def rerun_workflow(client: GitHubClient, **kwargs) -> str:
    if kwargs.get("failed_only"):
        path = f"/repos/{kwargs['owner']}/{kwargs['repo']}/actions/runs/{kwargs['run_id']}/rerun-failed-jobs"
    else:
        path = f"/repos/{kwargs['owner']}/{kwargs['repo']}/actions/runs/{kwargs['run_id']}/rerun"
    client._request("POST", path)
    return f"✅ Run {kwargs['run_id']} перезапущен"


@mcp_tool(
    name="rerun_failed_jobs",
    description=(
        "Перезапускает ТОЛЬКО упавшие jobs запуска (POST .../rerun-failed-jobs). "
        "Позволяет перепроверить фикс без нового пуша (не плодит коммиты). "
        "Эквивалент rerun_workflow(failed_only=true)."
    ),
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "run_id": {"type": "integer"},
    },
    required=["owner", "repo", "run_id"],
)
def rerun_failed_jobs(client: GitHubClient, **kwargs) -> str:
    client._request(
        "POST",
        f"/repos/{kwargs['owner']}/{kwargs['repo']}/actions/runs/{kwargs['run_id']}/rerun-failed-jobs",
    )
    return f"✅ Упавшие jobs run {kwargs['run_id']} перезапущены"


@mcp_tool(
    name="cancel_workflow",
    description="Отменяет выполняющийся workflow run",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "run_id": {"type": "integer"},
    },
    required=["owner", "repo", "run_id"],
)
def cancel_workflow(client: GitHubClient, **kwargs) -> str:
    client._request(
        "POST",
        f"/repos/{kwargs['owner']}/{kwargs['repo']}/actions/runs/{kwargs['run_id']}/cancel",
    )
    return f"✅ Run {kwargs['run_id']} отменён"


@mcp_tool(
    name="list_artifacts",
    description="Список артефактов workflow run",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "run_id": {"type": "integer"},
    },
    required=["owner", "repo", "run_id"],
)
def list_artifacts(client: GitHubClient, **kwargs) -> str:
    resp = client._request(
        "GET", f"/repos/{kwargs['owner']}/{kwargs['repo']}/actions/runs/{kwargs['run_id']}/artifacts"
    )
    items = resp.json().get("artifacts", [])
    if not items:
        return "Артефактов нет"
    lines = [f"Артефакты ({len(items)}):"]
    for a in items:
        size_kb = a.get("size_in_bytes", 0) / 1024
        lines.append(f"  {a['name']} — {size_kb:.1f} KB (id={a['id']}, expired={a.get('expired')})")
    return "\n".join(lines)


# Kept re-exported here for existing imports and registry discovery.
from mcp_server.tools.github.artifacts import download_artifact
