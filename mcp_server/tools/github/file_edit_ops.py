"""GitHub file edit tools: replace_in_file — точечная замена строки внутри файла.

Зачем: create_or_update_file перезаписывает файл ЦЕЛИКОМ (нужно прислать весь контент).
Для правки одной строки это дорого по токенам и опасно (легко потерять код).
replace_in_file читает файл, проверяет уникальность подстроки, заменяет и пишет обратно
(через client.create_or_update_file с уже полученным SHA).
"""

from __future__ import annotations

import base64

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


def _validate_inputs(owner, repo, path) -> str | None:
    if not owner or not str(owner).strip():
        return "❌ Не указан owner."
    if not repo or not str(repo).strip():
        return "❌ Не указан repo."
    if not path or not str(path).strip():
        return "❌ Не указан path."
    return None


@mcp_tool(
    name="replace_in_file",
    description=(
        "Точечная замена подстроки внутри текстового файла репозитория. "
        "Не требует присылать файл целиком (в отличие от create_or_update_file). "
        "old_string должен встречаться в файле ровно count_expected раз (по умолчанию 1); "
        "иначе операция отклоняется с числом вхождений — чтобы не испортить файл. "
        "Файл читается по ref (по умолчанию — ветка branch), замена пишется в branch."
    ),
    parameters={
        "owner": {"type": "string", "description": "Владелец репозитория"},
        "repo": {"type": "string", "description": "Имя репозитория"},
        "path": {"type": "string", "description": "Путь к файлу"},
        "old_string": {"type": "string", "description": "Подстрока, которую заменяем (должна быть уникальна)"},
        "new_string": {"type": "string", "description": "На что заменяем"},
        "message": {"type": "string", "description": "Коммит-сообщение"},
        "branch": {"type": "string", "description": "Ветка, куда писать (и откуда читать, если ref не задан)"},
        "ref": {"type": "string", "description": "Откуда читать (по умолчанию = branch)"},
        "count_expected": {"type": "integer", "description": "Ожидаемое число вхождений old_string (по умолчанию 1)"},
    },
    required=["owner", "repo", "path", "old_string", "new_string", "message", "branch"],
)
def replace_in_file(
    client: GitHubClient,
    owner: str, repo: str, path: str,
    old_string: str, new_string: str,
    message: str, branch: str,
    ref: str | None = None,
    count_expected: int = 1,
) -> str:
    """Surgical replace of old_string with new_string inside a file."""
    err = _validate_inputs(owner, repo, path)
    if err:
        return err
    if not branch or not str(branch).strip():
        return "❌ Не указана branch."
    if old_string == "":
        return "❌ old_string пуст."

    read_ref = ref or branch

    # 1. Read the file (content + current blob sha)
    try:
        data = client.get_file(owner, repo, path, read_ref)
    except Exception as e:
        return f"❌ Не удалось прочитать {path}: {e}"

    if isinstance(data, list):
        return f"❌ '{path}' — директория, replace_in_file не применим."
    if "content" not in data:
        return f"❌ Неожиданный ответ GitHub API для {path}."

    try:
        current = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    except Exception as e:
        return f"❌ Не удалось декодировать {path} как UTF-8: {e}"

    blob_sha = data.get("sha")

    # 2. Check occurrences
    found = current.count(old_string)
    expected = count_expected if isinstance(count_expected, int) and count_expected > 0 else 1
    if found == 0:
        return f"❌ old_string не найден в {path} (0 вхождений). Файл не изменён."
    if found != expected:
        return (
            f"❌ old_string встречается {found} раз(а), ожидалось {expected}. "
            f"Файл не изменён — уточни old_string или задай count_expected={found}."
        )

    # 3. Replace + write back
    updated = current.replace(old_string, new_string)
    try:
        client.create_or_update_file(
            owner, repo, path, updated, message, branch, blob_sha
        )
    except Exception as e:
        return f"❌ Ошибка записи {path}: {e}"

    return (
        f"✅ {path}: заменено вхождений {found} → новый размер "
        f"{len(updated.encode('utf-8'))} байт (ветка {branch})"
    )
