"""MCP tools: управление репозиториями (создание, список, апдейт)."""

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


_SCOPE_HINT = (
    "Похоже, у токена не хватает прав. Для создания/изменения репозиториев "
    "нужен scope 'repo' (или 'public_repo' — только для публичных). "
    "Проверь токен: https://github.com/settings/tokens"
)


def _raise_friendly(exc: Exception) -> None:
    """Превращает сырой 403 от GitHub в понятную ошибку про scope."""
    msg = str(exc)
    if "HTTP error 403" in msg:
        raise PermissionError(f"{_SCOPE_HINT}\n\nОригинал: {msg}") from exc
    raise exc


@mcp_tool(
    name="create_repo",
    description=(
        "Создаёт репозиторий на GitHub. Если задан org — в организации "
        "(POST /orgs/{org}/repos), иначе в личном аккаунте (POST /user/repos). "
        "auto_init=true (по умолчанию) — GitHub сразу создаёт первый коммит "
        "с README, ветка default_branch появляется сразу. auto_init=false — "
        "репозиторий пустой, для первых файлов используй push_multiple_files "
        "(он умеет работать с пустым репо)."
    ),
    parameters={
        "name": {"type": "string", "description": "Имя репозитория"},
        "description": {"type": "string", "description": "Описание (About)"},
        "private": {"type": "boolean", "description": "Приватный (по умолчанию false)"},
        "auto_init": {
            "type": "boolean",
            "description": "Инициализировать README (по умолчанию true)",
        },
        "gitignore_template": {
            "type": "string",
            "description": "Шаблон .gitignore (напр. 'Python', 'Node')",
        },
        "license_template": {
            "type": "string",
            "description": "Шаблон лицензии (напр. 'mit', 'apache-2.0')",
        },
        "org": {
            "type": "string",
            "description": "Организация (если создаём не в личном аккаунте)",
        },
    },
    required=["name"],
)
def create_repo(client: GitHubClient, **kwargs) -> str:
    """Создаёт репозиторий и возвращает ключевые поля.

    Возвращает: full_name, html_url, default_branch, clone_url.

    :param name: имя репозитория
    :param description: описание (About)
    :param private: приватный (default false)
    :param auto_init: создать README и первый коммит (default true).
        Если false — репо пустое; для первых файлов используй
        push_multiple_files (работает на пустом репо).
    :param gitignore_template: шаблон .gitignore
    :param license_template: шаблон лицензии
    :param org: организация; если не задана — личный аккаунт
    """
    name = kwargs["name"]
    org = kwargs.get("org")

    payload = {
        "name": name,
        "private": bool(kwargs.get("private", False)),
        "auto_init": bool(kwargs.get("auto_init", True)),
    }
    if kwargs.get("description"):
        payload["description"] = kwargs["description"]
    if kwargs.get("gitignore_template"):
        payload["gitignore_template"] = kwargs["gitignore_template"]
    if kwargs.get("license_template"):
        payload["license_template"] = kwargs["license_template"]

    url = f"/orgs/{org}/repos" if org else "/user/repos"
    try:
        resp = client._request("POST", url, json=payload).json()
    except Exception as e:
        _raise_friendly(e)

    return (
        f"✅ Репозиторий создан: {resp.get('full_name')}\n"
        f"   URL: {resp.get('html_url')}\n"
        f"   default_branch: {resp.get('default_branch')}\n"
        f"   clone: {resp.get('clone_url')}\n"
        f"   private: {resp.get('private')}"
    )


@mcp_tool(
    name="list_my_repos",
    description=(
        "Список репозиториев текущего пользователя (GET /user/repos). "
        "type: all|owner|member (по умолчанию all), sort: created|updated|pushed|full_name "
        "(по умолчанию updated)."
    ),
    parameters={
        "type": {
            "type": "string",
            "description": "all|owner|member (по умолчанию all)",
        },
        "sort": {
            "type": "string",
            "description": "created|updated|pushed|full_name (по умолчанию updated)",
        },
        "limit": {"type": "integer", "description": "Сколько вернуть (по умолчанию 30)"},
        "page": {"type": "integer", "description": "Страница (по умолчанию 1)"},
    },
    required=[],
)
def list_my_repos(client: GitHubClient, **kwargs) -> str:
    """Список репозиториев пользователя.

    Возвращает по каждому: full_name, private, updated_at.

    :param type: all|owner|member (default all)
    :param sort: created|updated|pushed|full_name (default updated)
    :param limit: сколько вернуть (default 30)
    :param page: страница (default 1)
    """
    params = {
        "type": kwargs.get("type") or "all",
        "sort": kwargs.get("sort") or "updated",
        "per_page": int(kwargs.get("limit") or 30),
        "page": int(kwargs.get("page") or 1),
    }
    try:
        repos = client._request("GET", "/user/repos", params=params).json()
    except Exception as e:
        _raise_friendly(e)

    if not repos:
        return "Репозиториев не найдено."

    lines = [f"Репозитории ({len(repos)}):"]
    for r in repos:
        lines.append(
            f"  {'🔒' if r.get('private') else '📦'} {r.get('full_name')} "
            f"— updated {r.get('updated_at')}"
        )
    return "\n".join(lines)


@mcp_tool(
    name="update_repo",
    description=(
        "PATCH /repos/{owner}/{repo}: меняет ТОЛЬКО переданные поля "
        "(description, homepage, private, archived, default_branch). "
        "Для topics/website см. update_repo_info."
    ),
    parameters={
        "owner": {"type": "string", "description": "Владелец"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "description": {"type": "string", "description": "Новое описание"},
        "homepage": {"type": "string", "description": "Новый сайт"},
        "private": {"type": "boolean", "description": "Приватность"},
        "archived": {"type": "boolean", "description": "Архивировать/разархивировать"},
        "default_branch": {"type": "string", "description": "Дефолтная ветка"},
    },
    required=["owner", "repo"],
)
def update_repo(client: GitHubClient, **kwargs) -> str:
    """Обновляет поля репозитория, меняет только переданные.

    :param owner: владелец
    :param repo: имя репозитория
    :param description: новое описание
    :param homepage: новый сайт
    :param private: приватность
    :param archived: архивировать/разархивировать
    :param default_branch: дефолтная ветка
    """
    owner, repo = kwargs["owner"], kwargs["repo"]

    payload = {}
    for field in ("description", "homepage", "private", "archived", "default_branch"):
        if field in kwargs and kwargs[field] is not None:
            payload[field] = kwargs[field]

    if not payload:
        return "❌ Не передано ни одного поля для изменения."

    try:
        resp = client._request(
            "PATCH", f"/repos/{owner}/{repo}", json=payload
        ).json()
    except Exception as e:
        _raise_friendly(e)

    changed = ", ".join(payload.keys())
    return (
        f"✅ {resp.get('full_name')}: обновлено ({changed})\n"
        f"   URL: {resp.get('html_url')}"
    )
