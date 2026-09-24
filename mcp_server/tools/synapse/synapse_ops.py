"""MCP tools: Synapse — people findability layer (batch 7a, no embeddings).

Design (see memories / project vision):
- Portable JSON profile. Publishing is explicit; contact is revealed only by
  mutual consent (propose_contact creates a request, never auto-reveals).
- search_people / search_notes are keyword-scored MVP. Batch 7b replaces the
  scoring with real embeddings (model_me / find_my_match).

Storage layout under SYNAPSE_DATA_DIR (default ~/workspace/synapse):
  profiles/<profile_id>.json
  notes/<note_id>.json
  requests/<request_id>.json
"""

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from mcp_server.core.registry import mcp_tool

_TOKEN_RE = re.compile(r"[\w\-]+", re.UNICODE)


def _data_dir() -> Path:
    raw = os.environ.get("SYNAPSE_DATA_DIR") or str(Path.home() / "workspace" / "synapse")
    root = Path(raw).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    (root / "profiles").mkdir(exist_ok=True)
    (root / "notes").mkdir(exist_ok=True)
    (root / "requests").mkdir(exist_ok=True)
    return root


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_id(value: str) -> str:
    """Only allow simple ids (no path traversal)."""
    if not re.fullmatch(r"[A-Za-z0-9_.\-]{1,80}", value or ""):
        raise ValueError("id must match [A-Za-z0-9_.-]{1,80}")
    return value


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text or "") if len(t) > 1}


def _score(query_tokens: set[str], haystack: str) -> float:
    """Tiny keyword overlap score in [0, 1]. MVP until embeddings (7b)."""
    if not query_tokens:
        return 0.0
    hay = _tokens(haystack)
    if not hay:
        return 0.0
    return len(query_tokens & hay) / len(query_tokens)


@mcp_tool(
    name="publish_profile",
    description=(
        "Публикует переносимый JSON-профиль в локальное хранилище Synapse. "
        "profile — произвольный JSON (name, skills, intents, contact и т.д.). "
        "Требует ENABLE_SYNAPSE=1."
    ),
    parameters={
        "profile": {"type": "object", "description": "JSON-профиль пользователя"},
        "profile_id": {
            "type": "string",
            "description": "Опциональный id (иначе сгенерируется). [A-Za-z0-9_.-]{1,80}",
        },
    },
    required=["profile"],
)
def publish_profile(client=None, **kwargs) -> str:
    profile = kwargs.get("profile")
    if not isinstance(profile, dict) or not profile:
        return "❌ profile должен быть непустым JSON-объектом"
    pid = kwargs.get("profile_id") or uuid.uuid4().hex[:12]
    try:
        pid = _safe_id(pid)
    except ValueError as e:
        return f"❌ {e}"

    record = {
        "profile_id": pid,
        "published_at": _now(),
        "profile": profile,
    }
    _write_json(_data_dir() / "profiles" / f"{pid}.json", record)
    return f"✅ Профиль '{pid}' опубликован в {_data_dir() / 'profiles'}"


@mcp_tool(
    name="search_people",
    description=(
        "Поиск людей по сохранённым профилям. MVP: keyword-скоринг "
        "(эмбеддинги — в батче 7b). Требует ENABLE_SYNAPSE=1."
    ),
    parameters={
        "query": {"type": "string", "description": "Поисковый запрос на естественном языке"},
        "limit": {"type": "integer", "description": "Сколько результатов (по умолчанию 10)"},
    },
    required=["query"],
)
def search_people(client=None, **kwargs) -> str:
    query = (kwargs.get("query") or "").strip()
    if not query:
        return "❌ Пустой запрос"
    limit = int(kwargs.get("limit") or 10)
    qt = _tokens(query)

    scored = []
    for path in sorted((_data_dir() / "profiles").glob("*.json")):
        try:
            rec = _read_json(path)
        except Exception:  # noqa: BLE001
            continue
        haystack = json.dumps(rec.get("profile", {}), ensure_ascii=False)
        s = _score(qt, haystack)
        if s > 0:
            scored.append((s, rec))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:limit]
    if not top:
        return "(совпадений нет — MVP keyword-поиск)"

    lines = [f"Найдено {len(top)} (keyword-MVP, эмбеддинги — 7b):"]
    for s, rec in top:
        name = rec.get("profile", {}).get("name") or rec.get("profile_id")
        lines.append(f"- {name} (id={rec.get('profile_id')}, score={s:.2f})")
    return "\n".join(lines)


@mcp_tool(
    name="propose_contact",
    description=(
        "Создаёт запрос контакта к профилю. Контакт НЕ раскрывается "
        "автоматически — только по взаимному согласию. Требует ENABLE_SYNAPSE=1."
    ),
    parameters={
        "to_profile_id": {"type": "string", "description": "id профиля адресата"},
        "message": {"type": "string", "description": "Сообщение к запросу"},
        "from_profile_id": {"type": "string", "description": "Ваш profile_id (опционально)"},
    },
    required=["to_profile_id"],
)
def propose_contact(client=None, **kwargs) -> str:
    to_id = kwargs.get("to_profile_id") or ""
    try:
        to_id = _safe_id(to_id)
    except ValueError as e:
        return f"❌ {e}"

    target = _data_dir() / "profiles" / f"{to_id}.json"
    if not target.exists():
        return f"❌ Профиль '{to_id}' не найден"

    rid = uuid.uuid4().hex[:12]
    record = {
        "request_id": rid,
        "to_profile_id": to_id,
        "from_profile_id": kwargs.get("from_profile_id") or None,
        "message": kwargs.get("message") or "",
        "status": "pending",
        "created_at": _now(),
    }
    _write_json(_data_dir() / "requests" / f"{rid}.json", record)
    return (
        f"✅ Запрос контакта '{rid}' создан (status=pending). "
        "Контакт раскрывается только при взаимном согласии."
    )


@mcp_tool(
    name="save_note",
    description="Сохраняет личную заметку. Требует ENABLE_SYNAPSE=1.",
    parameters={
        "text": {"type": "string", "description": "Текст заметки"},
        "tags": {"type": "array", "items": {"type": "string"}, "description": "Теги"},
    },
    required=["text"],
)
def save_note(client=None, **kwargs) -> str:
    text = (kwargs.get("text") or "").strip()
    if not text:
        return "❌ Пустая заметка"
    nid = uuid.uuid4().hex[:12]
    record = {
        "note_id": nid,
        "text": text,
        "tags": kwargs.get("tags") or [],
        "created_at": _now(),
    }
    _write_json(_data_dir() / "notes" / f"{nid}.json", record)
    return f"✅ Заметка '{nid}' сохранена"


@mcp_tool(
    name="search_notes",
    description=(
        "Поиск по личным заметкам. MVP: keyword-скоринг. Требует ENABLE_SYNAPSE=1."
    ),
    parameters={
        "query": {"type": "string", "description": "Поисковый запрос"},
        "limit": {"type": "integer", "description": "Сколько результатов (по умолчанию 10)"},
    },
    required=["query"],
)
def search_notes(client=None, **kwargs) -> str:
    query = (kwargs.get("query") or "").strip()
    if not query:
        return "❌ Пустой запрос"
    limit = int(kwargs.get("limit") or 10)
    qt = _tokens(query)

    scored = []
    for path in sorted((_data_dir() / "notes").glob("*.json")):
        try:
            rec = _read_json(path)
        except Exception:  # noqa: BLE001
            continue
        s = _score(qt, rec.get("text", ""))
        if s > 0:
            scored.append((s, rec))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:limit]
    if not top:
        return "(совпадений нет — MVP keyword-поиск)"

    lines = [f"Найдено {len(top)} заметок:"]
    for s, rec in top:
        preview = rec.get("text", "")[:80].replace("\n", " ")
        lines.append(f"- [{rec.get('note_id')}] {preview}… (score={s:.2f})")
    return "\n".join(lines)


@mcp_tool(
    name="index_github",
    description=(
        "Индексирует публичный GitHub-профиль как Synapse-профиль. "
        "Требует ENABLE_SYNAPSE=1 и GitHub-токен (заголовок Authorization)."
    ),
    parameters={
        "username": {"type": "string", "description": "GitHub-логин"},
    },
    required=["username"],
)
def index_github(client=None, **kwargs) -> str:
    username = (kwargs.get("username") or "").strip()
    if not username:
        return "❌ Пустой username"
    if client is None:
        return "❌ Нужен GitHub-токен (заголовок Authorization)"

    try:
        user_resp = client._request("GET", f"/users/{username}")
        user = user_resp.json()
    except Exception as e:  # noqa: BLE001
        return f"❌ GitHub: {e}"

    repos = []
    try:
        repos_resp = client._request(
            "GET", f"/users/{username}/repos", params={"per_page": 30, "sort": "updated"}
        )
        repos = [r.get("name") for r in repos_resp.json() if isinstance(r, dict)]
    except Exception:  # noqa: BLE001
        pass

    profile = {
        "name": user.get("name") or username,
        "github": username,
        "bio": user.get("bio") or "",
        "company": user.get("company") or "",
        "location": user.get("location") or "",
        "blog": user.get("blog") or "",
        "public_repos": user.get("public_repos"),
        "repos": repos,
        "source": "github",
    }
    pid = f"github_{username}"
    record = {"profile_id": pid, "published_at": _now(), "profile": profile}
    _write_json(_data_dir() / "profiles" / f"{pid}.json", record)
    return f"✅ GitHub-профиль '{username}' проиндексирован как '{pid}'"
