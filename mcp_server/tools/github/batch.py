"""MCP tools: batch push and file move in a single commit."""

import base64

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


@mcp_tool(
    name="push_multiple_files",
    description="Пушит несколько файлов одним коммитом (без промежуточных коммитов)",
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
    owner, repo, branch = kwargs["owner"], kwargs["repo"], kwargs["branch"]
    files = kwargs["files"]
    if isinstance(files, str):
        import json as _json
        files = _json.loads(files)
    if not files:
        return "❌ Список файлов пуст"

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

    # 4. Новое дерево
    new_tree = client._request(
        "POST",
        f"/repos/{owner}/{repo}/git/trees",
        json={"base_tree": base_tree_sha, "tree": tree_items},
    ).json()

    # 5. Коммит
    new_commit = client._request(
        "POST",
        f"/repos/{owner}/{repo}/git/commits",
        json={"message": kwargs["message"], "tree": new_tree["sha"], "parents": [base_sha]},
    ).json()

    # 6. Сдвиг ветки
    client._request(
        "PATCH",
        f"/repos/{owner}/{repo}/git/refs/heads/{branch}",
        json={"sha": new_commit["sha"], "force": False},
    )

    return (
        f"✅ {len(files)} файлов закоммичено одним коммитом {new_commit['sha'][:8]} "
        f"в {owner}/{repo}@{branch}"
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
