"""MCP tools: batch push and file move in a single commit."""

import base64
import json
import re
from urllib.parse import quote

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


_FILE_MODES = {"100644", "100755", "120000"}


def _is_empty_repo_error(exc: Exception) -> bool:
    # 404 can mask permissions or a missing branch, not an empty repository.
    message = str(exc)
    return "HTTP error 409" in message and "git repository is empty" in message.lower()


def _prepare_batch_files(files):
    if isinstance(files, str):
        files = json.loads(files)  # Preserve legacy raw-HTTP JSON-string callers.
    if not isinstance(files, list):
        raise ValueError("files must be an array of objects")
    seen = set()
    for file in files:
        if not isinstance(file, dict):
            raise ValueError("files entries must be objects")
        path = file.get("path")
        if (not isinstance(path, str) or not path or "\\" in path or "\x00" in path
                or any(part in ("", ".", "..") for part in path.split("/"))):
            raise ValueError("path must be a normalized relative POSIX file path")
        if path in seen:
            raise ValueError("duplicate path in files")
        seen.add(path)
        if not isinstance(file.get("content"), str):
            raise ValueError("content must be a UTF-8 string")
        if "mode" in file and (not isinstance(file["mode"], str) or file["mode"] not in _FILE_MODES):
            raise ValueError("mode must be 100644, 100755 or 120000")
    for path in seen:
        parts = path.split("/")
        if any("/".join(parts[:i]) in seen for i in range(1, len(parts))):
            raise ValueError("conflicting file/directory path in files")
    return files


def _batch_result(outcome, owner, repo, branch, *, expected=None, base=None,
                  observed=None, candidate=None, file_count=0, detail=""):
    info = {"outcome": outcome, "expected_head_sha": expected,
            "base_head_sha": base, "observed_head_sha": observed,
            "new_commit_sha": candidate, "file_count": file_count}
    if outcome == "applied":
        text = (f"✅ {file_count} файлов закоммичено одним коммитом {candidate[:8]} "
                f"в {owner}/{repo}@{branch}")
        if base is None:
            text += " (bootstrap пустого репо)"
    elif outcome == "conflict":
        text = "❌ Конфликт HEAD: обновление ветки отклонено. " + detail
    else:
        text = ("❌ Обновление ветки не подтверждено. Проверь ref перед повтором; "
                "автоматически не повторять запись. " + detail)
    return text + "\nmetadata: " + json.dumps(info, ensure_ascii=False, sort_keys=True)


@mcp_tool(
    name="push_multiple_files",
    description=(
        "Пушит несколько файлов одним коммитом, сохраняя existing executable/symlink modes. "
        "Новые файлы: 100644; mode можно задать явно. expected_head_sha отклоняет stale HEAD. "
        "Полнота базового tree обязательна; force push не используется. "
        "Поддерживает bootstrap подтверждённого пустого репозитория (409)."
    ),
    parameters={
        "owner": {"type": "string"}, "repo": {"type": "string"},
        "branch": {"type": "string", "description": "Ветка"},
        "message": {"type": "string", "description": "Коммит-сообщение"},
        "expected_head_sha": {"type": "string", "pattern": "^[0-9a-fA-F]{40}$",
                              "description": "Ожидаемый полный HEAD SHA; mismatch — конфликт до записи"},
        "files": {
            "type": "array", "description": "Массив {path, content, mode?}; mode сохраняется по умолчанию",
            "items": {"type": "object", "properties": {
                "path": {"type": "string"}, "content": {"type": "string"},
                "mode": {"type": "string", "enum": ["100644", "100755", "120000"]},
            }, "required": ["path", "content"]},
        },
    },
    required=["owner", "repo", "branch", "message", "files"],
)
def push_multiple_files(client: GitHubClient, **kwargs) -> str:
    files = _prepare_batch_files(kwargs["files"])
    if not files:
        return "❌ Список файлов пуст"
    expected = None
    if "expected_head_sha" in kwargs:
        value = kwargs["expected_head_sha"]
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", value):
            raise ValueError("expected_head_sha must be a full 40-character hexadecimal SHA")
        expected = value.lower()
    owner, repo, branch = kwargs["owner"], kwargs["repo"], kwargs["branch"]
    prefix = f"/repos/{owner}/{repo}/git"
    ref_read = f"{prefix}/ref/heads/{quote(branch, safe='')}"
    base_sha = base_tree_sha = None
    try:
        base_sha = client._request("GET", ref_read).json()["object"]["sha"]
        if not isinstance(base_sha, str) or not base_sha:
            raise ValueError("GitHub did not return a valid HEAD SHA")
    except Exception as error:
        if not _is_empty_repo_error(error):
            raise
    if expected is not None and expected != base_sha:
        return _batch_result("conflict", owner, repo, branch, expected=expected,
                             base=base_sha, observed=base_sha, file_count=len(files),
                             detail="expected_head_sha не совпадает с текущим HEAD; записи не выполнялись.")

    existing = {}
    if base_sha is not None:
        # Commit/tree errors must not be swallowed as empty-repo bootstrap.
        commit = client._request("GET", f"{prefix}/commits/{base_sha}").json()
        base_tree_sha = commit["tree"]["sha"]
        if not isinstance(base_tree_sha, str) or not base_tree_sha:
            raise ValueError("GitHub did not return a valid base tree SHA")
        tree = client._request("GET", f"{prefix}/trees/{base_tree_sha}",
                               params={"recursive": "1"}).json()
        if tree.get("truncated") is not False or not isinstance(tree.get("tree"), list):
            raise ValueError("base tree completeness not confirmed; modes cannot be inferred safely")
        for entry in tree["tree"]:
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                raise ValueError("invalid base tree entry")
            if entry["path"] in existing:
                raise ValueError("duplicate path in base tree")
            existing[entry["path"]] = entry

    modes = []
    for file in files:
        parts = file["path"].split("/")
        for i in range(1, len(parts)):
            ancestor = existing.get("/".join(parts[:i]))
            if ancestor and ancestor.get("type") != "tree":
                raise ValueError("path has a non-directory ancestor; implicit conversion refused")
        entry = existing.get(file["path"])
        if entry and (entry.get("type") != "blob" or not isinstance(entry.get("mode"), str)
                      or entry["mode"] not in _FILE_MODES):
            raise ValueError("existing entry type/mode unsupported; implicit conversion refused")
        modes.append(file.get("mode", entry["mode"] if entry else "100644"))

    tree_items = []
    for file, mode in zip(files, modes):
        blob = client._request("POST", f"{prefix}/blobs", json={
            "content": base64.b64encode(file["content"].encode("utf-8")).decode("ascii"),
            "encoding": "base64",
        }).json()
        tree_items.append({"path": file["path"], "mode": mode, "type": "blob", "sha": blob["sha"]})
    tree_payload = {"tree": tree_items}
    if base_tree_sha is not None:
        tree_payload["base_tree"] = base_tree_sha
    new_tree = client._request("POST", f"{prefix}/trees", json=tree_payload).json()
    commit_payload = {"message": kwargs["message"], "tree": new_tree["sha"]}
    if base_sha is not None:
        commit_payload["parents"] = [base_sha]
    new_sha = client._request("POST", f"{prefix}/commits", json=commit_payload).json()["sha"]

    if base_sha is not None:
        observed = client._request("GET", ref_read).json()["object"]["sha"]
        if observed != base_sha:
            return _batch_result("conflict", owner, repo, branch, expected=expected,
                                 base=base_sha, observed=observed, candidate=new_sha,
                                 file_count=len(files), detail="HEAD изменился во время подготовки; PATCH не выполнялся.")
        method, endpoint = "PATCH", f"{prefix}/refs/heads/{quote(branch, safe='')}"
        payload = {"sha": new_sha, "force": False}
    else:
        method, endpoint = "POST", f"{prefix}/refs"
        payload = {"ref": f"refs/heads/{branch}", "sha": new_sha}
    try:
        updated = client._request(method, endpoint, json=payload).json()
    except Exception as error:
        message = str(error)
        rejected = ("HTTP error 409" in message or (
            "HTTP error 422" in message and any(reason in message.lower() for reason in
            ("fast forward", "reference already exists"))))
        return _batch_result("conflict" if rejected else "unconfirmed", owner, repo, branch,
                             expected=expected, base=base_sha, candidate=new_sha,
                             file_count=len(files), detail=message)
    if (updated.get("object") or {}).get("sha") != new_sha:
        return _batch_result("unconfirmed", owner, repo, branch, expected=expected,
                             base=base_sha, candidate=new_sha, file_count=len(files),
                             detail="GitHub ref response не подтвердил SHA нового коммита.")
    return _batch_result("applied", owner, repo, branch, expected=expected,
                         base=base_sha, observed=new_sha, candidate=new_sha, file_count=len(files))


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
