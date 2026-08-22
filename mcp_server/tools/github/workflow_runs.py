import os
import requests
import zipfile
import io
import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from mcp_server.tools import mcp_tool


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
def get_run_logs_by_step(
    owner: str,
    repo: str,
    run_id: int,
    step_name: Optional[str] = None,
    step_number: Optional[int] = None,
    job_id: Optional[int] = None,
    max_lines: int = 200,
    start_time: Optional[str] = None
):
    """
    Gets logs for a specific workflow step.
    
    Either step_name OR step_number (+ optional job_id) must be provided.
    
    Args:
        owner: Repository owner
        repo: Repository name
        run_id: Workflow run ID
        step_name: Step name (partial match, case insensitive) - use if you don't know the exact step number
        step_number: Step number (1-based index within the job) - more precise than name
        job_id: Job ID - if provided together with step_number, finds the step in that specific job
        max_lines: Maximum lines to return (default: 200)
        start_time: ISO 8601 start time (e.g. '2026-08-22T10:30:00Z')
                   - if provided, only logs after this time are returned
    """
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return {"error": "GITHUB_TOKEN not set"}
    
    # Validate parameters
    if not step_name and step_number is None:
        return {"error": "Either step_name or step_number must be provided"}
    
    # 1. Get job/step info to find the right log file
    jobs = _get_jobs_for_run(owner, repo, run_id, token)
    if not jobs:
        return {"error": "No jobs found for this run"}
    
    target_file_pattern = None
    found_job_name = None
    
    if step_number is not None:
        # Find step by number
        for job in jobs:
            if job_id is not None and job.get("id") != job_id:
                continue
            steps = job.get("steps", [])
            if 1 <= step_number <= len(steps):
                step = steps[step_number - 1]
                step_name_from_api = step.get("name", "")
                target_file_pattern = step_name_from_api
                found_job_name = job.get("name", "")
                if not start_time:
                    start_time = step.get("started_at")
                break
        
        if not target_file_pattern:
            return {"error": f"Step #{step_number} not found in the workflow run"}
    else:
        # Find step by name
        for job in jobs:
            steps = job.get("steps", [])
            for step in steps:
                step_name_from_api = step.get("name", "")
                if step_name.lower() in step_name_from_api.lower():
                    target_file_pattern = step_name_from_api
                    found_job_name = job.get("name", "")
                    if not start_time:
                        start_time = step.get("started_at")
                    break
            if target_file_pattern:
                break
        
        if not target_file_pattern:
            return {"error": f"No step found with name containing: {step_name}"}
    
    # 2. Download the logs ZIP
    logs_url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/logs"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }
    
    response = requests.get(logs_url, headers=headers)
    if response.status_code != 200:
        return {"error": f"Failed to download logs: {response.status_code}"}
    
    # 3. Extract logs from ZIP
    log_lines = []
    try:
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            # Try multiple ways to find the right file
            found_file = None
            
            # First, try exact match with job name and step name
            if found_job_name:
                expected_pattern = f"{found_job_name}/{target_file_pattern}".lower()
                for file_name in z.namelist():
                    if expected_pattern in file_name.lower():
                        found_file = file_name
                        break
            
            # If not found, try partial match with step name
            if not found_file and target_file_pattern:
                for file_name in z.namelist():
                    if target_file_pattern.lower() in file_name.lower():
                        found_file = file_name
                        break
            
            # If still not found, try to find any file containing the step name
            if not found_file and target_file_pattern:
                for file_name in z.namelist():
                    if target_file_pattern.lower() in file_name.lower():
                        found_file = file_name
                        break
            
            if not found_file:
                return {
                    "error": f"No log file found for step: {target_file_pattern}",
                    "available_files": z.namelist()[:10]
                }
            
            with z.open(found_file) as f:
                content = f.read().decode('utf-8', errors='ignore')
                lines = content.splitlines()
                
                # 4. Filter by time if start_time is provided
                if start_time:
                    try:
                        start_dt = _parse_iso_time(start_time)
                        found_start = False
                        filtered_lines = []
                        
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
                
                log_lines = lines
    except Exception as e:
        return {"error": f"Failed to extract logs: {e}"}
    
    if not log_lines:
        return {"error": f"No logs found for step: {target_file_pattern}"}
    
    # 5. Return first max_lines lines
    return {
        "run_id": run_id,
        "step_name": target_file_pattern,
        "job_name": found_job_name,
        "step_number": step_number,
        "job_id": job_id,
        "start_time": start_time,
        "total_lines": len(log_lines),
        "returned_lines": min(max_lines, len(log_lines)),
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
    Gets step logs via GitHub Checks API.
    Fast way to get errors without downloading the entire ZIP archive.
    
    Args:
        owner: Repository owner
        repo: Repository name
        run_id: Workflow run ID
        step_name: Step name (partial match, case insensitive)
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
        "note": "Checks API returns truncated output (up to 65535 characters). For full logs, use get_run_logs_by_step."
    }
