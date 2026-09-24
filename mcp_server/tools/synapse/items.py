"""Synapse item tools: submit_offer / submit_want / list_my_items / deactivate_item.

Batch 7b. Items are the unit of matching: an offer matches other people's
wants, and vice versa. Embeddings are attached when a provider is configured;
otherwise items are stored text-only and matching falls back to keywords.
"""

from __future__ import annotations

from mcp_server.core.registry import mcp_tool

from mcp_server.tools.synapse import embeddings, vector_store


def _attach_embedding(item):
    """Best-effort: embed the item and persist the vector. Never raises."""
    if not embeddings.is_enabled():
        return None, "embeddings disabled (SYNAPSE_EMBEDDING_PROVIDER not set)"
    try:
        vec = embeddings.embed_item(item.text, item.type)
        vector_store.set_embedding(item.item_id, vec)
        item.embedding = vec
        return vec, None
    except Exception as exc:  # provider down, missing key, missing lib, ...
        return None, f"embedding failed: {exc}"


def _submit(owner_id: str, item_type: str, text: str, category, tags, geo) -> str:
    if not (owner_id or "").strip():
        return "❌ owner_id обязателен (profile_id автора)"
    try:
        item = vector_store.add_item(
            owner_id=owner_id.strip(),
            item_type=item_type,
            text=text,
            category=category,
            tags=tags,
            geo=geo,
        )
    except ValueError as exc:
        return f"❌ {exc}"

    vec, warn = _attach_embedding(item)
    lines = [
        f"✅ {item.type} добавлен: {item.item_id}",
        f"   owner: {item.owner_id}",
        f"   text: {item.text}",
        f"   active: {item.active}",
    ]
    if item.category:
        lines.append(f"   category: {item.category}")
    if item.tags:
        lines.append(f"   tags: {', '.join(item.tags)}")
    if item.geo:
        lines.append(f"   geo: {item.geo}")
    lines.append(
        f"   embedding: {'yes (' + str(len(vec)) + ' dim)' if vec is not None else 'no'}"
    )
    if warn:
        lines.append(f"   note: {warn}")
    return "\n".join(lines)


@mcp_tool(
    name="submit_offer",
    description="Добавить offer (что я предлагаю). Единица матчинга в Synapse.",
    parameters={
        "owner_id": {"type": "string", "description": "profile_id автора"},
        "text": {"type": "string", "description": "Свободное описание, в словах автора"},
        "category": {"type": "string", "description": "Опциональная категория"},
        "tags": {"type": "array", "items": {"type": "string"}, "description": "Теги"},
        "geo": {"type": "string", "description": "География (город/регион)"},
    },
    required=["owner_id", "text"],
)
def submit_offer(**kwargs) -> str:
    return _submit(
        kwargs.get("owner_id", ""),
        "offer",
        kwargs.get("text", ""),
        kwargs.get("category"),
        kwargs.get("tags"),
        kwargs.get("geo"),
    )


@mcp_tool(
    name="submit_want",
    description="Добавить want (что я ищу). Единица матчинга в Synapse.",
    parameters={
        "owner_id": {"type": "string", "description": "profile_id автора"},
        "text": {"type": "string", "description": "Свободное описание, в словах автора"},
        "category": {"type": "string", "description": "Опциональная категория"},
        "tags": {"type": "array", "items": {"type": "string"}, "description": "Теги"},
        "geo": {"type": "string", "description": "География (город/регион)"},
    },
    required=["owner_id", "text"],
)
def submit_want(**kwargs) -> str:
    return _submit(
        kwargs.get("owner_id", ""),
        "want",
        kwargs.get("text", ""),
        kwargs.get("category"),
        kwargs.get("tags"),
        kwargs.get("geo"),
    )


@mcp_tool(
    name="list_my_items",
    description="Показать мои items (offer/want) с флагом active и наличием эмбеддинга.",
    parameters={
        "owner_id": {"type": "string", "description": "profile_id автора"},
        "active_only": {"type": "boolean", "description": "Только активные (по умолчанию true)"},
    },
    required=["owner_id"],
)
def list_my_items(**kwargs) -> str:
    owner_id = (kwargs.get("owner_id") or "").strip()
    if not owner_id:
        return "❌ owner_id обязателен"
    active_only = kwargs.get("active_only", True)
    if isinstance(active_only, str):
        active_only = active_only.strip().lower() in {"1", "true", "yes", "on"}

    items = vector_store.list_items(owner_id, active_only=bool(active_only))
    if not items:
        return f"У {owner_id} нет items"

    offers = sum(1 for i in items if i.type == "offer")
    wants = sum(1 for i in items if i.type == "want")
    lines = [f"{owner_id}: {len(items)} items (offer={offers}, want={wants})"]
    for it in items:
        flags = []
        if not it.active:
            flags.append("inactive")
        flags.append("emb" if it.embedding is not None else "no-emb")
        extra = f" [{', '.join(flags)}]"
        lines.append(f"  {it.type:5s} {it.item_id}  {it.text}{extra}")
    return "\n".join(lines)


@mcp_tool(
    name="deactivate_item",
    description="Вывести item из матчинга (исполнен, неактуален). Не удаляет запись.",
    parameters={
        "item_id": {"type": "string", "description": "ID item'а"},
    },
    required=["item_id"],
)
def deactivate_item(**kwargs) -> str:
    item_id = (kwargs.get("item_id") or "").strip()
    if not item_id:
        return "❌ item_id обязателен"
    ok = vector_store.deactivate_item(item_id)
    if not ok:
        return f"❌ item не найден: {item_id}"
    return f"✅ item выведен из матчинга: {item_id}"
