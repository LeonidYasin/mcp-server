import os
import requests
import zipfile
import io
import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from mcp_server.decorators import mcp_tool


def _parse_iso_time(time_str: str) -> datetime:
    """Parse ISO 8601 time string to datetime object."""
    return datetime.fromisoformat(time_str.replace('Z', '+00:00'))


def _extract_timestamp(line: str) -> Optional[datetime]:
    """Extract ISO 8601 timestamp from a log line."""
    time_match = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)', line)
    if time_match:
        return _parse_iso_time(time_match.group(1))
    return None


def _get_jobs_for_run(owner: str, repo: str, run_id: int, token: str) -> List[Dict[str, Any]]:
    """Get jobs and steps for a workflow run via GitHub API."""
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return []
    
    data = response.json()
    return data.get("jobs", [])


@mcp_tool
def list_workflow_runs(
    owner: str,
    repo: str,
    limit: int = 10
):
    """
    Получает список последних запусков workflow с run_id, статусами и временем.
    
    Args:
        owner: Владелец репозитория
        repo: Имя репозитория
        limit: Количество запусков (по умолчанию 10)
    """
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return {"error": "GITHUB_TOKEN not set"}
    
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }
    params = {"per_page": limit}
    
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        return {"error": f"Failed to get workflow runs: {response.status_code}"}
    
    data = response.json()
    runs = data.get("workflow_runs", [])
    
    result = []
    for run in runs:
        result.append({
            "run_id": run.get("id"),
            "name": run.get("name"),
            "status": run.get("status"),
            "conclusion": run.get("conclusion"),
            "event": run.get("event"),
            "created_at": run.get("created_at"),
            "updated_at": run.get("updated_at"),
            "workflow_id": run.get("workflow_id"),
            "head_branch": run.get("head_branch"),
            "head_sha": run.get("head_sha")
        })
    
    return {
        "owner": owner,
        "repo": repo,
        "total": len(result),
        "runs": result
    }


@mcp_tool
def get_latest_run_id(
    owner: str,
    repo: str
):
    """
    Получает run_id последнего запуска workflow (успешного или нет).
    
    Args:
        owner: Владелец репозитория
        repo: Имя репозитория
    """
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return {"error": "GITHUB_TOKEN not set"}
    
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }
    params = {"per_page": 1}
    
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        return {"error": f"Failed to get workflow runs: {response.status_code}"}
    
    data = response.json()
    runs = data.get("workflow_runs", [])
    
    if not runs:
        return {"error": "No workflow runs found"}
    
    run = runs[0]
    return {
        "run_id": run.get("id"),
        "status": run.get("status"),
        "conclusion": run.get("conclusion"),
        "created_at": run.get("created_at"),
        "head_sha": run.get("head_sha")
    }


@mcp_tool
def get_workflow_run_steps(
    owner: str,
    repo: str,
    run_id: int
):
    """
    Получает список всех шагов для указанного запуска workflow с их статусами.
    
    Args:
        owner: Владелец репозитория
        repo: Имя репозитория
        run_id: ID запуска workflow
    """
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return {"error": "GITHUB_TOKEN not set"}
    
    jobs = _get_jobs_for_run(owner, repo, run_id, token)
    if not jobs:
        return {"error": "No jobs found for this run"}
    
    result = []
    for job in jobs:
        job_name = job.get("name", "")
        job_id = job.get("id")
        for step in job.get("steps", []):
            result.append({
                "job": job_name,
                "job_id": job_id,
                "step": step.get("name", ""),
                "number": step.get("number"),
                "status": step.get("status"),
                "conclusion": step.get("conclusion"),
                "started_at": step.get("started_at"),
                "completed_at": step.get("completed_at")
            })
    
    return {
        "owner": owner,
        "repo": repo,
        "run_id": run_id,
        "total_steps": len(result),
        "steps": result
    }


@mcp_tool
def get_run_logs_by_step(
    owner: str,
    repo: str,
    run_id: int,
    step_name: str,
    max_lines: int = 200,
    start_time: Optional[str] = None
):
    """
    Получает логи конкретного шага workflow по имени шага.
    Поддерживает фильтрацию по времени.
    
    Args:
        owner: Владелец репозитория
        repo: Имя репозитория
        run_id: ID запуска workflow
        step_name: Название шага (часть имени, регистр не важен)
        max_lines: Максимум строк для вывода (по умолчанию 200)
        start_time: ISO 8601 время начала (например 2026-08-22T10:30:00Z)
                   - если указано, выводятся логи только после этого времени
    """
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return {"error": "GITHUB_TOKEN not set"}
    
    # 1. Download the logs ZIP
    logs_url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/logs"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }
    
    response = requests.get(logs_url, headers=headers)
    if response.status_code != 200:
        return {"error": f"Failed to download logs: {response.status_code}"}
    
    # 2. Extract the ZIP
    log_lines = []
    try:
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            for file_name in z.namelist():
                # Find file containing the step name
                if step_name.lower() in file_name.lower():
                    with z.open(file_name) as f:
                        content = f.read().decode('utf-8', errors='ignore')
                        lines = content.splitlines()
                        
                        # 3. Filter by time if start_time is provided
                        if start_time:
                            try:
                                start_dt = _parse_iso_time(start_time)
                                filtered_lines = []
                                found_start = False
                                for line in lines:
                                    line_time = _extract_timestamp(line)
                                    if line_time:
                                        if line_time >= start_dt:
                                            found_start = True
                                    if found_start:
                                        filtered_lines.append(line)
                                lines = filtered_lines
                            except Exception as e:
                                return {"error": f"Failed to parse start_time: {e}"}
                        
                        log_lines.extend(lines)
                        break
    except Exception as e:
        return {"error": f"Failed to extract logs: {e}"}
    
    if not log_lines:
        return {"error": f"No logs found for step: {step_name}"}
    
    # 4. Return first max_lines lines
    return {
        "run_id": run_id,
        "step_name": step_name,
        "total_lines": len(log_lines),
        "returned_lines": min(max_lines, len(log_lines)),
        "start_time": start_time,
        "logs": log_lines[:max_lines]
    }


@mcp_tool
def get_step_logs_via_checks(
    owner: str,
    repo: str,
    run_id: int,
    step_name: str
):
    """
    Получает логи шага через GitHub Checks API.
    Быстрый способ получить ошибки без скачивания всего ZIP-архива.
    
    Args:
        owner: Владелец репозитория
        repo: Имя репозитория
        run_id: ID запуска workflow
        step_name: Название шага (часть имени, регистр не важен)
    """
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return {"error": "GITHUB_TOKEN not set"}
    
    # 1. Get run info to get commit SHA
    run_info_url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }
    
    response = requests.get(run_info_url, headers=headers)
    if response.status_code != 200:
        return {"error": f"Failed to get run info: {response.status_code}"}
    
    run_data = response.json()
    commit_sha = run_data.get("head_sha")
    if not commit_sha:
        return {"error": "No commit SHA found"}
    
    # 2. Get check-runs for this commit
    checks_url = f"https://api.github.com/repos/{owner}/{repo}/commits/{commit_sha}/check-runs"
    params = {"per_page": 100}
    
    response = requests.get(checks_url, headers=headers, params=params)
    if response.status_code != 200:
        return {"error": f"Failed to get check-runs: {response.status_code}"}
    
    checks_data = response.json()
    check_runs = checks_data.get("check_runs", [])
    
    # 3. Find check-run with the step name
    found_check = None
    for check in check_runs:
        check_name = check.get("name", "").lower()
        if step_name.lower() in check_name:
            found_check = check
            break
    
    if not found_check:
        return {
            "error": f"No check-run found for step: {step_name}",
            "available_checks": [c.get("name") for c in check_runs[:10]]
        }
    
    # 4. Return check-run data
    return {
        "run_id": run_id,
        "step_name": step_name,
        "commit_sha": commit_sha,
        "check_run": {
            "name": found_check.get("name"),
            "status": found_check.get("status"),
            "conclusion": found_check.get("conclusion"),
            "started_at": found_check.get("started_at"),
            "completed_at": found_check.get("completed_at"),
            "output": {
                "title": found_check.get("output", {}).get("title"),
                "summary": found_check.get("output", {}).get("summary"),
                "text": found_check.get("output", {}).get("text"),
                "annotations_count": len(found_check.get("output", {}).get("annotations", []))
            }
        },
        "note": "Checks API returns truncated output (up to 65535 characters). For full logs, use get_run_logs_by_step. "
    }
