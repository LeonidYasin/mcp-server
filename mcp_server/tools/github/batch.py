"""MCP tool: batch push of multiple files in a single commit."""

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
