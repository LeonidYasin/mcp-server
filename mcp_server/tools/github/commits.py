"""MCP tools: commit and workflow operations."""

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


@mcp_tool(
    name="list_commits",
    description="Получает список коммитов репозитория",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "sha": {"type": "string", "description": "Ветка или SHA"},
    },
    required=["owner", "repo"],
)
def list_commits(client: GitHubClient, **kwargs) -> str:
    commits = client.list_commits(kwargs["owner"], kwargs["repo"], kwargs.get("sha"))
    if not commits:
        return "Нет коммитов"
    lines = []
    for c in commits[:10]:
        sha_short = c["sha"][:7]
        msg = c["commit"]["message"].splitlines()[0]
        lines.append(f"{sha_short} - {msg}")
    return "\n".join(lines)


@mcp_tool(
    name="get_commit_status",
    description="Получает статус проверок для конкретного коммита",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "sha": {"type": "string", "description": "SHA коммита"},
    },
    required=["owner", "repo", "sha"],
)
def get_commit_status(client: GitHubClient, **kwargs) -> str:
    status = client.get_commit_status(kwargs["owner"], kwargs["repo"], kwargs["sha"])
    checks = client.get_check_runs(kwargs["owner"], kwargs["repo"], kwargs["sha"])
    output = f"🔖 Коммит: {kwargs['sha']}\n📊 Статус: {status.get('state', 'unknown')}\n\n"
    if checks:
        failed = [c for c in checks if c.get("conclusion") == "failure"]
        pending = [c for c in checks if c.get("status") == "in_progress"]
        success = [c for c in checks if c.get("conclusion") == "success"]
        if failed:
            output += f"❌ Проваленных: {len(failed)}\n"
            for c in failed:
                output += f"   - {c.get('name')}: {c.get('conclusion')}\n"
        if pending:
            output += f"⏳ В процессе: {len(pending)}\n"
        if success:
            output += f"✅ Успешных: {len(success)}\n"
    else:
        output += "ℹ️ Нет проверок"
    return output


@mcp_tool(
    name="get_latest_workflow_error",
    description="Получает ошибку последней сборки через GitHub API",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
    },
    required=["owner", "repo"],
)
def get_latest_workflow_error(client: GitHubClient, **kwargs) -> str:
    runs = client.get_workflow_runs(kwargs["owner"], kwargs["repo"], 1)
    if not runs:
        return "Нет запусков workflow"
    run = runs[0]
    jobs = client.get_workflow_jobs(kwargs["owner"], kwargs["repo"], run["id"])
    failed = [j for j in jobs if j.get("conclusion") == "failure"]
    if failed:
        return f"❌ Ошибка в: {failed[0].get('name', 'unknown')}"
    return f"✅ Успех (run #{run['id']})"


@mcp_tool(
    name="get_workflow_run_logs",
    description="Получает логи и причину падения конкретного workflow run",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "run_id": {"type": "integer"},
    },
    required=["owner", "repo", "run_id"],
)
def get_workflow_run_logs(client: GitHubClient, **kwargs) -> str:
    run = client.get_workflow_run(kwargs["owner"], kwargs["repo"], kwargs["run_id"])
    jobs = client.get_workflow_jobs(kwargs["owner"], kwargs["repo"], kwargs["run_id"])
    output = f"🏃 Запуск #{kwargs['run_id']}\n"
    output += f"📌 Статус: {run.get('status')}\n"
    output += f"📊 Результат: {run.get('conclusion')}\n"
    output += f"🌿 Ветка: {run.get('head_branch')}\n"
    output += f"🔖 Коммит: {run.get('head_sha', '')[:7]}\n\n"
    failed_jobs = [j for j in jobs if j.get("conclusion") == "failure"]
    if failed_jobs:
        output += "❌ НАЙДЕНЫ ОШИБКИ:\n"
        for job in failed_jobs:
            output += f"📦 Job: {job.get('name')}\n   Статус: {job.get('status')}\n"
            for step in job.get("steps", []):
                if step.get("conclusion") == "failure":
                    output += f"   ❌ {step.get('name')}\n"
    else:
        output += "✅ Все проверки успешны"
    return output


@mcp_tool(
    name="get_full_workflow_logs",
    description="Получает ПОЛНЫЕ логи всех jobs для конкретного workflow run",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "run_id": {"type": "integer"},
    },
    required=["owner", "repo", "run_id"],
)
def get_full_workflow_logs(client: GitHubClient, **kwargs) -> str:
    jobs = client.get_workflow_jobs(kwargs["owner"], kwargs["repo"], kwargs["run_id"])
    output = f"📋 ПОЛНЫЕ ЛОГИ для запуска #{kwargs['run_id']}\nВсего jobs: {len(jobs)}\n{'=' * 60}\n\n"
    for job in jobs:
        output += f"📦 JOB: {job.get('name')}\n   Статус: {job.get('status')}\n   Результат: {job.get('conclusion')}\n"
        job_id = job.get("id")
        if job_id:
            try:
                logs = client.get_job_logs(kwargs["owner"], kwargs["repo"], job_id)
                log_lines = logs.split("\n")
                output += f"\n   📄 ЛОГИ (первые 50 из {len(log_lines)}):\n   {'-' * 40}\n"
                output += "\n".join(f"   {line}" for line in log_lines[:50])
                if len(log_lines) > 50:
                    output += f"\n   ... (обрезано, всего {len(log_lines)} строк)"
                output += f"\n   {'-' * 40}\n"
            except Exception as e:
                output += f"\n   ⚠️ Ошибка получения логов: {e}\n"
        output += f"\n{'-' * 40}\n\n"
    return output


@mcp_tool(
    name="get_workflow_by_file",
    description="Получает последние запуски workflow по имени YAML файла",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "filename": {"type": "string", "description": "Имя YAML файла (например build.yml)"},
    },
    required=["owner", "repo", "filename"],
)
def get_workflow_by_file(client: GitHubClient, **kwargs) -> str:
    workflows = client.get_workflows(kwargs["owner"], kwargs["repo"])
    target = None
    for wf in workflows:
        if wf.get("name") == kwargs["filename"] or wf.get("path", "").endswith(kwargs["filename"]):
            target = wf
            break
    if not target:
        return f"❌ Workflow '{kwargs['filename']}' не найден"
    runs = client.get_workflow_runs_by_id(kwargs["owner"], kwargs["repo"], target["id"], 5)
    output = f"📄 Workflow: {target['name']}\n📁 Файл: {target['path']}\n\n📋 Последние запуски:\n"
    for run in runs:
        icon = "✅" if run.get("conclusion") == "success" else "❌" if run.get("conclusion") == "failure" else "⏳"
        output += f"  {icon} #{run['id']} - {run['head_sha'][:7]} - {run.get('conclusion', 'pending')} - {run['created_at'][:10]}\n"
    return output
