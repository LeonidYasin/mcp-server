"""Расширенные инструменты для диагностики сборок: получение полных логов, анализ ошибок."""

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


def _safe_utf8(text: str) -> str:
    """Безопасно преобразует строку в UTF-8."""
    try:
        return text.encode('utf-8', errors='replace').decode('utf-8')
    except Exception:
        return str(text)


@mcp_tool(
    name="get_android_build_error",
    description="Получает детальную ошибку сборки Android APK из логов",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "run_id": {"type": "integer", "description": "ID запуска workflow"},
        "job_name": {"type": "string", "description": "Название job (например build-android)"},
    },
    required=["owner", "repo", "run_id"],
)
def get_android_build_error(client: GitHubClient, owner: str, repo: str, run_id: int, job_name: str = "build-android") -> str:
    """Получает детальную ошибку сборки Android."""
    try:
        jobs = client.get_workflow_jobs(owner, repo, run_id)
        
        target_job = None
        for job in jobs:
            if job_name in job.get('name', '').lower():
                target_job = job
                break
        
        if not target_job:
            available = [j.get('name', 'unknown') for j in jobs]
            return _safe_utf8(f"❌ Job '{job_name}' не найден. Доступны: {', '.join(available)}")
        
        job_id = target_job.get('id')
        if not job_id:
            return "❌ Не удалось получить ID job"
        
        logs = client.get_job_logs(owner, repo, job_id)
        lines = logs.split('\n')
        
        error_lines = []
        for line in lines:
            if 'FAILURE' in line.upper() or 'ERROR' in line.upper() or 'Exception' in line:
                error_lines.append(line.strip())
        
        result = [
            f"🔍 АНАЛИЗ СБОРКИ ANDROID",
            f"📦 Job: {target_job.get('name')}",
            f"📊 Статус: {target_job.get('status')}",
            f"📈 Результат: {target_job.get('conclusion')}",
            f"📋 Всего строк логов: {len(lines)}",
            ""
        ]
        
        if error_lines:
            result.append(f"❌ НАЙДЕНО ОШИБОК: {len(error_lines)}")
            result.append("\n🔴 КЛЮЧЕВЫЕ ОШИБКИ:")
            for err in error_lines[:10]:
                result.append(f"  • {_safe_utf8(err)}")
        else:
            result.append("✅ Явных ошибок в логах не найдено")
            result.append("\n📋 ПОСЛЕДНИЕ 20 СТРОК ЛОГОВ:")
            for line in lines[-20:]:
                result.append(f"  {_safe_utf8(line)}")
        
        return _safe_utf8('\n'.join(result))
        
    except Exception as e:
        return _safe_utf8(f"❌ Ошибка: {e}")


@mcp_tool(
    name="get_ios_build_error",
    description="Получает детальную ошибку сборки iOS из логов",
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "run_id": {"type": "integer", "description": "ID запуска workflow"},
        "job_name": {"type": "string", "description": "Название job (например build-ios)"},
    },
    required=["owner", "repo", "run_id"],
)
def get_ios_build_error(client: GitHubClient, owner: str, repo: str, run_id: int, job_name: str = "build-ios") -> str:
    """Получает детальную ошибку сборки iOS."""
    try:
        jobs = client.get_workflow_jobs(owner, repo, run_id)
        
        target_job = None
        for job in jobs:
            if job_name in job.get('name', '').lower():
                target_job = job
                break
        
        if not target_job:
            available = [j.get('name', 'unknown') for j in jobs]
            return _safe_utf8(f"❌ Job '{job_name}' не найден. Доступны: {', '.join(available)}")
        
        job_id = target_job.get('id')
        if not job_id:
            return "❌ Не удалось получить ID job"
        
        logs = client.get_job_logs(owner, repo, job_id)
        lines = logs.split('\n')
        
        error_lines = []
        for line in lines:
            if 'FAILURE' in line.upper() or 'ERROR' in line.upper() or 'Exception' in line or 'error:' in line.lower():
                error_lines.append(line.strip())
        
        result = [
            f"🔍 АНАЛИЗ СБОРКИ iOS",
            f"📦 Job: {target_job.get('name')}",
            f"📊 Статус: {target_job.get('status')}",
            f"📈 Результат: {target_job.get('conclusion')}",
            f"📋 Всего строк логов: {len(lines)}",
            ""
        ]
        
        if error_lines:
            result.append(f"❌ НАЙДЕНО ОШИБОК: {len(error_lines)}")
            result.append("\n🔴 КЛЮЧЕВЫЕ ОШИБКИ:")
            for err in error_lines[:10]:
                result.append(f"  • {_safe_utf8(err)}")
        else:
            result.append("✅ Явных ошибок в логах не найдено")
            result.append("\n📋 ПОСЛЕДНИЕ 20 СТРОК ЛОГОВ:")
            for line in lines[-20:]:
                result.append(f"  {_safe_utf8(line)}")
        
        return _safe_utf8('\n'.join(result))
        
    except Exception as e:
        return _safe_utf8(f"❌ Ошибка: {e}")
