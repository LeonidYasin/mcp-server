import os
import requests
import zipfile
import io
import re
from datetime import datetime
from typing import Optional
from mcp_server.decorators import mcp_tool


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
    Gets logs for a specific workflow step by step name.
    
    Args:
        owner: Repository owner
        repo: Repository name
        run_id: Workflow run ID
        step_name: Step name (partial match, case insensitive)
        max_lines: Maximum lines to return (default: 200)
        start_time: ISO 8601 start time (e.g. '2026-08-22T10:30:00Z')
                   - if provided, only logs after this time are returned
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
                                start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                                filtered_lines = []
                                for line in lines:
                                    # Look for timestamp in the line
                                    time_match = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)', line)
                                    if time_match:
                                        line_time = datetime.fromisoformat(time_match.group(1).replace('Z', '+00:00'))
                                        if line_time >= start_dt:
                                            filtered_lines.append(line)
                                    else:
                                        # If no timestamp, keep the line (it might be part of the log)
                                        filtered_lines.append(line)
                                lines = filtered_lines
                            except Exception as e:
                                return {"error": f"Failed to parse start_time: {e}"}
                        
                        log_lines.extend(lines)
                        break  # Found the right file
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
