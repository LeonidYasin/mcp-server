"""SQLite room core. No HTTP, models, credentials, background tasks or global connection."""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import time
import unicodedata
import uuid


class RoomError(Exception):
    def __init__(self, code, **details):
        super().__init__(code)
        self.code, self.details = code, details


@dataclass(frozen=True)
class Limits:
    rooms: int = 100
    rooms_per_owner: int = 5
    principals: int = 1000
    memberships_per_owner: int = 20
    members_per_room: int = 100
    messages: int = 20000
    messages_per_room: int = 1000
    text: int = 500
    cadence_ms: int = 10000
    ttl_ms: int = 86400000


def _text(value, maximum):
    if not isinstance(value, str):
        raise RoomError('invalid_text')
    value = unicodedata.normalize('NFC', value).strip()
    if not value or len(value) > maximum or any(unicodedata.category(c) == 'Cc' and c not in '\n\t' for c in value):
        raise RoomError('invalid_text')
    return value


def _id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', value):
        raise RoomError('invalid_id')
    return value


def _limit(value):
    if type(value) is not int or not 1 <= value <= 100:
        raise RoomError('invalid_limit')
    return value


def _cursor(value, scope):
    if value is None:
        return 0
    if not isinstance(value, str) or len(value) > 80 or not value.startswith(scope + ':'):
        raise RoomError('invalid_cursor')
    sequence = value[len(scope) + 1:]
    if not re.fullmatch(r'0|[1-9][0-9]{0,18}', sequence) or int(sequence) > 9223372036854775807:
        raise RoomError('invalid_cursor')
    return int(sequence)


class RoomStore:
    def __init__(self, path, clock=None, limits=Limits()):
        self.path = Path(path)
        self.clock = clock or (lambda: int(time.time() * 1000))
        self.limits = limits
        if not self.path.is_absolute() or not self.path.parent.is_dir() or self.path.is_symlink():
            raise RoomError('invalid_database_path')
        # Admin-controlled, private directory required. Never accept a path from tool arguments.
        flags = os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
        fd = os.open(self.path, flags, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise RoomError('invalid_database_path')
            os.fchmod(fd, 0o600)
        finally:
            os.close(fd)
        with self._db(write=True, initialize=True) as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0, 1):
                raise RoomError('unsupported_database_version')
            for statement in (
                'CREATE TABLE IF NOT EXISTS actors (owner TEXT PRIMARY KEY, last_send INTEGER)',
                'CREATE TABLE IF NOT EXISTS rooms (seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, owner TEXT NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL, created_at INTEGER NOT NULL)',
                'CREATE TABLE IF NOT EXISTS members (room_id TEXT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE, owner TEXT NOT NULL, PRIMARY KEY(room_id, owner))',
                'CREATE INDEX IF NOT EXISTS members_owner ON members(owner)',
                'CREATE TABLE IF NOT EXISTS messages (seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, room_id TEXT NOT NULL REFERENCES rooms(id) ON DELETE CASCADE, owner TEXT NOT NULL, text TEXT NOT NULL, digest TEXT NOT NULL, client_id TEXT NOT NULL, reply_to TEXT, deleted INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL, UNIQUE(room_id, owner, client_id))',
                'CREATE INDEX IF NOT EXISTS messages_room_seq ON messages(room_id, seq)',
                'CREATE INDEX IF NOT EXISTS messages_expiry ON messages(expires_at)',
            ):
                db.execute(statement)
            db.execute('PRAGMA user_version=1')

    @contextmanager
    def _db(self, write=False, initialize=False):
        db = sqlite3.connect(str(self.path), timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA busy_timeout=5000')
            if initialize:
                db.execute('PRAGMA journal_mode=WAL')
            db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _actor(self, db, owner):
        if not isinstance(owner, str) or not re.fullmatch(r'github:[1-9][0-9]{0,19}', owner):
            raise RoomError('invalid_principal')
        if not db.execute('SELECT 1 FROM actors WHERE owner=?', (owner,)).fetchone():
            if db.execute('SELECT COUNT(*) FROM actors').fetchone()[0] >= self.limits.principals:
                raise RoomError('principal_capacity')
            db.execute('INSERT INTO actors(owner) VALUES (?)', (owner,))

    def _room(self, db, room_id):
        row = db.execute('SELECT * FROM rooms WHERE id=?', (_id(room_id),)).fetchone()
        if not row:
            raise RoomError('room_unavailable')
        return row

    def _member(self, db, room_id, owner):
        self._room(db, room_id)
        if not db.execute('SELECT 1 FROM members WHERE room_id=? AND owner=?', (room_id, owner)).fetchone():
            raise RoomError('membership_required')

    @staticmethod
    def _message(row):
        return {k: row[k] for k in ('id', 'room_id', 'owner', 'text', 'reply_to', 'deleted', 'created_at', 'expires_at')}

    def create(self, owner, title, description=''):
        title = _text(title, 80)
        description = _text(description, 300) if description != '' else ''
        room_id, now = str(uuid.uuid4()), self.clock()
        with self._db(write=True) as db:
            self._actor(db, owner)
            if db.execute('SELECT COUNT(*) FROM rooms').fetchone()[0] >= self.limits.rooms:
                raise RoomError('room_capacity')
            if db.execute('SELECT COUNT(*) FROM rooms WHERE owner=?', (owner,)).fetchone()[0] >= self.limits.rooms_per_owner:
                raise RoomError('owner_room_capacity')
            self._join_capacity(db, owner)
            db.execute('INSERT INTO rooms(id,owner,title,description,created_at) VALUES (?,?,?,?,?)', (room_id, owner, title, description, now))
            db.execute('INSERT INTO members VALUES (?,?)', (room_id, owner))
        return {'room_id': room_id, 'owner': owner, 'title': title, 'visibility': 'public_to_allowlist'}

    def list(self, owner, cursor=None, limit=20):
        after, limit = _cursor(cursor, 'rooms'), _limit(limit)
        with self._db() as db:
            rows = db.execute('SELECT r.*, EXISTS(SELECT 1 FROM members m WHERE m.room_id=r.id AND m.owner=?) AS joined FROM rooms r WHERE r.seq>? ORDER BY r.seq LIMIT ?', (owner, after, limit + 1)).fetchall()
        selected = rows[:limit]
        return {'rooms': [{k: row[k] for k in ('id', 'owner', 'title', 'description', 'created_at', 'joined')} for row in selected],
                'next_cursor': 'rooms:' + str(selected[-1]['seq'] if selected else after), 'has_more': len(rows) > limit}

    def _join_capacity(self, db, owner):
        if db.execute('SELECT COUNT(*) FROM members WHERE owner=?', (owner,)).fetchone()[0] >= self.limits.memberships_per_owner:
            raise RoomError('membership_capacity')

    def join(self, owner, room_id):
        with self._db(write=True) as db:
            self._room(db, room_id)
            if db.execute('SELECT 1 FROM members WHERE room_id=? AND owner=?', (room_id, owner)).fetchone():
                return {'joined': True, 'already_joined': True}
            self._actor(db, owner)
            self._join_capacity(db, owner)
            if db.execute('SELECT COUNT(*) FROM members WHERE room_id=?', (room_id,)).fetchone()[0] >= self.limits.members_per_room:
                raise RoomError('room_member_capacity')
            db.execute('INSERT INTO members VALUES (?,?)', (room_id, owner))
        return {'joined': True, 'already_joined': False}

    def leave(self, owner, room_id):
        with self._db(write=True) as db:
            if self._room(db, room_id)['owner'] == owner:
                raise RoomError('owner_must_close_room')
            db.execute('DELETE FROM members WHERE room_id=? AND owner=?', (room_id, owner))
        return {'left': True}

    def close(self, owner, room_id):
        with self._db(write=True) as db:
            if self._room(db, room_id)['owner'] != owner:
                raise RoomError('not_room_owner')
            db.execute('DELETE FROM rooms WHERE id=?', (room_id,))
        return {'closed': True, 'history_deleted': True}

    def send(self, owner, room_id, text, client_message_id, reply_to=None):
        text = _text(text, self.limits.text)
        if not isinstance(client_message_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', client_message_id):
            raise RoomError('invalid_client_message_id')
        if reply_to is not None:
            _id(reply_to)
        digest = hashlib.sha256(json.dumps([text, reply_to], ensure_ascii=False).encode()).hexdigest()
        now = self.clock()
        with self._db(write=True) as db:
            self._member(db, room_id, owner)
            db.execute('DELETE FROM messages WHERE expires_at<=?', (now,))
            old = db.execute('SELECT * FROM messages WHERE room_id=? AND owner=? AND client_id=?', (room_id, owner, client_message_id)).fetchone()
            if old:
                if old['digest'] != digest:
                    raise RoomError('idempotency_conflict')
                return {'message': self._message(old), 'replayed': True}
            if reply_to and not db.execute('SELECT 1 FROM messages WHERE id=? AND room_id=? AND deleted=0', (reply_to, room_id)).fetchone():
                raise RoomError('reply_unavailable')
            last = db.execute('SELECT last_send FROM actors WHERE owner=?', (owner,)).fetchone()
            if not last:
                raise RoomError('invalid_principal')
            if last[0] is not None and now - last[0] < self.limits.cadence_ms:
                raise RoomError('rate_limited', retry_after_ms=self.limits.cadence_ms - (now - last[0]))
            if db.execute('SELECT COUNT(*) FROM messages').fetchone()[0] >= self.limits.messages:
                raise RoomError('message_capacity')
            if db.execute('SELECT COUNT(*) FROM messages WHERE room_id=?', (room_id,)).fetchone()[0] >= self.limits.messages_per_room:
                raise RoomError('room_message_capacity')
            message_id = str(uuid.uuid4())
            db.execute('INSERT INTO messages(id,room_id,owner,text,digest,client_id,reply_to,created_at,expires_at) VALUES (?,?,?,?,?,?,?,?,?)',
                       (message_id, room_id, owner, text, digest, client_message_id, reply_to, now, now + self.limits.ttl_ms))
            db.execute('UPDATE actors SET last_send=? WHERE owner=?', (now, owner))
            row = db.execute('SELECT * FROM messages WHERE id=?', (message_id,)).fetchone()
        return {'message': self._message(row), 'replayed': False}

    def read(self, owner, room_id, cursor=None, limit=20):
        _id(room_id)
        after, limit, now = _cursor(cursor, room_id), _limit(limit), self.clock()
        with self._db() as db:
            self._member(db, room_id, owner)
            rows = db.execute('SELECT * FROM messages WHERE room_id=? AND seq>? AND expires_at>? ORDER BY seq LIMIT ?', (room_id, after, now, limit + 1)).fetchall()
        selected = rows[:limit]
        return {'messages': [self._message(row) for row in selected],
                'next_cursor': room_id + ':' + str(selected[-1]['seq'] if selected else after),
                'has_more': len(rows) > limit, 'history_complete': False, 'retention': 'active_window_only',
                'ttl_ms': self.limits.ttl_ms, 'durable': True, 'untrusted_content': True}

    def delete_message(self, owner, room_id, message_id):
        _id(message_id)
        with self._db(write=True) as db:
            self._member(db, room_id, owner)
            row = db.execute('SELECT * FROM messages WHERE room_id=? AND id=? AND owner=? AND expires_at>?', (room_id, message_id, owner, self.clock())).fetchone()
            if not row:
                raise RoomError('message_unavailable_or_not_yours')
            db.execute("UPDATE messages SET text='', deleted=1 WHERE id=?", (message_id,))
        return {'deleted': True, 'tombstone': True}
