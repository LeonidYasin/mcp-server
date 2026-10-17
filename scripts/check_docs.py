"""Offline documentation guard: registry inventory and repository-local Markdown links.

Run with project dependencies installed. No handlers, GitHub requests, model
providers, production services or user files are invoked. --write-inventory is
an explicit maintainer action, never part of the default check.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs/tool-inventory.json"
CHILD = r'''
import contextlib, io, json
with contextlib.redirect_stdout(io.StringIO()):
    from mcp_server.server import registry, _tool_needs_token
rows = []
for tool in sorted(registry.get_all(), key=lambda t: t.name):
    if not set(tool.required).issubset(tool.parameters):
        raise RuntimeError("Unknown required parameter: " + tool.name)
    rows.append({"name": tool.name, "category": tool.handler.__module__.split(".")[2],
                 "token_required": _tool_needs_token(tool.name)})
print(json.dumps(rows, sort_keys=True))
'''


def inventory() -> dict:
    profiles = {}
    for name, enabled in (("default", "0"), ("all_enabled", "1")):
        env = dict(os.environ)
        for flag in ("ENABLE_LOCAL_TOOLS", "ENABLE_LOCAL_SHELL", "ENABLE_SYNAPSE", "ENABLE_AGENT_ROOMS"):
            env[flag] = enabled
        # Discovery only; providers must not be activated by the calling shell.
        env.pop("SYNAPSE_EMBEDDING_PROVIDER", None)
        result = subprocess.run([sys.executable, "-c", CHILD], cwd=ROOT, env=env,
                                capture_output=True, text=True, timeout=30, check=True)
        rows = json.loads(result.stdout)
        profiles[name] = {"count": len(rows), "tools": rows}
    return {"format_version": 1, "profiles": profiles}


def without_fences(text: str) -> str:
    lines = []
    fence_char, fence_size = None, 0
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if match:
            token = match[1]
            if fence_char is None:
                fence_char, fence_size = token[0], len(token)
            elif token[0] == fence_char and len(token) >= fence_size:
                fence_char, fence_size = None, 0
            lines.append("")
        elif fence_char is None:
            lines.append(line)
    if fence_char:
        raise ValueError("Unclosed fenced code block")
    return "\n".join(lines)


def headings(path: Path) -> set[str]:
    found, repeated = set(), {}
    for line in without_fences(path.read_text(encoding="utf-8")).splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)(?:\s+#+)?$", line)
        if not match:
            continue
        text = re.sub(r"<[^>]*>", "", match[1]).strip().lower()
        # GitHub-style Unicode slugs for this repository's plain headings.
        slug = "".join(c for c in text if c.isalnum() or c in "_ -").replace(" ", "-")
        occurrence = repeated.get(slug, 0)
        repeated[slug] = occurrence + 1
        found.add(slug + (f"-{occurrence}" if occurrence else ""))
    return found


def check_links(root: Path = ROOT) -> tuple[int, list[str]]:
    errors, checked = [], 0
    paths = sorted([*root.glob("*.md"), *root.joinpath("docs").rglob("*.md")])
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if "\ufffd" in text:
            errors.append(f"{path.relative_to(root)}: replacement character")
        try:
            text = without_fences(text)
        except ValueError as exc:
            errors.append(f"{path.relative_to(root)}: {exc}")
            continue
        for target in re.findall(r"!?\[[^\]\n]*\]\(([^)\s]+)\)", text):
            parts = urlsplit(target)
            if parts.scheme or parts.netloc:
                continue
            checked += 1
            dest = (path.parent / unquote(parts.path)).resolve() if parts.path else path
            if not dest.exists():
                errors.append(f"{path.relative_to(root)}: missing {target}")
            elif parts.fragment and dest.suffix == ".md":
                if unquote(parts.fragment) not in headings(dest):
                    errors.append(f"{path.relative_to(root)}: missing anchor {target}")
    return checked, errors


def check() -> dict:
    actual = inventory()
    if actual != json.loads(INVENTORY.read_text(encoding="utf-8")):
        raise ValueError("Registry drift: review changes and run scripts/check_docs.py --write-inventory")
    tools_doc = (ROOT / "TOOLS.md").read_text(encoding="utf-8")
    documented = set(re.findall(r"`([a-z][a-z0-9_]+)`", tools_doc))
    names = {row["name"] for row in actual["profiles"]["all_enabled"]["tools"]}
    missing = sorted(names - documented)
    if missing:
        raise ValueError("TOOLS.md missing registered tools: " + ", ".join(missing))
    links, errors = check_links()
    if errors:
        raise ValueError("\n".join(errors))
    return {"inventory": {k: v["count"] for k, v in actual["profiles"].items()},
            "local_links_checked": links, "result": "passed"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-inventory", action="store_true")
    args = parser.parse_args()
    if args.write_inventory:
        INVENTORY.write_text(json.dumps(inventory(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(check(), ensure_ascii=False))


if __name__ == "__main__":
    main()
