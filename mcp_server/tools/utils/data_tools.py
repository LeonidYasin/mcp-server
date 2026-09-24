"""MCP tools: data converters (csv, yaml, markdown)."""

import csv
import io
import json

from mcp_server.core.registry import mcp_tool


def _try_yaml():
    try:
        import yaml  # type: ignore
        return yaml
    except ImportError:
        return None


@mcp_tool(
    name="csv_parse",
    description="Парсит CSV в JSON (список объектов)",
    parameters={
        "text": {"type": "string", "description": "CSV-текст"},
        "delimiter": {"type": "string", "description": "Разделитель (по умолчанию ',')"},
        "limit": {"type": "integer", "description": "Сколько строк (по умолчанию 100)"},
    },
    required=["text"],
)
def csv_parse(client=None, **kwargs) -> str:
    delim = kwargs.get("delimiter", ",") or ","
    limit = int(kwargs.get("limit", 100))
    reader = csv.DictReader(io.StringIO(kwargs["text"]), delimiter=delim)
    rows = []
    for i, row in enumerate(reader):
        if i >= limit:
            break
        rows.append(row)
    return json.dumps(rows, indent=2, ensure_ascii=False)


@mcp_tool(
    name="csv_generate",
    description="Генерирует CSV из JSON-массива объектов",
    parameters={
        "json_text": {"type": "string", "description": "JSON-массив объектов"},
        "delimiter": {"type": "string", "description": "Разделитель (по умолчанию ',')"},
    },
    required=["json_text"],
)
def csv_generate(client=None, **kwargs) -> str:
    try:
        data = json.loads(kwargs["json_text"])
    except Exception as e:  # noqa: BLE001
        return f"❌ Невалидный JSON: {e}"
    if not isinstance(data, list) or not data:
        return "❌ Ожидается непустой JSON-массив объектов"
    fields = list({k for row in data for k in row.keys()})
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, delimiter=kwargs.get("delimiter", ",") or ",")
    writer.writeheader()
    for row in data:
        writer.writerow(row)
    return buf.getvalue()


@mcp_tool(
    name="yaml_to_json",
    description="Конвертирует YAML в JSON (требует PyYAML)",
    parameters={"text": {"type": "string", "description": "YAML-текст"}},
    required=["text"],
)
def yaml_to_json(client=None, **kwargs) -> str:
    yaml = _try_yaml()
    if yaml is None:
        return "❌ PyYAML не установлен. Установите: pip install pyyaml"
    try:
        data = yaml.safe_load(kwargs["text"])
    except Exception as e:  # noqa: BLE001
        return f"❌ Ошибка YAML: {e}"
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp_tool(
    name="json_to_yaml",
    description="Конвертирует JSON в YAML (требует PyYAML)",
    parameters={"text": {"type": "string", "description": "JSON-текст"}},
    required=["text"],
)
def json_to_yaml(client=None, **kwargs) -> str:
    yaml = _try_yaml()
    if yaml is None:
        return "❌ PyYAML не установлен. Установите: pip install pyyaml"
    try:
        data = json.loads(kwargs["text"])
    except Exception as e:  # noqa: BLE001
        return f"❌ Невалидный JSON: {e}"
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


@mcp_tool(
    name="markdown_to_html",
    description="Простое преобразование Markdown в HTML (заголовки, **жирный**, *курсив*, `код`, списки)",
    parameters={"text": {"type": "string", "description": "Markdown-текст"}},
    required=["text"],
)
def markdown_to_html(client=None, **kwargs) -> str:
    import re
    lines = kwargs["text"].splitlines()
    out = []
    in_list = False
    for line in lines:
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            if in_list:
                out.append("</ul>")
                in_list = False
            level = len(m.group(1))
            out.append(f"<h{level}>{m.group(2)}</h{level}>")
            continue
        if re.match(r"^[-*+]\s+", line):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{line[2:].strip()}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if not line.strip():
            out.append("")
        else:
            out.append(f"<p>{line}</p>")
    if in_list:
        out.append("</ul>")
    html = "\n".join(out)
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)
    html = re.sub(r"`(.+?)`", r"<code>\1</code>", html)
    html = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', html)
    return html
