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


@mcp_tool(
    name="download_artifact",
    description=(
        "Скачивание артефакта workflow: возвращает подписанную (временную) ссылку "
        "archive_download_url на ZIP. Сам файл НЕ скачивается на диск. "
        "Принимает artifact_id (из list_artifacts) или name — тогда id ищется по имени."
    ),
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "artifact_id": {"type": "integer", "description": "ID артефакта (из list_artifacts)"},
        "name": {"type": "string", "description": "Имя артефакта (если artifact_id не задан)"},
        "run_id": {"type": "integer", "description": "ID запуска (нужен, если ищем по name)"},
    },
    required=["owner", "repo"],
)
def download_artifact(client: GitHubClient, **kwargs) -> str:
    owner, repo = kwargs["owner"], kwargs["repo"]
    artifact_id = kwargs.get("artifact_id")
    name = (kwargs.get("name") or "").strip()
    run_id = kwargs.get("run_id")

    # Если id не передан — ищем по имени (в конкретном run или по всему репо)
    if not artifact_id:
        if not name:
            return "❌ Нужен artifact_id или name (плюс run_id для поиска по имени)."
        if run_id:
            resp = client._request(
                "GET",
                f"/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts",
                params={"name": name},
            )
        else:
            resp = client._request(
                "GET", f"/repos/{owner}/{repo}/actions/artifacts", params={"name": name}
            )
        found = resp.json().get("artifacts", [])
        if not found:
            return f"❌ Артефакт '{name}' не найден в {owner}/{repo}."
        art = found[0]
        artifact_id = art["id"]
    else:
        resp = client._request(
            "GET", f"/repos/{owner}/{repo}/actions/artifacts/{artifact_id}"
        )
        art = resp.json()

    if art.get("expired"):
        return f"❌ Артефакт '{art.get('name')}' (id={artifact_id}) просрочен (expired) и недоступен."

    size_mb = art.get("size_in_bytes", 0) / (1024 * 1024)
    created = art.get("created_at", "?")
    # archive_download_url — подписанная ссылка, действительна ограниченное время
    url = art.get("archive_download_url") or (
        f"{GitHubClient.BASE_URL}/repos/{owner}/{repo}/actions/artifacts/{artifact_id}/zip"
    )
    return (
        f"📦 Артефакт: {art.get('name')} (id={artifact_id})\n"
        f"   Размер: {size_mb:.2f} MB\n"
        f"   Создан: {created}\n"
        f"   Expired: {art.get('expired')}\n"
        f"   🔗 Скачать (ZIP, временная ссылка):\n{url}\n"
        f"\nℹ️ Ссылка подписанная и временная — качай сразу. "
        f"Требует заголовок Authorization: Bearer <token> (для приватных репо)."
    )
