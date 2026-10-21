"""Bounded binary payloads, verified GitHub user ownership, redacted failures."""
import json
import os

from mcp_server.core.registry import mcp_tool
from mcp_server.core.uploads import UploadError, UploadStore, CHUNK_BYTES


def authenticate_owner(client):
    # Never trust a nonempty header or a caller-supplied owner/session ID.
    # Fresh verification deliberately avoids retaining PATs or stale auth caches.
    if client is None:
        raise UploadError("authentication_required")
    try:
        response = client._client.get(
            "https://api.github.com/user", headers=dict(client._headers),
            follow_redirects=False, timeout=10,
        )
        if response.status_code != 200:
            raise UploadError("authentication_failed")
        identity = response.json().get("id")
        if type(identity) is not int or identity < 1:
            raise UploadError("authentication_failed")
        return f"github:{identity}"
    except UploadError:
        raise
    except Exception:
        raise UploadError("authentication_unavailable") from None


def _invoke(client, action, **kwargs):
    try:
        if os.environ.get("ENABLE_FILE_UPLOADS", "").strip().lower() not in {"1", "true", "yes", "on"}:
            raise UploadError("uploads_disabled")
        owner = authenticate_owner(client)
        allowed = os.environ.get("FILE_UPLOAD_ALLOWED_USERS", "").split(",")
        allowed = [part.strip() for part in allowed]
        if not allowed or any(not part.isascii() or not part.isdecimal() or int(part) < 1 for part in allowed):
            raise UploadError("upload_allowlist_not_configured")
        if owner not in {f"github:{int(part)}" for part in allowed}:
            raise UploadError("owner_not_allowed")
        root = os.environ.get("FILE_UPLOAD_ROOT", "")
        if not root:
            raise UploadError("staging_not_configured")
        result = getattr(UploadStore(root), action)(owner, **kwargs)
        payload = {"ok": True, **result}
    except UploadError as exc:
        payload = {"ok": False, "error": str(exc)}
    except Exception:
        # No exception traceback/body/path, payload, token or capability in logs.
        payload = {"ok": False, "error": "staging_unavailable"}
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}


@mcp_tool("begin_file_upload", "Start private bounded staging (opt-in). GitHub-verified owner, no server path. Returns upload_id, expiry and limits; same request_key is idempotent until expiry/cancel.", {
    "name": {"type": "string", "minLength": 1, "maxLength": 128, "description": "Safe display filename, never a path"},
    "size": {"type": "integer", "minimum": 0, "maximum": 67108864},
    "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "request_key": {"type": "string", "pattern": "^[0-9a-f]{64}$", "description": "Client random 32-byte hex retry key; same key must use identical metadata"},
}, required=["name", "size", "sha256", "request_key"])
def begin_file_upload(client, name, size, sha256, request_key):
    return _invoke(client, "begin", name=name, size=size, sha256=sha256, request_key=request_key)


@mcp_tool("append_file_chunk", "Append <=48 KiB bytes as canonical base64. Exact same offset+bytes retry is idempotent; gaps/overlaps/conflicts refused. Never echoes contents.", {
    "upload_id": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "offset": {"type": "integer", "minimum": 0},
    "data": {"type": "string", "maxLength": 4 * ((CHUNK_BYTES + 2) // 3), "description": "Canonical base64, generated programmatically outside model text"},
    "chunk_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
}, required=["upload_id", "offset", "data", "chunk_sha256"])
def append_file_chunk(client, upload_id, offset, data, chunk_sha256):
    return _invoke(client, "append", upload_id=upload_id, offset=offset, data=data, chunk_sha256=chunk_sha256)


@mcp_tool("finish_file_upload", "Validate complete bytes/size/SHA-256 before issuing owner-scoped opaque file_id. Retry returns same file_id; no Release/Actions mutation.", {
    "upload_id": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
}, required=["upload_id"])
def finish_file_upload(client, upload_id):
    return _invoke(client, "finish", upload_id=upload_id)


@mcp_tool("get_file_upload_status", "Owner-only bounded upload progress/expiry; no bytes, token or server-local path.", {
    "upload_id": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
}, required=["upload_id"])
def get_file_upload_status(client, upload_id):
    return _invoke(client, "status", upload_id=upload_id)


@mcp_tool("cancel_file_upload", "Delete this owner's pending or finalized upload and its chunks; invalidates file_id. Unknown/expired IDs are refused.", {
    "upload_id": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
}, required=["upload_id"])
def cancel_file_upload(client, upload_id):
    return _invoke(client, "cancel", upload_id=upload_id)


@mcp_tool("cleanup_file_uploads", "Purge expired staging records/chunks, including finalized ones; never report other owners. No unexpired files are deleted.", {})
def cleanup_file_uploads(client):
    return _invoke(client, "cleanup")
