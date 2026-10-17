"""Bounded, read-only release metadata. No asset bytes, redirects or mutations."""
from __future__ import annotations

import json
import re
import time
from urllib.parse import quote, urlsplit

import httpx

from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient

MAX_RESPONSE_BYTES = 512 * 1024
MAX_OUTPUT_BYTES = 64 * 1024


class InvalidMetadata(ValueError):
    pass


def _error(code, status=None):
    return {"ok": False, "error": code, "http_status": status}


def _identity(owner, repo):
    if (not isinstance(owner, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,100}", owner)
            or not isinstance(repo, str) or repo in (".", "..")
            or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", repo)):
        raise InvalidMetadata()
    return f"/repos/{owner}/{repo}"


def _positive(value):
    if type(value) is not int or not 1 <= value < 2**63:
        raise InvalidMetadata()
    return value


def _text(value, maximum=1024, nullable=True):
    if value is None and nullable:
        return None
    if not isinstance(value, str) or len(value) > maximum:
        raise InvalidMetadata()
    return value


def _url(value, host, prefix):
    # Metadata only; these URLs are never followed. No query/capability reflection.
    if not isinstance(value, str) or len(value) > 4096:
        return None
    try:
        p = urlsplit(value)
        if (p.scheme != "https" or p.netloc.lower() != host
                or p.query or p.fragment or not p.path.startswith(prefix)
                or "\\" in value or any(ord(c) < 33 or ord(c) > 126 for c in value)):
            return None
    except ValueError:
        return None
    return value


def _read(client, path, params=None):
    """Bypass legacy _request: it follows redirects and loses status/error bounds."""
    started = time.monotonic()
    try:
        with client._client.stream(
            "GET", "https://api.github.com" + path,
            params=params, headers=dict(client._headers),
            follow_redirects=False, timeout=15.0,
        ) as response:
            status = response.status_code
            if status != 200:
                code = {401: "authentication_failed", 403: "access_denied_or_rate_limited",
                        404: "not_found_or_inaccessible", 429: "rate_limited"}.get(status)
                return _error(code or ("redirect_refused" if 300 <= status < 400
                                       else "upstream_failure"), status)
            body = bytearray()
            for chunk in response.iter_bytes(chunk_size=8192):
                if time.monotonic() - started > 35:
                    return _error("request_timeout", status)
                if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                    return _error("response_too_large", status)
                body.extend(chunk)
            try:
                data = json.loads(body)
            except (ValueError, RecursionError):
                return _error("invalid_api_response", status)
            return {"ok": True, "data": data, "link": response.headers.get("Link", ""),
                    "http_status": status}
    except httpx.TimeoutException:
        return _error("request_timeout")
    except Exception:
        # No body, exception text, request headers or PAT in a tool result.
        return _error("request_failed")


def _encode(result):
    encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    try:
        output_size = len(encoded.encode("utf-8"))
    except UnicodeError:
        return json.dumps(_error("invalid_api_response", 200))
    if output_size > MAX_OUTPUT_BYTES:
        return json.dumps(_error("output_too_large_reduce_page_size"))
    return encoded


COMMON = {"owner": {"type": "string"}, "repo": {"type": "string"}}


@mcp_tool(
    name="get_release",
    description="Read-only release lookup by exactly one tag or ID; bounded structured metadata. No create/publish or redirect.",
    parameters={**COMMON, "release_id": {"type": "integer", "minimum": 1},
                "tag": {"type": "string", "minLength": 1, "maxLength": 1024,
                        "description": "Exact tag; use exactly one of tag/release_id"}},
    required=["owner", "repo"],
)
def get_release(client: GitHubClient, **kwargs) -> str:
    try:
        base = _identity(kwargs.get("owner"), kwargs.get("repo"))
        by_id = kwargs.get("release_id") is not None
        by_tag = kwargs.get("tag") is not None
        if by_id == by_tag:
            raise InvalidMetadata()
        if by_id:
            release_id = _positive(kwargs["release_id"])
            path = f"{base}/releases/{release_id}"
        else:
            tag = _text(kwargs["tag"], nullable=False)
            if not tag or ".." in tag or any(ord(c) < 33 or ord(c) == 127 for c in tag):
                raise InvalidMetadata()
            path = f"{base}/releases/tags/{quote(tag, safe='')}"
    except InvalidMetadata:
        return _encode(_error("invalid_input"))
    result = _read(client, path)
    if not result["ok"]:
        return _encode(result)
    try:
        row = result["data"]
        if not isinstance(row, dict):
            raise InvalidMetadata()
        rid = _positive(row.get("id"))
        if by_id and rid != release_id:
            raise InvalidMetadata()
        actual_tag = _text(row.get("tag_name"), nullable=False)
        if by_tag and actual_tag != tag:
            raise InvalidMetadata()
        if type(row.get("draft")) is not bool or type(row.get("prerelease")) is not bool:
            raise InvalidMetadata()
        release = {"release_id": rid, "tag_name": actual_tag,
                   "name": _text(row.get("name")), "draft": row["draft"],
                   "prerelease": row["prerelease"],
                   "target_commitish": _text(row.get("target_commitish")),
                   "created_at": _text(row.get("created_at"), 64),
                   "published_at": _text(row.get("published_at"), 64),
                   "api_url": f"https://api.github.com{base}/releases/{rid}",
                   "html_url": _url(row.get("html_url"), "github.com", base[6:] + "/releases/")}
        return _encode({"ok": True, "release": release,
                        "lookup": "id" if by_id else "tag", "http_status": 200,
                        "assets_included": False})
    except (InvalidMetadata, TypeError):
        return _encode(_error("invalid_api_response", 200))


@mcp_tool(
    name="list_release_assets",
    description="Read-only single page of Release asset metadata/IDs/digest, NOT Actions artifacts or asset bytes. Explicit pagination; bounded output.",
    parameters={**COMMON, "release_id": {"type": "integer", "minimum": 1},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100,
                          "description": "Rows on one page, default25; reduce if output exceeds64KiB"},
                "page": {"type": "integer", "minimum": 1, "description": "Page number, default1"}},
    required=["owner", "repo", "release_id"],
)
def list_release_assets(client: GitHubClient, **kwargs) -> str:
    try:
        base = _identity(kwargs.get("owner"), kwargs.get("repo"))
        rid = _positive(kwargs.get("release_id"))
        limit, page = kwargs.get("limit", 25), kwargs.get("page", 1)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise InvalidMetadata()
        _positive(page)
    except InvalidMetadata:
        return _encode(_error("invalid_input"))
    path = f"{base}/releases/{rid}/assets"
    result = _read(client, path, {"per_page": limit, "page": page})
    if not result["ok"]:
        return _encode(result)
    try:
        rows = result["data"]
        if not isinstance(rows, list) or len(rows) > limit:
            raise InvalidMetadata()
        items, seen = [], set()
        for row in rows:
            if not isinstance(row, dict):
                raise InvalidMetadata()
            aid = _positive(row.get("id"))
            if aid in seen or type(row.get("size")) is not int or row["size"] < 0:
                raise InvalidMetadata()
            seen.add(aid)
            digest = _text(row.get("digest"), 256)
            items.append({"asset_id": aid, "name": _text(row.get("name"), 256, False),
                          "label": _text(row.get("label"), 256), "size": row["size"],
                          "content_type": _text(row.get("content_type"), 256),
                          "state": _text(row.get("state"), 64), "digest": digest,
                          "digest_source": "github" if digest is not None else None,
                          "api_url": f"https://api.github.com{base}/releases/assets/{aid}",
                          "browser_download_url": _url(row.get("browser_download_url"), "github.com", base[6:] + "/releases/download/"),
                          "created_at": _text(row.get("created_at"), 64),
                          "updated_at": _text(row.get("updated_at"), 64)})
        # Link metadata is inspected, NEVER followed; pagination remains explicit.
        next_present = bool(re.search(r';\s*rel="next"', result["link"]))
        has_next = True if next_present else (False if len(rows) < limit else None)
        return _encode({"ok": True, "release_id": rid, "assets": items, "http_status": 200,
                        "pagination": {"scope": "single_page", "page": page, "per_page": limit,
                                       "returned": len(items), "has_next": has_next,
                                       "next_page": page + 1 if next_present else None},
                        "total_count": None, "asset_bytes_fetched": False})
    except (InvalidMetadata, TypeError):
        return _encode(_error("invalid_api_response", 200))
