"""MCP tools: batch push and file move in a single commit."""

import base64

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


def _is_empty_repo_error(exc: Exception) -> bool:
    """True, если исключение от _request означает отсутствие базовой ветки.

    GitHub отдаёт 409 (Git Repository is empty) для репозитория без коммитов
    и 404 для отсутствующей ветки. Оба случая — bootstrap нового репозитория.
    """
    msg = str(exc)
    return "HTTP error 409" in msg or "HTTP error 404" in msg


@mcp_tool(
    name="push_multiple_files",
    description=(
        "Пушит несколько файлов одним коммитом (без промежуточных коммитов). "
        "Работает и на пустом репозитории (без коммитов): в этом случае "
        "создаёт первую ветку и первый коммит из переданных файлов."
    ),
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "branch": {"type": "string", "description": "Ветка"},
        "message": {"type": "string", "description": "Коммит-сообщение"},
        "files": {
            "type": "array",
            "description": "Массив объектов {path, content}",
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    required=["owner", "repo", "branch", "message", "files"],
)
def push_multiple_files(client: GitHubClient, **kwargs) -> str:
    """Один коммит на все файлы. Работает и на пустом репозитории.

    На непустом репозитории используется Git Trees API поверх текущего
    HEAD ветки (base_tree + parents), ветка сдвигается через PATCH.

    На пустом репозитории (нет коммитов, GET ref → 409/404) выполняется
    bootstrap: дерево строится без base_tree, коммит без parents,
    ветка создаётся через POST /git/refs.

    :param owner: владелец репозитория
    :param repo: имя репозитория
    :param branch: ветка (на пустом репо будет создана)
    :param message: коммит-сообщение
    :param files: список {path, content}
    """
    owner, repo, branch = kwargs["owner"], kwargs["repo"], kwargs["branch"]
    files = kwargs["files"]
    if isinstance(files, str):
        import json as _json
        files = _json.loads(files)
    if not files:
        return "❌ Список файлов пуст"

    # 1. Пробуем получить текущий HEAD ветки.
    #    На пустом репозитории GET ref отдаёт 409 (Git Repository is empty),
    #    на отсутствующей ветке — 404. Оба случая означают: базовой ветки нет,
    #    это bootstrap нового репозитория.
    base_sha = None
    base_tree_sha = None
    try:
        ref = client._request(
            "GET", f"/repos/{owner}/{repo}/git/ref/heads/{branch}"
        ).json()
        base_sha = ref["object"]["sha"]

        # 2. Базовое дерево
        commit = client._request(
            "GET", f"/repos/{owner}/{repo}/git/commits/{base_sha}"
        ).json()
        base_tree_sha = commit["tree"]["sha"]
    except Exception as e:
        if not _is_empty_repo_error(e):
            # Настоящая ошибка (сеть, права, 5xx) — не глотаем
            raise
        base_sha = None
        base_tree_sha = None

    # 3. Blobs
    tree_items = []
    for f in files:
        blob = client._request(
            "POST",
            f"/repos/{owner}/{repo}/git/blobs",
            json={
                "content": base64.b64encode(f["content"].encode("utf-8")).decode("ascii"),
                "encoding": "base64",
            },
        ).json()
        tree_items.append(
            {"path": f["path"], "mode": "100644", "type": "blob", "sha": blob["sha"]}
        )

    # 4. Новое дерево: base_tree только если есть от чего отталкиваться
    tree_payload = {"tree": tree_items}
    if base_tree_sha:
        tree_payload["base_tree"] = base_tree_sha
    new_tree = client._request(
        "POST",
        f"/repos/{owner}/{repo}/git/trees",
        json=tree_payload,
    ).json()

    # 5. Коммит: parents только для непустого репо
    commit_payload = {"message": kwargs["message"], "tree": new_tree["sha"]}
    if base_sha:
        commit_payload["parents"] = [base_sha]
    new_commit = client._request(
        "POST",
        f"/repos/{owner}/{repo}/git/commits",
        json=commit_payload,
    ).json()

    # 6. Ветка: создать (пустой репо) или сдвинуть (непустой)
    if base_sha:
        client._request(
            "PATCH",
            f"/repos/{owner}/{repo}/git/refs/heads/{branch}",
            json={"sha": new_commit["sha"], "force": False},
        )
        mode = ""
    else:
        client._request(
            "POST",
            f"/repos/{owner}/{repo}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": new_commit["sha"]},
        )
        mode = " (bootstrap пустого репо)"

    return (
        f"✅ {len(files)} файлов закоммичено одним коммитом {new_commit['sha'][:8]} "
        f"в {owner}/{repo}@{branch}{mode}"
    )


@mcp_tool(
    name="move_file",
    description=(
        "Перемещает или переименовывает файл ОДНИМ коммитом (Git Trees API). "
        "Заменяет связку create_or_update_file + delete_file. "
        "from_path — текущий путь, to_path — новый (включая новое имя)."
    ),
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "from_path": {"type": "string", "description": "Текущий путь файла"},
        "to_path": {"type": "string", "description": "Новый путь (включая имя файла)"},
        "message": {"type": "string", "description": "Коммит-сообщение"},
        "branch": {"type": "string", "description": "Ветка (по умолчанию main)"},
    },
    required=["owner", "repo", "from_path", "to_path", "message"],
)
def move_file(client: GitHubClient, **kwargs) -> str:
    owner, repo = kwargs["owner"], kwargs["repo"]
    from_path, to_path = kwargs["from_path"], kwargs["to_path"]
    branch = kwargs.get("branch") or "main"

    if from_path == to_path:
        return "❌ from_path и to_path совпадают — нечего перемещать."

    try:
        # 1. Текущий HEAD ветки
        ref = client._request(
            "GET", f"/repos/{owner}/{repo}/git/ref/heads/{branch}"
        ).json()
        base_sha = ref["object"]["sha"]

        # 2. Базовое дерево
        commit = client._request(
            "GET", f"/repos/{owner}/{repo}/git/commits/{base_sha}"
        ).json()
        base_tree_sha = commit["tree"]["sha"]

        # 3. Читаем содержимое исходного файла (содержимое + режим)
        src = client._request(
            "GET",
            f"/repos/{owner}/{repo}/contents/{from_path}",
            params={"ref": branch},
        ).json()
        if isinstance(src, list):
            return f"❌ '{from_path}' — директория, move_file работает только с файлами."
        src_content_b64 = src.get("content", "")
        src_sha = src.get("sha")

        # 4. Новый blob с тем же содержимым
        blob = client._request(
            "POST",
            f"/repos/{owner}/{repo}/git/blobs",
            json={"content": src_content_b64, "encoding": "base64"},
        ).json()

        # 5. Новое дерево: добавляем to_path, удаляем from_path (sha: None)
        tree_items = [
            {"path": to_path, "mode": "100644", "type": "blob", "sha": blob["sha"]},
            {"path": from_path, "mode": "100644", "type": "blob", "sha": None},
        ]
        new_tree = client._request(
            "POST",
            f"/repos/{owner}/{repo}/git/trees",
            json={"base_tree": base_tree_sha, "tree": tree_items},
        ).json()

        # 6. Коммит
        new_commit = client._request(
            "POST",
            f"/repos/{owner}/{repo}/git/commits",
            json={"message": kwargs["message"], "tree": new_tree["sha"], "parents": [base_sha]},
        ).json()

        # 7. Сдвиг ветки
        client._request(
            "PATCH",
            f"/repos/{owner}/{repo}/git/refs/heads/{branch}",
            json={"sha": new_commit["sha"], "force": False},
        )

        return (
            f"✅ Перемещено: {from_path} → {to_path}\n"
            f"   Коммит {new_commit['sha'][:8]} в {owner}/{repo}@{branch}"
        )
    except Exception as e:
        return f"❌ Ошибка move_file: {e}"
