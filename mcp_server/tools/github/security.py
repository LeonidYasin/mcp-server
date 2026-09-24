"""MCP tools: GitHub security alerts."""

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient


@mcp_tool(
    name="list_dependabot_alerts",
    description="Список Dependabot-алертов репозитория",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "state": {"type": "string", "description": "open|dismissed|fixed|auto_dismissed (по умолчанию open)"},
        "severity": {"type": "string", "description": "low|medium|high|critical"},
    },
    required=["owner", "repo"],
)
def list_dependabot_alerts(client: GitHubClient, **kwargs) -> str:
    params = {"state": kwargs.get("state", "open"), "per_page": 50}
    if kwargs.get("severity"):
        params["severity"] = kwargs["severity"]
    resp = client._request(
        "GET", f"/repos/{kwargs['owner']}/{kwargs['repo']}/dependabot/alerts", params=params
    )
    items = resp.json()
    if isinstance(items, dict):
        return f"❌ {items.get('message', 'Ошибка')}"
    if not items:
        return "Dependabot-алертов нет"
    lines = [f"Dependabot ({len(items)}):"]
    for a in items:
        sec = a.get("security_advisory", {})
        pkg = a.get("dependency", {}).get("package", {}).get("name", "?")
        lines.append(f"  [{sec.get('severity')}] {pkg}: {sec.get('summary', '')[:80]}")
    return "\n".join(lines)


@mcp_tool(
    name="list_code_scanning_alerts",
    description="Список Code Scanning (CodeQL) алертов репозитория",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "state": {"type": "string", "description": "open|closed|dismissed"},
    },
    required=["owner", "repo"],
)
def list_code_scanning_alerts(client: GitHubClient, **kwargs) -> str:
    params = {"state": kwargs.get("state", "open"), "per_page": 50}
    resp = client._request(
        "GET", f"/repos/{kwargs['owner']}/{kwargs['repo']}/code-scanning/alerts", params=params
    )
    items = resp.json()
    if isinstance(items, dict):
        return f"❌ {items.get('message', 'Ошибка')}"
    if not items:
        return "Code Scanning алертов нет"
    lines = [f"Code Scanning ({len(items)}):"]
    for a in items:
        rule = a.get("rule", {})
        loc = a.get("most_recent_instance", {}).get("location", {})
        lines.append(
            f"  [{rule.get('severity')}] {rule.get('id')} — {loc.get('path', '?')}:{loc.get('start_line', '?')}"
        )
    return "\n".join(lines)


@mcp_tool(
    name="list_secret_scanning_alerts",
    description="Список Secret Scanning алертов репозитория",
    parameters={
        "owner": {"type": "string"},
        "repo": {"type": "string"},
        "state": {"type": "string", "description": "open|resolved"},
    },
    required=["owner", "repo"],
)
def list_secret_scanning_alerts(client: GitHubClient, **kwargs) -> str:
    params = {"state": kwargs.get("state", "open"), "per_page": 50}
    resp = client._request(
        "GET", f"/repos/{kwargs['owner']}/{kwargs['repo']}/secret-scanning/alerts", params=params
    )
    items = resp.json()
    if isinstance(items, dict):
        return f"❌ {items.get('message', 'Ошибка')}"
    if not items:
        return "Secret Scanning алертов нет"
    lines = [f"Secret Scanning ({len(items)}):"]
    for a in items:
        lines.append(
            f"  [{a.get('state')}] {a.get('secret_type_display_name', a.get('secret_type'))}"
        )
    return "\n".join(lines)
