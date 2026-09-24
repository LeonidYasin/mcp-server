"""Расширенные инструменты для диагностики сборок: получение полных логов, анализ ошибок."""

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


def _safe_utf8(text: str) -> str:
    """Безопасно преобразует строку в UTF-8."""
    try:
        return text.encode('utf-8', errors='replace').decode('utf-8')
    except Exception:
        return str(text)


def _pick_job(jobs: list, job_name: str = None, prefixes: tuple = ()):
    """Выбирает job: явное имя → точное совпадение → префикс → единственный job.

    Возвращает (job, note) где note — пояснение выбора; либо (None, ошибка-str).
    """
    if not jobs:
        return None, "в этом run нет job'ов (возможно, run ещё не стартовал)"

    names = [j.get('name', '') for j in jobs]

    # 1. Явно заданное имя — по подстроке (регистр не важен)
    if job_name:
        needle = job_name.lower()
        for job in jobs:
            if needle in job.get('name', '').lower():
                return job, None
        return None, (
            f"Job '{job_name}' не найден. Доступны: {', '.join(names)}. "
            f"Передай job_name= один из них."
        )

    # 2. Авто-подбор: ровно один job — берём его
    if len(jobs) == 1:
        return jobs[0], None

    # 3. Авто-подбор по префиксам
    for p in prefixes:
        for job in jobs:
            if job.get('name', '').lower().startswith(p):
                return job, f"Job '{job.get('name')}' matched by prefix '{p}'. Use job_name= to override."
    for p in prefixes:
        for job in jobs:
            if p in job.get('name', '').lower():
                return job, f"Job '{job.get('name')}' matched by prefix '{p}'. Use job_name= to override."

    # 4. Не смогли — подсказка, без падения
    return None, (
        f"Не удалось авто-выбрать job. Доступны: {', '.join(names)}. "
        f"Передай job_name= один из них."
    )


def _build_error_report(kind: str, target_job: dict, logs: str) -> str:
    """Собирает отчёт по логам job'а."""
    lines = logs.split('\n')
    error_lines = []
    for line in lines:
        up = line.upper()
        if 'FAILURE' in up or 'ERROR' in up or 'Exception' in line or 'error:' in line.lower():
            error_lines.append(line.strip())

    result = [
        f"🔍 АНАЛИЗ СБОРКИ {kind}",
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


@mcp_tool(
    name="get_android_build_error",
    description=(
        "Получает детальную ошибку сборки Android APK из логов. "
        "job_name необязателен: если не задан — выбирается единственный job "
        "или первый по префиксам build/android/apk/assemble."
    ),
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "run_id": {"type": "integer", "description": "ID запуска workflow"},
        "job_name": {"type": "string", "description": "Название job (опционально; иначе авто-подбор)"},
    },
    required=["owner", "repo", "run_id"],
)
def get_android_build_error(client: GitHubClient, owner: str, repo: str, run_id: int, job_name: str = None) -> str:
    """Получает детальную ошибку сборки Android."""
    try:
        jobs = client.get_workflow_jobs(owner, repo, run_id)
        target_job, note = _pick_job(
            jobs, job_name, prefixes=("build", "android", "apk", "assemble")
        )
        if target_job is None:
            return _safe_utf8(f"❌ {note}")

        job_id = target_job.get('id')
        if not job_id:
            return "❌ Не удалось получить ID job"

        logs = _safe_utf8(client.get_job_logs(owner, repo, job_id))
        report = _build_error_report("ANDROID", target_job, logs)
        if note:
            report = f"ℹ️ {note}\n{report}"
        return report
    except Exception as e:
        return _safe_utf8(f"❌ Ошибка: {e}")


@mcp_tool(
    name="get_ios_build_error",
    description=(
        "Получает детальную ошибку сборки iOS из логов. "
        "job_name необязателен: если не задан — выбирается единственный job "
        "или первый по префиксам build/ios/xcode/archive."
    ),
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "run_id": {"type": "integer", "description": "ID запуска workflow"},
        "job_name": {"type": "string", "description": "Название job (опционально; иначе авто-подбор)"},
    },
    required=["owner", "repo", "run_id"],
)
def get_ios_build_error(client: GitHubClient, owner: str, repo: str, run_id: int, job_name: str = None) -> str:
    """Получает детальную ошибку сборки iOS."""
    try:
        jobs = client.get_workflow_jobs(owner, repo, run_id)
        target_job, note = _pick_job(
            jobs, job_name, prefixes=("build", "ios", "xcode", "archive")
        )
        if target_job is None:
            return _safe_utf8(f"❌ {note}")

        job_id = target_job.get('id')
        if not job_id:
            return "❌ Не удалось получить ID job"

        logs = _safe_utf8(client.get_job_logs(owner, repo, job_id))
        report = _build_error_report("iOS", target_job, logs)
        if note:
            report = f"ℹ️ {note}\n{report}"
        return report
    except Exception as e:
        return _safe_utf8(f"❌ Ошибка: {e}")
