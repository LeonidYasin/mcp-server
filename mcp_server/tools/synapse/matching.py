"""Synapse matching tools (batch 7b): model_me, find_my_match,
draft_profile_from_dialog, report_match_outcome.

Matching is asymmetric: an offer is compared against other people's wants
(and vice versa). Candidates come from cosine similarity when embeddings are
available; otherwise we fall back to keyword overlap, honestly labelled as
such in the output.

Hybrid filter: category / tags / geo / active / freshness applied before the
final score is reported.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from mcp_server.core.registry import mcp_tool

from mcp_server.tools.synapse import embeddings, vector_store


def _tokenize(text: str) -> set:
    return {t for t in re.findall(r"[\w\-]+", (text or "").lower()) if len(t) > 2}


def _keyword_score(a: str, b: str) -> float:
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (na * nb)))


def _passes_filters(src: vector_store.Item, cand: vector_store.Item) -> bool:
    """Structured filters applied before scoring."""
    if src.category and cand.category and src.category != cand.category:
        return False
    if src.geo and cand.geo and src.geo != cand.geo:
        return False
    if src.tags and cand.tags:
        if not (set(src.tags) & set(cand.tags)):
            return False
    return True


def _match_pairs(src: vector_store.Item) -> List[vector_store.Item]:
    """Asymmetric: offer -> others' wants, want -> others' offers."""
    opposite = "want" if src.type == "offer" else "offer"
    candidates = vector_store.active_items(opposite)
    return [c for c in candidates if c.owner_id != src.owner_id and _passes_filters(src, c)]


@mcp_tool(
    name="model_me",
    description="Построить эмбеддинг-слепок из описания и сохранить его как item.",
    parameters={
        "owner_id": {"type": "string", "description": "profile_id автора"},
        "text": {"type": "string", "description": "Описание: кто я, что предлагаю"},
        "item_type": {"type": "string", "description": "offer (по умолчанию) или want"},
        "category": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "geo": {"type": "string"},
    },
    required=["owner_id", "text"],
)
def model_me(**kwargs) -> str:
    owner_id = (kwargs.get("owner_id") or "").strip()
    text = (kwargs.get("text") or "").strip()
    item_type = (kwargs.get("item_type") or "offer").strip().lower()
    if not owner_id or not text:
        return "❌ owner_id и text обязательны"
    if item_type not in vector_store.ITEM_TYPES:
        return f"❌ item_type должен быть offer или want, получено {item_type!r}"

    try:
        item = vector_store.add_item(
            owner_id=owner_id,
            item_type=item_type,
            text=text,
            category=kwargs.get("category"),
            tags=kwargs.get("tags"),
            geo=kwargs.get("geo"),
        )
    except ValueError as exc:
        return f"❌ {exc}"

    note = None
    if embeddings.is_enabled():
        try:
            vec = embeddings.embed_item(item.text, item.type)
            vector_store.set_embedding(item.item_id, vec)
        except Exception as exc:
            note = f"embedding failed: {exc}"
    else:
        note = "embeddings disabled — сохранён text-only (keyword-матчинг)"

    lines = [
        f"✅ profile snapshot сохранён как item: {item.item_id}",
        f"   type: {item.type}",
        f"   provider: {embeddings.provider_name() or 'none (keyword fallback)'}",
    ]
    if note:
        lines.append(f"   note: {note}")
    return "\n".join(lines)


@mcp_tool(
    name="find_my_match",
    description="Найти асимметричные матчи для моего item (offer ↔ want), hybrid: vector + фильтры + freshness.",
    parameters={
        "item_id": {"type": "string", "description": "Мой item (offer или want)"},
        "limit": {"type": "integer", "description": "Сколько результатов (по умолчанию 10)"},
        "min_score": {"type": "number", "description": "Минимальный скор 0..1 (по умолчанию 0.1)"},
    },
    required=["item_id"],
)
def find_my_match(**kwargs) -> str:
    item_id = (kwargs.get("item_id") or "").strip()
    if not item_id:
        return "❌ item_id обязателен"
    src = vector_store.get_item(item_id)
    if not src:
        return f"❌ item не найден: {item_id}"
    if not src.active:
        return f"❌ item неактивен: {item_id}"

    try:
        limit = int(kwargs.get("limit", 10))
    except (TypeError, ValueError):
        limit = 10
    try:
        min_score = float(kwargs.get("min_score", 0.1))
    except (TypeError, ValueError):
        min_score = 0.1

    candidates = _match_pairs(src)
    if not candidates:
        return f"Матчей не найдено для {item_id} ({src.type})"

    use_vec = embeddings.is_enabled() and src.embedding is not None
    if use_vec and any(c.embedding is None for c in candidates):
        for c in candidates:
            if c.embedding is None:
                try:
                    vec = embeddings.embed_item(c.text, c.type)
                    vector_store.set_embedding(c.item_id, vec)
                    c.embedding = vec
                except Exception:
                    pass

    scored: List[Tuple[float, vector_store.Item, str]] = []
    for cand in candidates:
        if use_vec and cand.embedding is not None:
            base = _cosine(src.embedding, cand.embedding)
            source = "embedding"
        else:
            base = _keyword_score(src.text, cand.text)
            source = "keyword"
        score = base * vector_store.freshness_factor(cand)
        if score >= min_score:
            scored.append((score, cand, source))

    if not scored:
        return f"Матчей выше порога {min_score} нет для {item_id}"

    scored.sort(key=lambda t: t[0], reverse=True)
    scored = scored[: max(1, limit)]

    mode = "embedding" if use_vec else "keyword (MVP fallback)"
    lines = [f"Матчи для {item_id} ({src.type}) — режим: {mode}, найдено {len(scored)}:"]
    for score, cand, source in scored:
        lines.append(
            f"  {score:.3f}  {cand.item_id}  {cand.type} by {cand.owner_id}  "
            f"[{source}]  {cand.text}"
        )
    return "\n".join(lines)


@mcp_tool(
    name="draft_profile_from_dialog",
    description="Собрать черновик profile+items из свободного текста/диалога (эвристика, без LLM-вызовов).",
    parameters={
        "owner_id": {"type": "string", "description": "profile_id автора"},
        "dialog": {"type": "string", "description": "Свободный текст или диалог"},
        "save": {"type": "boolean", "description": "Сохранить items в стор (по умолчанию false)"},
    },
    required=["owner_id", "dialog"],
)
def draft_profile_from_dialog(**kwargs) -> str:
    owner_id = (kwargs.get("owner_id") or "").strip()
    dialog = (kwargs.get("dialog") or "").strip()
    if not owner_id or not dialog:
        return "❌ owner_id и dialog обязательны"

    save = kwargs.get("save", False)
    if isinstance(save, str):
        save = save.strip().lower() in {"1", "true", "yes", "on"}

    # Heuristic split: lines starting with want-markers -> want, otherwise offer.
    want_markers = ("ищу", "нужно", "нужен", "хочу найти", "looking for", "need", "want")
    offer_markers = ("предлагаю", "могу", "умею", "offer", "i can", "i offer")

    offers: List[str] = []
    wants: List[str] = []
    for raw in re.split(r"[\n\.;]+", dialog):
        line = raw.strip()
        if len(line) < 8:
            continue
        low = line.lower()
        if any(m in low for m in want_markers):
            wants.append(line)
        elif any(m in low for m in offer_markers):
            offers.append(line)
        else:
            offers.append(line)

    lines = [f"Черновик профиля {owner_id}:", f"  offers: {len(offers)}", f"  wants: {len(wants)}"]
    for t in offers:
        lines.append(f"    + offer: {t}")
    for t in wants:
        lines.append(f"    + want:  {t}")

    if save:
        saved = []
        for t in offers:
            it = vector_store.add_item(owner_id, "offer", t)
            saved.append(it.item_id)
            if embeddings.is_enabled():
                try:
                    vector_store.set_embedding(it.item_id, embeddings.embed_item(it.text, it.type))
                except Exception:
                    pass
        for t in wants:
            it = vector_store.add_item(owner_id, "want", t)
            saved.append(it.item_id)
            if embeddings.is_enabled():
                try:
                    vector_store.set_embedding(it.item_id, embeddings.embed_item(it.text, it.type))
                except Exception:
                    pass
        lines.append(f"  saved items: {len(saved)}")
        lines.append(f"  item_ids: {', '.join(saved)}")
    else:
        lines.append("  (dry-run; передай save=true, чтобы сохранить items)")
    return "\n".join(lines)


@mcp_tool(
    name="report_match_outcome",
    description="Зафиксировать исход матча (unknown/accepted/rejected/exchanged) — задел под behavioral ranking.",
    parameters={
        "match_id": {"type": "string", "description": "ID матча"},
        "item_a": {"type": "string", "description": "offer item_id"},
        "item_b": {"type": "string", "description": "want item_id"},
        "outcome": {"type": "string", "description": "unknown|accepted|rejected|exchanged"},
    },
    required=["match_id", "item_a", "item_b", "outcome"],
)
def report_match_outcome(**kwargs) -> str:
    match_id = (kwargs.get("match_id") or "").strip()
    item_a = (kwargs.get("item_a") or "").strip()
    item_b = (kwargs.get("item_b") or "").strip()
    outcome = (kwargs.get("outcome") or "").strip().lower()
    allowed = {"unknown", "accepted", "rejected", "exchanged"}
    if not match_id or not item_a or not item_b:
        return "❌ match_id, item_a, item_b обязательны"
    if outcome not in allowed:
        return f"❌ outcome должен быть одним из {sorted(allowed)}"
    vector_store.record_outcome(match_id, item_a, item_b, outcome)
    return f"✅ outcome записан: {match_id} -> {outcome}"
