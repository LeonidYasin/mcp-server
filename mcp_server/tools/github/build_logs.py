"""One canonical implementation for both GitHub and build registry exports."""
from mcp_server.core.registry import mcp_tool
from .workflow_attempt_logs import PARAMETERS
from .workflow_diagnostics import platform_report

SCHEMA={"owner":{"type":"string"},"repo":{"type":"string"},"run_id":{"type":"integer"},
    "job_name":{"type":"string","description":"Уникальный job; неоднозначность не выбирает первый"},
    "step_name":{"type":"string"},**PARAMETERS}

@mcp_tool(name="get_android_build_error",description="ANDROID: attempt-pinned bounded heuristic diagnostics, не root-cause/success proof.",
    parameters=SCHEMA,required=["owner","repo","run_id"])
def get_android_build_error(client,owner,repo,run_id,job_name=None,run_attempt=None,
        max_pages=5,max_lines=100,max_chars=16000,step_name=None):
    return platform_report(client,owner,repo,run_id,"android",job_name,run_attempt,
                           max_pages,max_lines,max_chars,step_name)

@mcp_tool(name="get_ios_build_error",description="IOS: attempt-pinned bounded heuristic diagnostics, не root-cause/success proof.",
    parameters=SCHEMA,required=["owner","repo","run_id"])
def get_ios_build_error(client,owner,repo,run_id,job_name=None,run_attempt=None,
        max_pages=5,max_lines=100,max_chars=16000,step_name=None):
    return platform_report(client,owner,repo,run_id,"ios",job_name,run_attempt,
                           max_pages,max_lines,max_chars,step_name)
