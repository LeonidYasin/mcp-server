"""Synapse vector store: SQLite + numpy, item-model (batch 7b).

Stores items (offer | want) with their embeddings in a single SQLite
file under SYNAPSE_DATA_DIR. No external services: the whole store is one
file plus in-memory numpy matrices rebuilt on demand.

Item-model, not user-model: one user has many items, one embedding per
item. Matching is asymmetric (offer <-> want).

Freshness: items carry active/updated_at; stale items decay out instead
of accumulating forever.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

ITEM_TYPES = ("offer", "want")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    item_id       TEXT PRIMARY KEY,
    owner_id      TEXT NOT NULL,
    type          TEXT NOT NULL CHECK (type IN ('offer','want')),
    text          TEXT NOT NULL,
    category      TEXT,
    tags          TEXT NOT NULL DEFAULT '[]',
    geo           TEXT,
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    embedding     TEXT
);
CREATE INDEX IF NOT EXISTS idx_items_owner ON items(owner_id);
CREATE INDEX IF NOT EXISTS idx_items_type  ON items(type, active);

CREATE TABLE IF NOT EXISTS match_outcomes (
    match_id      TEXT PRIMARY KEY,
    item_a        TEXT NOT NULL,
    item_b        TEXT NOT NULL,
    outcome       TEXT NOT NULL,
    created_at    TEXT NOT NULL
);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def data_dir() -> str:
    """Directory for Synapse data. Created on demand."""
    raw = (os.environ.get("SYNAPSE_DATA_DIR", "") or "").strip()
    if not raw:
        raw = os.path.join(os.path.expanduser("~"), "workspace", "synapse")
    os.makedirs(raw, exist_ok=True)
    return raw


def db_path() -> str:
    return os.path.join(data_dir(), "synapse.sqlite3")


def freshness_days() -> int:
    raw = (os.environ.get("SYNAPSE_FRESHNESS_DAYS", "") or "").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 90


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


@dataclass
class Item:
    item_id: str
    owner_id: str
    type: str
    text: str
    category: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    geo: Optional[str] = None
    active: bool = True
    created_at: str = ""
    updated_at: str = ""
    embedding: Optional[List[float]] = None

    def to_dict(self, include_embedding: bool = False) -> dict:
        d = {
            "schema": "synapse/v0",
            "item_id": self.item_id,
            "type": self.type,
            "owner_id": self.owner_id,
            "text": self.text,
            "category": self.category,
            "tags": list(self.tags),
            "geo": self.geo,
            "active": self.active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if include_embedding and self.embedding is not None:
            d["embedding"] = self.embedding
        return d

    @staticmethod
    def from_row(row: sqlite3.Row) -> "Item":
        emb = row["embedding"]
        return Item(
            item_id=row["item_id"],
            owner_id=row["owner_id"],
            type=row["type"],
            text=row["text"],
            category=row["category"],
            tags=json.loads(row["tags"] or "[]"),
            geo=row["geo"],
            active=bool(row["active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            embedding=json.loads(emb) if emb else None,
        )


def new_item_id() -> str:
    return f"it_{uuid.uuid4().hex[:16]}"


def new_match_id() -> str:
    return f"m_{uuid.uuid4().hex[:16]}"


def add_item(
    owner_id: str,
    item_type: str,
    text: str,
    category: Optional[str] = None,
    tags: Optional[Sequence[str]] = None,
    geo: Optional[str] = None,
    embedding: Optional[List[float]] = None,
) -> Item:
    """Insert a new item. Returns the stored Item."""
    item_type = (item_type or "").strip().lower()
    if item_type not in ITEM_TYPES:
        raise ValueError(f"item type must be one of {ITEM_TYPES}, got {item_type!r}")
    if not (text or "").strip():
        raise ValueError("item text must not be empty")

    now = _now_iso()
    item = Item(
        item_id=new_item_id(),
        owner_id=owner_id,
        type=item_type,
        text=text.strip(),
        category=(category or None),
        tags=list(tags or []),
        geo=(geo or None),
        active=True,
        created_at=now,
        updated_at=now,
        embedding=embedding,
    )
    with _connect() as conn:
        conn.execute(
            "INSERT INTO items (item_id, owner_id, type, text, category, tags, geo, "
            "active, created_at, updated_at, embedding) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                item.item_id,
                item.owner_id,
                item.type,
                item.text,
                item.category,
                json.dumps(item.tags, ensure_ascii=False),
                item.geo,
                1 if item.active else 0,
                item.created_at,
                item.updated_at,
                json.dumps(item.embedding) if item.embedding is not None else None,
            ),
        )
    return item


def get_item(item_id: str) -> Optional[Item]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM items WHERE item_id = ?", (item_id,)).fetchone()
    return Item.from_row(row) if row else None


def list_items(owner_id: str, active_only: bool = False) -> List[Item]:
    sql = "SELECT * FROM items WHERE owner_id = ?"
    if active_only:
        sql += " AND active = 1"
    sql += " ORDER BY created_at DESC"
    with _connect() as conn:
        rows = conn.execute(sql, (owner_id,)).fetchall()
    return [Item.from_row(r) for r in rows]


def deactivate_item(item_id: str) -> bool:
    """Mark an item inactive (removed from matching). Returns True if found."""
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE items SET active = 0, updated_at = ? WHERE item_id = ?",
            (_now_iso(), item_id),
        )
    return cur.rowcount > 0


def set_embedding(item_id: str, embedding: List[float]) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE items SET embedding = ? WHERE item_id = ?",
            (json.dumps(embedding), item_id),
        )


def _age_days(updated_at: str) -> float:
    try:
        ts = datetime.strptime(updated_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return 0.0
    return (datetime.now(timezone.utc) - ts).total_seconds() / 86400.0


def freshness_factor(item: Item) -> float:
    """Linear decay: 1.0 fresh -> ~0.5 at the freshness horizon, floor 0.1."""
    horizon = freshness_days()
    age = _age_days(item.updated_at)
    if age <= 0:
        return 1.0
    if age >= horizon:
        return 0.1
    return max(0.1, 1.0 - 0.5 * (age / horizon))


def active_items(item_type: Optional[str] = None) -> List[Item]:
    """All active items of a given type (or both), for candidate search."""
    sql = "SELECT * FROM items WHERE active = 1"
    params: tuple = ()
    if item_type:
        sql += " AND type = ?"
        params = (item_type,)
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [Item.from_row(r) for r in rows]


def record_outcome(match_id: str, item_a: str, item_b: str, outcome: str) -> None:
    """Store the outcome of a match (behavioral ranking signal, Stage 2)."""
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO match_outcomes (match_id, item_a, item_b, outcome, created_at) "
            "VALUES (?,?,?,?,?)",
            (match_id, item_a, item_b, outcome, _now_iso()),
        )


def stats() -> dict:
    """Small status dict for diagnostics."""
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM items").fetchone()["c"]
        active = conn.execute("SELECT COUNT(*) AS c FROM items WHERE active = 1").fetchone()["c"]
        offers = conn.execute("SELECT COUNT(*) AS c FROM items WHERE type='offer' AND active=1").fetchone()["c"]
        wants = conn.execute("SELECT COUNT(*) AS c FROM items WHERE type='want' AND active=1").fetchone()["c"]
        with_emb = conn.execute("SELECT COUNT(*) AS c FROM items WHERE embedding IS NOT NULL").fetchone()["c"]
    return {
        "db": db_path(),
        "items_total": total,
        "items_active": active,
        "offers_active": offers,
        "wants_active": wants,
        "items_with_embedding": with_emb,
        "freshness_days": freshness_days(),
    }
