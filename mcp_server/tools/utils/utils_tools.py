"""MCP tools: pure-python utilities (encoding, hashing, json, dates, regex, diff)."""

import base64
import datetime as _dt
import difflib
import hashlib
import json
import re
import uuid

from mcp_server.core.registry import mcp_tool


@mcp_tool(
    name="base64_encode",
    description="Кодирует текст в base64 (UTF-8)",
    parameters={"text": {"type": "string"}},
    required=["text"],
)
def base64_encode(client=None, **kwargs) -> str:
    return base64.b64encode(kwargs["text"].encode("utf-8")).decode("ascii")


@mcp_tool(
    name="base64_decode",
    description="Декодирует base64 в текст (UTF-8)",
    parameters={"data": {"type": "string"}},
    required=["data"],
)
def base64_decode(client=None, **kwargs) -> str:
    try:
        return base64.b64decode(kwargs["data"]).decode("utf-8", errors="replace")
    except Exception as e:  # noqa: BLE001
        return f"❌ Ошибка декодирования: {e}"


@mcp_tool(
    name="hash_text",
    description="Считает хэш текста: md5 | sha1 | sha256 | sha512",
    parameters={
        "text": {"type": "string"},
        "algo": {"type": "string", "description": "md5|sha1|sha256|sha512 (по умолчанию sha256)"},
    },
    required=["text"],
)
def hash_text(client=None, **kwargs) -> str:
    algo = (kwargs.get("algo") or "sha256").lower()
    if algo not in ("md5", "sha1", "sha256", "sha512"):
        return f"❌ Неизвестный алгоритм: {algo}"
    h = hashlib.new(algo)
    h.update(kwargs["text"].encode("utf-8"))
    return f"{algo}: {h.hexdigest()}"


@mcp_tool(
    name="json_format",
    description="Форматирует JSON (pretty-print) или валидирует",
    parameters={
        "text": {"type": "string", "description": "JSON-строка"},
        "indent": {"type": "integer", "description": "Отступ (по умолчанию 2)"},
    },
    required=["text"],
)
def json_format(client=None, **kwargs) -> str:
    try:
        data = json.loads(kwargs["text"])
    except Exception as e:  # noqa: BLE001
        return f"❌ Невалидный JSON: {e}"
    return json.dumps(data, indent=int(kwargs.get("indent", 2)), ensure_ascii=False)


@mcp_tool(
    name="json_query",
    description="Достаёт значение из JSON по точечному пути (a.b.0.c)",
    parameters={
        "text": {"type": "string"},
        "path": {"type": "string", "description": "Путь через точку, например items.0.name"},
    },
    required=["text", "path"],
)
def json_query(client=None, **kwargs) -> str:
    try:
        cur = json.loads(kwargs["text"])
    except Exception as e:  # noqa: BLE001
        return f"❌ Невалидный JSON: {e}"
    for part in kwargs["path"].split("."):
        if not part:
            continue
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return f"❌ Нет индекса '{part}' в списке"
        elif isinstance(cur, dict):
            if part not in cur:
                return f"❌ Нет ключа '{part}'"
            cur = cur[part]
        else:
            return f"❌ Путь '{part}' не применим к {type(cur).__name__}"
    if isinstance(cur, (dict, list)):
        return json.dumps(cur, indent=2, ensure_ascii=False)
    return str(cur)


@mcp_tool(
    name="uuid_generate",
    description="Генерирует UUID (по умолчанию v4)",
    parameters={"version": {"type": "integer", "description": "4 или 1 (по умолчанию 4)"}},
    required=[],
)
def uuid_generate(client=None, **kwargs) -> str:
    v = int(kwargs.get("version", 4))
    if v == 1:
        return str(uuid.uuid1())
    return str(uuid.uuid4())


@mcp_tool(
    name="timestamp_now",
    description="Текущее время: unix + ISO + UTC",
    parameters={},
    required=[],
)
def timestamp_now(client=None, **kwargs) -> str:
    now = _dt.datetime.now(_dt.timezone.utc)
    return (
        f"unix: {int(now.timestamp())}\n"
        f"iso: {now.isoformat()}\n"
        f"utc: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}"
    )


@mcp_tool(
    name="date_convert",
    description="Конвертирует дату: ISO <-> unix (секунды)",
    parameters={
        "value": {"type": "string", "description": "ISO-строка или unix-секунды"},
    },
    required=["value"],
)
def date_convert(client=None, **kwargs) -> str:
    raw = kwargs["value"].strip()
    # try unix
    if re.fullmatch(r"-?\d+", raw):
        ts = int(raw)
        dt = _dt.datetime.fromtimestamp(ts, tz=_dt.timezone.utc)
        return f"unix {ts} -> {dt.isoformat()}"
    # try ISO
    try:
        iso = raw.replace("Z", "+00:00")
        dt = _dt.datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_dt.timezone.utc)
        return f"{raw} -> unix {int(dt.timestamp())}"
    except Exception as e:  # noqa: BLE001
        return f"❌ Не удалось распарсить дату: {e}"


@mcp_tool(
    name="regex_test",
    description="Проверяет regex на тексте, возвращает все совпадения",
    parameters={
        "pattern": {"type": "string", "description": "Regex-шаблон"},
        "text": {"type": "string", "description": "Текст для проверки"},
        "flags": {"type": "string", "description": "i=ignorecase, m=multiline, s=dotall (например 'im')"},
        "limit": {"type": "integer", "description": "Максимум совпадений (по умолчанию 50)"},
    },
    required=["pattern", "text"],
)
def regex_test(client=None, **kwargs) -> str:
    fl = 0
    for ch in (kwargs.get("flags") or ""):
        if ch == "i":
            fl |= re.I
        elif ch == "m":
            fl |= re.M
        elif ch == "s":
            fl |= re.S
    try:
        rx = re.compile(kwargs["pattern"], fl)
    except re.error as e:
        return f"❌ Ошибка в regex: {e}"
    matches = list(rx.finditer(kwargs["text"]))
    limit = int(kwargs.get("limit", 50))
    if not matches:
        return "Совпадений нет"
    lines = [f"Совпадений: {len(matches)}"]
    for m in matches[:limit]:
        groups = m.groups()
        lines.append(
            f"  [{m.start()}:{m.end()}] {m.group(0)!r}"
            + (f" groups={groups}" if groups else "")
        )
    if len(matches) > limit:
        lines.append(f"  ... ещё {len(matches) - limit}")
    return "\n".join(lines)


@mcp_tool(
    name="text_diff",
    description="Unified diff между двумя текстами",
    parameters={
        "a": {"type": "string", "description": "Старый текст"},
        "b": {"type": "string", "description": "Новый текст"},
        "name_a": {"type": "string", "description": "Имя A (по умолчанию 'a')"},
        "name_b": {"type": "string", "description": "Имя B (по умолчанию 'b')"},
        "context": {"type": "integer", "description": "Контекст строк (по умолчанию 3)"},
    },
    required=["a", "b"],
)
def text_diff(client=None, **kwargs) -> str:
    diff = difflib.unified_diff(
        kwargs["a"].splitlines(),
        kwargs["b"].splitlines(),
        fromfile=kwargs.get("name_a", "a"),
        tofile=kwargs.get("name_b", "b"),
        lineterm="",
        n=int(kwargs.get("context", 3)),
    )
    out = "\n".join(diff)
    return out if out else "Тексты идентичны"
