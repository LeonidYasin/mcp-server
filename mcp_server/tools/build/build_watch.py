"""Read-only build snapshots; unsafe template-to-main autofix is disabled."""
from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.workflow_attempts import PARAMETERS, snapshot

@mcp_tool(name="watch_build",description="Мгновенный attempt-pinned snapshot; interval/timeout игнорируются, без polling.",
    parameters={"owner":{"type":"string"},"repo":{"type":"string"},"run_id":{"type":"integer"},
        "interval":{"type":"integer","description":"Deprecated, ignored"},
        "timeout":{"type":"integer","description":"Deprecated, ignored"},**PARAMETERS},
    required=["owner","repo","run_id"])
def watch_build(client,owner,repo,run_id,interval=10,timeout=600,run_attempt=None,max_pages=5,max_jobs=20,max_steps=100):
    result=snapshot(client,owner,repo,run_id,run_attempt,max_pages,max_jobs,max_steps)
    result['monitoring_mode']='single_snapshot'
    result['interval_timeout_ignored']=True
    return result

@mcp_tool(name="auto_fix_build",description="Отключён unsafe template-to-main autofix; нужен reviewed fix в отдельной ветке/PR. Ничего не пишет.",
    parameters={"owner":{"type":"string"},"repo":{"type":"string"},"run_id":{"type":"integer"},"platform":{"type":"string"}},
    required=["owner","repo","run_id","platform"])
def auto_fix_build(client,owner,repo,run_id,platform):
    return {'complete':False,'error':'auto_fix_requires_reviewed_pr','writes_performed':False,
        'note':'Use read-only diagnostic tools, inspect repository-specific sources, then a reviewed branch/PR; no generic templates to main.'}
