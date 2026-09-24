"""MCP tool: update_repo_info — обновляет About-поля репозитория.

Позволяет менять:
- description (короткое описание, поле About)
- homepage    (поле Website — например GitHub Pages)
- topics      (список тем)

GitHub API требует два разных вызова:
- PATCH /repos/{owner}/{repo}          — description, homepage
- PUT   /repos/{owner}/{repo}/topics   — topics (с preview Accept)
"""

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


@mcp_tool(
    name="update_repo_info",
    description=(
        "Обновляет описание (About), сайт (Website) и topics репозитория. "
        "Передавай только те поля, которые нужно изменить."
    ),
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "description": {
            "type": "string",
            "description": "Короткое описание репозитория (поле About). Пустая строка очищает.",
        },
        "homepage": {
            "type": "string",
            "description": "URL сайта (поле Website), напр. https://leonidyasin.github.io/mcp-server/",
        },
        "topics": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Список topics (строчные, без пробелов — через дефис)",
        },
    },
    required=["owner", "repo"],
)
def update_repo_info(client: GitHubClient, owner: str, repo: str, **kwargs) -> str:
    changed = []
    errors = []

    patch_body = {}
    if "description" in kwargs and kwargs["description"] is not None:
        patch_body["description"] = kwargs["description"]
    if "homepage" in kwargs and kwargs["homepage"] is not None:
        patch_body["homepage"] = kwargs["homepage"]

    if patch_body:
        try:
            client._request("PATCH", f"/repos/{owner}/{repo}", json=patch_body)
            changed.extend(patch_body.keys())
        except Exception as e:  # noqa: BLE001
            errors.append(f"PATCH: {e}")

    topics = kwargs.get("topics")
    if topics is not None:
        try:
            # GitHub topics API uses a preview media type.
            client._request(
                "PUT",
                f"/repos/{owner}/{repo}/topics",
                json={"names": list(topics)},
                headers={"Accept": "application/vnd.github.mercy-preview+json"},
            )
            changed.append("topics")
        except Exception as e:  # noqa: BLE001
            errors.append(f"topics: {e}")

    if not changed and not errors:
        return "⚠️ Не передано ни одного поля для изменения (description/homepage/topics)"

    lines = []
    if changed:
        lines.append(f"✅ Обновлено: {', '.join(changed)}")
    if errors:
        lines.append("❌ Ошибки: " + "; ".join(errors))
    return "\n".join(lines)
