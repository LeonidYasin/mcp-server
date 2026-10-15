"""Private bounded staging, independent of shell/local tools. POSIX only.

SQLite transactions serialize workers; payload chunks and metadata commit together.
No user paths, URL fetching, token persistence, or automatic external mutations.
"""
import base64
import binascii
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import time
import unicodedata

CHUNK_BYTES = 48 * 1024
MAX_CHUNKS = 2048
ID = re.compile(r"[0-9a-f]{64}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")


class UploadError(Exception):
    """Only fixed, public error codes may leave this boundary."""


@dataclass(frozen=True)
class Limits:
    max_file_bytes: int = 64 * 1024 * 1024
    owner_bytes: int = 128 * 1024 * 1024
    total_bytes: int = 256 * 1024 * 1024
    owner_uploads: int = 8
    total_uploads: int = 32
    ttl_seconds: int = 3600


def _integer(value, lower=0):
    if type(value) is not int or value < lower:
        raise UploadError("invalid_integer")
    return value


def _digest(value):
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise UploadError("invalid_sha256")
    return value


def _identity(value, prefix=""):
    if not isinstance(value, str) or not value.startswith(prefix) or not ID.fullmatch(value[len(prefix):]):
        raise UploadError("invalid_id")
    return value


def _filename(value):
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeError:
            raise UploadError("invalid_name") from None
    if (not isinstance(value, str) or not value or value in (".", "..")
            or len(value) > 128 or len(value.encode("utf-8")) > 255
            or value != unicodedata.normalize("NFC", value)
            or value.startswith(".") or value != value.strip()
            or any(c in '/\\:' or unicodedata.category(c).startswith("C") for c in value)):
        raise UploadError("invalid_name")
    return value


def decode_chunk(data, sha256):
    _digest(sha256)
    if not isinstance(data, str) or not 1 <= len(data) <= 4 * ((CHUNK_BYTES + 2) // 3):
        raise UploadError("chunk_size_limit")
    try:
        raw = base64.b64decode(data, validate=True)
    except (ValueError, binascii.Error):
        raise UploadError("invalid_base64") from None
    if not raw or len(raw) > CHUNK_BYTES:
        raise UploadError("chunk_size_limit")
    if base64.b64encode(raw).decode("ascii") != data:
        raise UploadError("invalid_base64")
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise UploadError("chunk_hash_mismatch")
    return raw


class UploadStore:
    def __init__(self, root, limits=None, clock=time.time):
        self.root = Path(root)
        self.limits = limits or Limits()
        self.clock = clock
        for field in self.limits.__dataclass_fields__:
            _integer(getattr(self.limits, field), 1)

    def _private_root(self):
        if os.name != "posix" or not self.root.is_absolute():
            raise UploadError("unsafe_staging_root")
        # Refuse symlink ancestors too. A same-uid process/root is trusted; this
        # does not sandbox shell tools, or defend an already compromised account.
        for path in [*reversed(self.root.parents), self.root]:
            s = path.lstat()
            if not stat.S_ISDIR(s.st_mode) or s.st_uid not in (0, os.geteuid()):
                raise UploadError("unsafe_staging_root")
            writable = s.st_mode & 0o022
            if writable and not (s.st_uid == 0 and s.st_mode & stat.S_ISVTX):
                raise UploadError("unsafe_staging_root")
        s = self.root.lstat()
        if s.st_uid != os.geteuid() or s.st_mode & 0o077:
            raise UploadError("unsafe_staging_root")
        # Only fixed SQLite names exist; caller names/IDs never become paths.
        for suffix in ("", "-journal", "-wal", "-shm"):
            p = self.root / ("staging.sqlite3" + suffix)
            if p.exists() or p.is_symlink():
                s = p.lstat()
                if (not stat.S_ISREG(s.st_mode) or s.st_nlink != 1
                        or s.st_uid != os.geteuid() or s.st_mode & 0o077):
                    raise UploadError("unsafe_staging_database")
        fd = os.open(self.root / "staging.sqlite3", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            s = os.fstat(fd)
            if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or s.st_uid != os.geteuid() or s.st_mode & 0o077:
                raise UploadError("unsafe_staging_database")
        finally:
            os.close(fd)

    @contextmanager
    def _transaction(self):
        self._private_root()
        db = sqlite3.connect(str(self.root / "staging.sqlite3"), timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA secure_delete=ON")
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            db.execute("""CREATE TABLE IF NOT EXISTS uploads(
                upload_id TEXT PRIMARY KEY, owner TEXT NOT NULL, request_key TEXT NOT NULL,
                name TEXT NOT NULL, expected_size INTEGER NOT NULL, sha256 TEXT NOT NULL,
                received INTEGER NOT NULL DEFAULT 0, expires REAL NOT NULL,
                file_id TEXT UNIQUE, UNIQUE(owner, request_key))""")
            db.execute("""CREATE TABLE IF NOT EXISTS chunks(
                upload_id TEXT NOT NULL REFERENCES uploads(upload_id) ON DELETE CASCADE,
                offset INTEGER NOT NULL, data BLOB NOT NULL, PRIMARY KEY(upload_id, offset))""")
            db.execute("DELETE FROM uploads WHERE expires <= ?", (self.clock(),))
            # Commit expiry even when a subsequent caller operation is refused.
            db.execute("COMMIT")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.execute("COMMIT")
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    def _row(self, db, owner, identity, finalized=False):
        key = "file_id" if finalized else "upload_id"
        _identity(identity, "file_" if finalized else "")
        row = db.execute(f"SELECT * FROM uploads WHERE {key}=? AND owner=? AND expires>?",
                         (identity, owner, self.clock())).fetchone()
        if row is None:
            raise UploadError("not_found_or_expired")
        return row

    @staticmethod
    def _public(row):
        result = {k: row[k] for k in ("upload_id", "name", "expected_size", "received", "sha256", "expires")}
        result.update(state="finalized" if row["file_id"] else "uploading", chunk_bytes=CHUNK_BYTES,
                      max_chunks=MAX_CHUNKS)
        if row["file_id"]:
            result.update(file_id=row["file_id"], size=row["received"])
        return result

    def begin(self, owner, name, size, sha256, request_key):
        _filename(name); _integer(size); _digest(sha256); _identity(request_key)
        if size > self.limits.max_file_bytes:
            raise UploadError("file_size_limit")
        with self._transaction() as db:
            old = db.execute("SELECT * FROM uploads WHERE owner=? AND request_key=?",
                             (owner, request_key)).fetchone()
            if old:
                if (old["name"], old["expected_size"], old["sha256"]) != (name, size, sha256):
                    raise UploadError("request_key_conflict")
                return self._public(old)
            total = db.execute("SELECT COUNT(*), COALESCE(SUM(expected_size),0) FROM uploads").fetchone()
            own = db.execute("SELECT COUNT(*), COALESCE(SUM(expected_size),0) FROM uploads WHERE owner=?", (owner,)).fetchone()
            if (total[0] >= self.limits.total_uploads or own[0] >= self.limits.owner_uploads
                    or total[1] + size > self.limits.total_bytes or own[1] + size > self.limits.owner_bytes):
                raise UploadError("quota_exceeded")
            uid = secrets.token_hex(32)
            db.execute("INSERT INTO uploads(upload_id,owner,request_key,name,expected_size,sha256,expires) VALUES(?,?,?,?,?,?,?)",
                       (uid, owner, request_key, name, size, sha256, self.clock() + self.limits.ttl_seconds))
            return self._public(self._row(db, owner, uid))

    def append(self, owner, upload_id, offset, data, chunk_sha256):
        _integer(offset)
        raw = decode_chunk(data, chunk_sha256)
        with self._transaction() as db:
            row = self._row(db, owner, upload_id)
            # Exact retries remain safe after finalize (lost append/finish reply).
            previous = db.execute("SELECT data FROM chunks WHERE upload_id=? AND offset=?", (upload_id, offset)).fetchone()
            if previous:
                if bytes(previous[0]) != raw:
                    raise UploadError("chunk_conflict")
                return self._public(row)
            if row["file_id"]:
                raise UploadError("already_finalized")
            if offset != row["received"]:
                raise UploadError("offset_conflict")
            if offset + len(raw) > row["expected_size"]:
                raise UploadError("size_mismatch")
            if db.execute("SELECT COUNT(*) FROM chunks WHERE upload_id=?", (upload_id,)).fetchone()[0] >= MAX_CHUNKS:
                raise UploadError("chunk_count_limit")
            db.execute("INSERT INTO chunks VALUES(?,?,?)", (upload_id, offset, raw))
            db.execute("UPDATE uploads SET received=? WHERE upload_id=?", (offset + len(raw), upload_id))
            return self._public(self._row(db, owner, upload_id))

    @staticmethod
    def _verify(db, row):
        digest, position = hashlib.sha256(), 0
        for part in db.execute("SELECT offset,data FROM chunks WHERE upload_id=? ORDER BY offset", (row["upload_id"],)):
            if part["offset"] != position or not 0 < len(part["data"]) <= CHUNK_BYTES:
                raise UploadError("integrity_mismatch")
            digest.update(part["data"]); position += len(part["data"])
        if position != row["expected_size"] or position != row["received"]:
            raise UploadError("incomplete_upload")
        if digest.hexdigest() != row["sha256"]:
            raise UploadError("file_hash_mismatch")

    def finish(self, owner, upload_id):
        with self._transaction() as db:
            row = self._row(db, owner, upload_id)
            self._verify(db, row)
            if not row["file_id"]:
                db.execute("UPDATE uploads SET file_id=? WHERE upload_id=?", ("file_" + secrets.token_hex(32), upload_id))
            return self._public(self._row(db, owner, upload_id))

    def status(self, owner, upload_id):
        with self._transaction() as db:
            return self._public(self._row(db, owner, upload_id))

    def cancel(self, owner, upload_id):
        with self._transaction() as db:
            row = self._row(db, owner, upload_id)
            db.execute("DELETE FROM uploads WHERE upload_id=?", (row["upload_id"],))
            return {"deleted": True}  # no metadata/path disclosure

    def cleanup(self, owner):
        # Expiry is global but response never reveals another owner's records.
        with self._transaction() as db:
            return {"cleanup": "completed"}

    @contextmanager
    def verified_chunks(self, owner, file_id):
        """Internal downstream boundary, no tool accepting a server-local path.

        Revalidates before yielding a bounded iterator. Transaction stays open:
        consumers MUST NOT perform network calls here; copy to a separately
        authorized stream/spool in a future release-asset implementation.
        """
        with self._transaction() as db:
            row = self._row(db, owner, file_id, finalized=True)
            self._verify(db, row)
            yield (bytes(p[0]) for p in db.execute(
                "SELECT data FROM chunks WHERE upload_id=? ORDER BY offset", (row["upload_id"],)))
