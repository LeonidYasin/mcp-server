"""Build log analysis tools for Android and iOS."""

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


def _safe_utf8(text: str) -> str:
    """Safely encode string to UTF-8."""
    try:
        return text.encode('utf-8', errors='replace').decode('utf-8')
    except Exception:
        return str(text)


@mcp_tool(
    name="get_android_build_error",
    description="Get detailed Android APK build error from logs",
    parameters={
        "owner": {"type": "string", "description": "Repository owner"},
        "repo": {"type": "string", "description": "Repository name"},
        "run_id": {"type": "integer", "description": "Workflow run ID"},
        "job_name": {"type": "string", "description": "Job name (e.g. build-android)"},
    },
    required=["owner", "repo", "run_id"],
)
def get_android_build_error(client: GitHubClient, owner: str, repo: str, run_id: int, job_name: str = "build-android") -> str:
    """Get detailed Android build error."""
    try:
        jobs = client.get_workflow_jobs(owner, repo, run_id)

        target_job = None
        for job in jobs:
            if job_name in job.get('name', '').lower():
                target_job = job
                break

        if not target_job:
            available = [j.get('name', 'unknown') for j in jobs]
            return _safe_utf8(f"Job '{job_name}' not found. Available: {', '.join(available)}")

        job_id = target_job.get('id')
        if not job_id:
            return "Could not get job ID"

        logs = client.get_job_logs(owner, repo, job_id)
        lines = logs.split('\n')

        error_lines = []
        for line in lines:
            if 'FAILURE' in line.upper() or 'ERROR' in line.upper() or 'Exception' in line:
                error_lines.append(line.strip())

        result = [
            f"ANALYZING ANDROID BUILD",
            f"Job: {target_job.get('name')}",
            f"Status: {target_job.get('status')}",
            f"Conclusion: {target_job.get('conclusion')}",
            f"Total log lines: {len(lines)}",
            ""
        ]

        if error_lines:
            result.append(f"Found {len(error_lines)} error(s):")
            result.append("")
            for err in error_lines[:10]:
                result.append(_safe_utf8(err))
        else:
            result.append("No explicit errors found in logs.")
            result.append("")
            result.append("Last 20 lines:")
            for line in lines[-20:]:
                result.append(_safe_utf8(line))

        return _safe_utf8('\n'.join(result))

    except Exception as e:
        return _safe_utf8(f"Error: {e}")


@mcp_tool(
    name="get_ios_build_error",
    description="Get detailed iOS build error from logs",
    parameters={
        "owner": {"type": "string", "description": "Repository owner"},
        "repo": {"type": "string", "description": "Repository name"},
        "run_id": {"type": "integer", "description": "Workflow run ID"},
        "job_name": {"type": "string", "description": "Job name (e.g. build-ios)"},
    },
    required=["owner", "repo", "run_id"],
)
def get_ios_build_error(client: GitHubClient, owner: str, repo: str, run_id: int, job_name: str = "build-ios") -> str:
    """Get detailed iOS build error."""
    try:
        jobs = client.get_workflow_jobs(owner, repo, run_id)

        target_job = None
        for job in jobs:
            if job_name in job.get('name', '').lower():
                target_job = job
                break

        if not target_job:
            available = [j.get('name', 'unknown') for j in jobs]
            return _safe_utf8(f"Job '{job_name}' not found. Available: {', '.join(available)}")

        job_id = target_job.get('id')
        if not job_id:
            return "Could not get job ID"

        logs = client.get_job_logs(owner, repo, job_id)
        lines = logs.split('\n')

        error_lines = []
        for line in lines:
            if 'FAILURE' in line.upper() or 'ERROR' in line.upper() or 'Exception' in line or 'error:' in line.lower():
                error_lines.append(line.strip())

        result = [
            f"ANALYZING iOS BUILD",
            f"Job: {target_job.get('name')}",
            f"Status: {target_job.get('status')}",
            f"Conclusion: {target_job.get('conclusion')}",
            f"Total log lines: {len(lines)}",
            ""
        ]

        if error_lines:
            result.append(f"Found {len(error_lines)} error(s):")
            result.append("")
            for err in error_lines[:10]:
                result.append(_safe_utf8(err))
        else:
            result.append("No explicit errors found in logs.")
            result.append("")
            result.append("Last 20 lines:")
            for line in lines[-20:]:
                result.append(_safe_utf8(line))

        return _safe_utf8('\n'.join(result))

    except Exception as e:
        return _safe_utf8(f"Error: {e}")
