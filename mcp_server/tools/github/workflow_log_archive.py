"""Attempt-only log download; bounded ZIP, no extraction and no CDN credentials."""
import io
import logging
import re
import stat
import time
import zipfile
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit

import httpx

MAX_DOWNLOAD = 8 * 1024 * 1024
MAX_EXPANDED = 8 * 1024 * 1024
MAX_FILE = 4 * 1024 * 1024
MAX_FILES = 256


class LogError(Exception):
    def __init__(self, code, status=None):
        self.code, self.status = code, status
        super().__init__(code)


class _CapabilityFilter(logging.Filter):
    """httpx INFO normally prints the full signed URL; never persist its query."""
    def filter(self, record):
        message = record.getMessage()
        record.msg = re.sub(r'(https://[^\s?"\']+)\?[^\s"\']+', r'\1?[redacted]', message)
        record.args = ()
        return True


# Applies across threads: a temporary filter would race concurrent downloads.
if not any(isinstance(f, _CapabilityFilter) for f in logging.getLogger('httpx').filters):
    logging.getLogger('httpx').addFilter(_CapabilityFilter())


def unpack(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_DOWNLOAD:
        raise LogError('archive_limit_exceeded')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_FILES:
                raise LogError('archive_limit_exceeded')
            total, names, out = 0, set(), {}
            for info in entries:
                name = info.filename
                parts = PurePosixPath(name).parts
                mode = info.external_attr >> 16
                if (not name or len(name) > 512 or '\\' in name or name.startswith('/')
                        or '..' in parts or ':' in name or any(ord(c) < 32 for c in name)
                        or name in names or info.flag_bits & 1 or stat.S_ISLNK(mode)):
                    raise LogError('archive_invalid')
                names.add(name)
                if info.is_dir():
                    continue
                if not name.lower().endswith('.txt'):
                    raise LogError('archive_invalid')
                total += info.file_size
                if info.file_size > MAX_FILE or total > MAX_EXPANDED:
                    raise LogError('archive_limit_exceeded')
                with archive.open(info) as stream:
                    data = stream.read(MAX_FILE + 1)
                    if len(data) != info.file_size or len(data) > MAX_FILE:
                        raise LogError('archive_limit_exceeded')
                out[name] = data.decode('utf-8', errors='replace')
            return out
    except LogError:
        raise
    except Exception:
        raise LogError('archive_invalid') from None


def _location(value, token):
    if (not isinstance(value, str) or not value or len(value) > 16384
            or '\\' in value or any(ord(c) < 33 or ord(c) > 126 for c in value)):
        raise LogError('redirect_rejected')
    try:
        p = urlsplit(value)
        host = p.hostname or ''
        allowed = (host == 'objects.githubusercontent.com'
                   or re.fullmatch(r'[a-z0-9-]+(?:\.[a-z0-9-]+)*\.actions\.githubusercontent\.com', host)
                   or re.fullmatch(r'productionresultssa[0-9]+\.blob\.core\.windows\.net', host))
        if (p.scheme != 'https' or not allowed or p.port not in (None, 443)
                or p.username is not None or p.password is not None or p.fragment
                or not p.path.startswith('/') or (token and token in unquote(value))):
            raise LogError('redirect_rejected')
    except ValueError:
        raise LogError('redirect_rejected') from None
    return value


def download(client, owner, repo, run_id, attempt):
    """Caller validates/pins identity first. Redirect only from fixed API endpoint."""
    path = f'/repos/{owner}/{repo}/actions/runs/{run_id}/attempts/{attempt}/logs'
    auth = client._headers.get('Authorization', '')
    token = auth[7:] if auth.startswith('Bearer ') else ''
    try:
        with client._client.stream('GET', path, headers=dict(client._headers),
                                   follow_redirects=False, timeout=20) as response:
            if response.status_code != 302:
                raise LogError('logs_unavailable', response.status_code)
            destination = _location(response.headers.get('Location'), token)
        # Fresh client: no shared auth headers, cookies or redirect behavior.
        # trust_env=False also excludes proxy credentials inherited from env.
        with httpx.Client(follow_redirects=False, trust_env=False, timeout=20) as cdn:
            with cdn.stream('GET', destination) as response:
                if response.status_code != 200:
                    raise LogError('logs_download_failed', response.status_code)
                length = response.headers.get('Content-Length')
                if length is not None and (not length.isdigit() or int(length) > MAX_DOWNLOAD):
                    raise LogError('archive_limit_exceeded')
                chunks, size, deadline = [], 0, time.monotonic() + 30
                for chunk in response.iter_bytes(65536):
                    size += len(chunk)
                    if size > MAX_DOWNLOAD or time.monotonic() > deadline:
                        raise LogError('archive_limit_exceeded')
                    chunks.append(chunk)
        return unpack(b''.join(chunks))
    except LogError:
        raise
    except Exception:
        raise LogError('logs_download_failed') from None
