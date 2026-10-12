"""Attempt-pinned workflow diagnostic adapters; legacy names, bounded results."""
from mcp_server.core.registry import mcp_tool
from .client import GitHubClient
from .workflow_attempts import snapshot, PARAMETERS as SNAPSHOT_PARAMETERS, _integer
from .workflow_attempt_logs import query, PARAMETERS as LOG_PARAMETERS
from .workflow_diagnostics import latest_snapshot
from .commits import _safe_text

IDENTITY = {"owner":{"type":"string"},"repo":{"type":"string"},"run_id":{"type":"integer"}}

@mcp_tool(name="get_latest_workflow_error",description="Последний run: attempt-pinned snapshot, не объявляет success по отсутствию ошибок.",
    parameters={"owner":{"type":"string"},"repo":{"type":"string"},**SNAPSHOT_PARAMETERS},required=["owner","repo"])
def get_latest_workflow_error(client,owner,repo,run_attempt=None,max_pages=5,max_jobs=20,max_steps=100):
    return latest_snapshot(client,owner,repo,run_attempt,max_pages,max_jobs,max_steps)

@mcp_tool(name="get_workflow_run_logs",description="Attempt-pinned bounded tail ИЛИ grep; не считает отсутствие ошибок успешной сборкой.",
    parameters={**IDENTITY,**LOG_PARAMETERS,"job_name":{"type":"string"},"step_name":{"type":"string"},
        "tail_lines":{"type":"integer","description":"Глобальный tail 0–100, default15;0 без grep => только metadata"},
        "context_before":{"type":"integer","description":"Дополнительные tail строки 0–200"},
        "grep_pattern":{"type":"string"},"grep_context":{"type":"integer","description":"0–20, default1"}},
    required=["owner","repo","run_id"])
def get_workflow_run_logs(client,owner,repo,run_id,tail_lines=15,context_before=0,
        grep_pattern=None,grep_context=1,run_attempt=None,max_pages=5,max_lines=200,max_chars=16000,
        job_name=None,step_name=None):
    if (not _integer(tail_lines,0,100) or not _integer(context_before,0,200)
            or not _integer(grep_context,0,20) or not _integer(max_lines,1,1000)
            or not _integer(max_chars,1,65536)):
        return {"complete":False,"error":"invalid_input"}
    if grep_pattern is None and tail_lines==0:
        return snapshot(client,owner,repo,run_id,run_attempt,max_pages,20,100)
    result=query(client,"grep" if grep_pattern is not None else "offset",owner=owner,repo=repo,
        run_id=run_id,run_attempt=run_attempt,max_pages=max_pages,job_name=job_name,step_name=step_name,
        pattern=grep_pattern,context=grep_context,direction="tail",
        max_lines=max_lines if grep_pattern is not None else min(max_lines,tail_lines+context_before),max_chars=max_chars)
    result['scope']="selected_step" if step_name else "archive_or_explicit_job"
    result['no_matches_means_success']=False
    return result

@mcp_tool(name="get_full_workflow_logs",description="Legacy full name: bounded attempt archive window; полный вывод НЕ гарантируется.",
    parameters={**IDENTITY,**LOG_PARAMETERS,"offset":{"type":"integer"},"job_name":{"type":"string"},"step_name":{"type":"string"}},
    required=["owner","repo","run_id"])
def get_full_workflow_logs(client,owner,repo,run_id,run_attempt=None,max_pages=5,max_lines=200,
        max_chars=16000,offset=0,job_name=None,step_name=None):
    result=query(client,"offset",owner=owner,repo=repo,run_id=run_id,run_attempt=run_attempt,max_pages=max_pages,
        max_lines=max_lines,max_chars=max_chars,offset=offset,job_name=job_name,step_name=step_name)
    result['legacy_full_name_bounded']=True
    return result

@mcp_tool(name="get_workflow_logs_preview",description="Глобальное bounded preview выбранной попытки; limit не умножается на jobs.",
    parameters={**IDENTITY,**LOG_PARAMETERS,"limit":{"type":"integer","description":"1–1000, default50"},"job_name":{"type":"string"},"step_name":{"type":"string"}},
    required=["owner","repo","run_id"])
def get_workflow_logs_preview(client,owner,repo,run_id,limit=50,run_attempt=None,max_pages=5,max_lines=200,
        max_chars=16000,job_name=None,step_name=None):
    if not _integer(limit,1,1000) or not _integer(max_lines,1,1000):
        return {"complete":False,"error":"invalid_input"}
    return query(client,"offset",owner=owner,repo=repo,run_id=run_id,run_attempt=run_attempt,max_pages=max_pages,
        max_lines=min(limit,max_lines),max_chars=max_chars,job_name=job_name,step_name=step_name)

@mcp_tool(
    name="get_workflow_by_file",
    description="Получает последние запуски workflow по имени YAML файла",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "filename": {"type": "string", "description": "Имя файла workflow (например build.yml)"},
    },
    required=["owner", "repo", "filename"],
)
def get_workflow_by_file(client: GitHubClient, owner: str, repo: str, filename: str) -> str:
    """Get workflow runs by filename."""
    try:
        workflows = client.get_workflows(owner, repo)
        target = None
        for wf in workflows:
            if wf.get("name") == filename or wf.get("path", "").endswith(filename):
                target = wf
                break

        if not target:
            return str(f"❌ Workflow '{filename}' не найден")

        runs = client.get_workflow_runs_by_id(owner, repo, target["id"])

        lines = [
            f"📄 Workflow: {target['name']}",
            f"📁 Файл: {target['path']}",
            "",
            f"📋 Последние {len(runs)} запусков:",
        ]

        for run in runs:
            conclusion = run.get("conclusion", "pending")
            icon = {"success": "✅", "failure": "❌"}.get(conclusion, "⏳")
            lines.append(
                f"  {icon} #{run['id']} - {(run.get('head_sha') or '')[:7]} "
                f"- {conclusion} - {run.get('created_at', '')[:10]}"
            )

        return str("\n".join(lines))
    except Exception as e:
        return {"error":"workflow_listing_unavailable"}
