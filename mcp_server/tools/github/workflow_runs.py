"""GitHub workflow runs tools: list_workflow_runs, get_latest_run_id, get_run_logs_by_step, get_workflow_run_steps, get_step_logs_via_checks."""

import os
import requests
import zipfile
import io
import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


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


def _safe_utf8(text: str) -> str:
    """Безопасно преобразует строку в UTF-8, заменяя проблемные символы."""
    try:
        return text.encode('utf-8', errors='replace').decode('utf-8')
    except Exception:
        return str(text)


@mcp_tool(
    name="list_workflow_runs",
    description="Получает список последних запусков workflow с run_id, статусами и временем",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "limit": {"type": "integer", "description": "Количество запусков (по умолчанию 10)"},
    },
    required=["owner", "repo"],
)
def list_workflow_runs(client: GitHubClient, owner: str, repo: str, limit: int = 10) -> str:
    """Get list of workflow runs with run_id, status, and time."""
    try:
        runs = client.get_workflow_runs(owner, repo, per_page=limit)
        if not runs:
            return _safe_utf8("Нет запусков workflow")

        lines = [
            f"📋 Последние {len(runs)} запусков workflow в {owner}/{repo}:",
            "=" * 60,
            ""
        ]

        for run in runs:
            run_id = run.get("id")
            status = run.get("status", "unknown")
            conclusion = run.get("conclusion", "")
            branch = run.get("head_branch", "")
            created_at = run.get("created_at", "")
            
            status_icon = "✅" if conclusion == "success" else "❌" if conclusion == "failure" else "⏳"
            lines.append(f"{status_icon} #{run_id} | {status} | {conclusion} | {branch} | {created_at}")

        return _safe_utf8("\n".join(lines))
    except Exception as e:
        return _safe_utf8(f"❌ Ошибка: {e}")


@mcp_tool(
    name="get_latest_run_id",
    description="Получает run_id последнего запуска workflow (успешного или нет)",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
    },
    required=["owner", "repo"],
)
def get_latest_run_id(client: GitHubClient, owner: str, repo: str) -> str:
    """Get the latest workflow run ID."""
    try:
        runs = client.get_workflow_runs(owner, repo, per_page=1)
        if not runs:
            return _safe_utf8("Нет запусков workflow")

        run = runs[0]
        run_id = run.get("id")
        status = run.get("status", "unknown")
        conclusion = run.get("conclusion", "")
        
        return _safe_utf8(f"✅ Последний запуск: #{run_id} | Статус: {status} | Результат: {conclusion}")
    except Exception as e:
        return _safe_utf8(f"❌ Ошибка: {e}")


@mcp_tool(
    name="get_workflow_run_steps",
    description="Получает список всех шагов для указанного запуска workflow с их статусами",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "run_id": {"type": "integer", "description": "ID запуска workflow"},
    },
    required=["owner", "repo", "run_id"],
)
def get_workflow_run_steps(client: GitHubClient, owner: str, repo: str, run_id: int) -> str:
    """Get all steps for a workflow run with their statuses."""
    try:
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            return _safe_utf8("❌ GITHUB_TOKEN не установлен")

        jobs = _get_jobs_for_run(owner, repo, run_id, token)
        if not jobs:
            return _safe_utf8(f"Нет jobs для запуска #{run_id}")

        lines = [
            f"📋 Шаги для запуска #{run_id}:",
            "=" * 60,
            ""
        ]

        for job in jobs:
            job_name = job.get("name", "unknown")
            job_status = job.get("status", "unknown")
            job_conclusion = job.get("conclusion", "")
            
            lines.append(f"📦 JOB: {job_name} [{job_status} / {job_conclusion}]")
            
            for step in job.get("steps", []):
                step_name = step.get("name", "unknown")
                step_status = step.get("status", "unknown")
                step_conclusion = step.get("conclusion", "")
                started_at = step.get("started_at", "")
                
                icon = "✅" if step_conclusion == "success" else "❌" if step_conclusion == "failure" else "⏳"
                lines.append(f"  {icon} {step_name} [{step_status} / {step_conclusion}] {started_at}")
            
            lines.append("")

        return _safe_utf8("\n".join(lines))
    except Exception as e:
        return _safe_utf8(f"❌ Ошибка: {e}")


@mcp_tool(
    name="get_run_logs_by_step",
    description="Получает логи конкретного шага workflow по имени шага. Поддерживает фильтрацию по времени.",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "run_id": {"type": "integer", "description": "ID запуска workflow"},
        "step_name": {"type": "string", "description": "Название шага (часть имени, регистр не важен)"},
        "max_lines": {"type": "integer", "description": "Максимум строк для вывода (по умолчанию 200)"},
        "start_time": {"type": "string", "description": "ISO 8601 время начала (например 2026-08-22T10:30:00Z) - если указано, выводятся логи только после этого времени"},
    },
    required=["owner", "repo", "run_id", "step_name"],
)
def get_run_logs_by_step(
    client: GitHubClient,
    owner: str,
    repo: str,
    run_id: int,
    step_name: str,
    max_lines: int = 200,
    start_time: Optional[str] = None
) -> str:
    """Get logs for a specific workflow step by step name."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return _safe_utf8("❌ GITHUB_TOKEN не установлен")
    
    try:
        # 1. Download the logs ZIP
        logs_url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/logs"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json"
        }
        
        response = requests.get(logs_url, headers=headers)
        if response.status_code != 200:
            return _safe_utf8(f"❌ Не удалось скачать логи: {response.status_code}")
        
        # 2. Extract the ZIP
        log_lines = []
        found_file = None
        
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            # Find file containing the step name
            for file_name in z.namelist():
                if step_name.lower() in file_name.lower():
                    found_file = file_name
                    break
            
            if not found_file:
                return _safe_utf8(f"❌ Не найден файл с логами для шага: {step_name}")
            
            with z.open(found_file) as f:
                content = f.read().decode('utf-8', errors='ignore')
                lines = content.splitlines()
                
                # 3. Filter by time if start_time is provided
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
                        return _safe_utf8(f"❌ Ошибка парсинга start_time: {e}")
                
                log_lines = lines
        
        if not log_lines:
            return _safe_utf8(f"❌ Нет логов для шага: {step_name}")
        
        # 4. Return first max_lines lines
        result_lines = [
            f"📄 Логи для шага '{step_name}' (запуск #{run_id})",
            f"📊 Всего строк: {len(log_lines)}",
            f"📊 Показано: {min(max_lines, len(log_lines))}",
            f"🕐 С фильтром по времени: {start_time if start_time else 'нет'}",
            "=" * 60,
            ""
        ]
        
        for line in log_lines[:max_lines]:
            result_lines.append(_safe_utf8(line))
        
        if len(log_lines) > max_lines:
            result_lines.append(f"\n... и еще {len(log_lines) - max_lines} строк")
        
        return _safe_utf8("\n".join(result_lines))
    except Exception as e:
        return _safe_utf8(f"❌ Ошибка: {e}")


@mcp_tool(
    name="get_step_logs_via_checks",
    description="Получает логи шага через GitHub Checks API. Быстрый способ получить ошибки без скачивания всего ZIP-архива.",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "run_id": {"type": "integer", "description": "ID запуска workflow"},
        "step_name": {"type": "string", "description": "Название шага (часть имени, регистр не важен)"},
    },
    required=["owner", "repo", "run_id", "step_name"],
)
def get_step_logs_via_checks(
    client: GitHubClient,
    owner: str,
    repo: str,
    run_id: int,
    step_name: str
) -> str:
    """Get step logs via GitHub Checks API."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return _safe_utf8("❌ GITHUB_TOKEN не установлен")
    
    try:
        # 1. Get run info to get commit SHA
        run_info_url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json"
        }
        
        response = requests.get(run_info_url, headers=headers)
        if response.status_code != 200:
            return _safe_utf8(f"❌ Не удалось получить информацию о запуске: {response.status_code}")
        
        run_data = response.json()
        commit_sha = run_data.get("head_sha")
        if not commit_sha:
            return _safe_utf8("❌ Не найден SHA коммита")
        
        # 2. Get check-runs for this commit
        checks_url = f"https://api.github.com/repos/{owner}/{repo}/commits/{commit_sha}/check-runs"
        params = {"per_page": 100}
        
        response = requests.get(checks_url, headers=headers, params=params)
        if response.status_code != 200:
            return _safe_utf8(f"❌ Не удалось получить check-runs: {response.status_code}")
        
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
            available = [c.get("name") for c in check_runs[:10]]
            return _safe_utf8(f"❌ Не найден check-run для шага: {step_name}\nДоступные проверки: {', '.join(available)}")
        
        # 4. Return check-run data
        output = found_check.get("output", {})
        lines = [
            f"📋 Данные из Checks API для шага '{step_name}'",
            "=" * 60,
            f"📌 Название: {found_check.get('name')}",
            f"📊 Статус: {found_check.get('status')}",
            f"📊 Результат: {found_check.get('conclusion')}",
            f"🕐 Начало: {found_check.get('started_at')}",
            f"🕐 Завершение: {found_check.get('completed_at')}",
            "",
            f"📝 Заголовок: {output.get('title', 'нет')}",
            "",
            f"📄 Сводка:\n{_safe_utf8(output.get('summary', 'нет'))}",
            "",
        ]
        
        if output.get("text"):
            lines.append(f"📄 Текст:\n{_safe_utf8(output.get('text'))}")
        
        if output.get("annotations"):
            lines.append(f"\n📌 Аннотации ({len(output.get('annotations'))}):")
            for ann in output.get("annotations", [])[:5]:
                lines.append(f"  - {ann.get('message', '')}")
        
        lines.append("")
        lines.append("ℹ️ Примечание: Checks API возвращает обрезанный вывод (до 65535 символов). Для полных логов используйте get_run_logs_by_step.")
        
        return _safe_utf8("\n".join(lines))
    except Exception as e:
        return _safe_utf8(f"❌ Ошибка: {e}")
