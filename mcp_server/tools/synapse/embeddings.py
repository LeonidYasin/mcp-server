"""Synapse embeddings: provider abstraction (batch 7b).

Three providers, selected by SYNAPSE_EMBEDDING_PROVIDER:
  - openai : text-embedding-3-small (1536 dim), needs OPENAI_API_KEY
  - local  : sentence-transformers (384 dim), downloaded once
  - ollama : nomic-embed-text (768 dim), local server on OLLAMA_BASE_URL

If no provider is configured, embeddings are unavailable and callers fall
back to keyword scoring (see synapse_ops.search_people).

Instruction-aware: offers and wants are embedded with different role
prefixes so that crossed matching (offer <-> want) improves.
"""

from __future__ import annotations

import os
from typing import List, Optional

_TRUTHY = {"1", "true", "yes", "on"}

PROVIDER_OPENAI = "openai"
PROVIDER_LOCAL = "local"
PROVIDER_OLLAMA = "ollama"

# Role prefixes prepended to item text before embedding.
ROLE_PREFIX = {"offer": "offer: ", "want": "want: "}

# Known model dimensions (fallback when provider does not report it).
_DIMS = {
    "text-embedding-3-small": 1536,
    "all-MiniLM-L6-v2": 384,
    "bge-small-en": 384,
    "nomic-embed-text": 768,
}


def provider_name() -> Optional[str]:
    """Return configured provider name, or None if embeddings disabled."""
    raw = (os.environ.get("SYNAPSE_EMBEDDING_PROVIDER", "") or "").strip().lower()
    if raw in (PROVIDER_OPENAI, PROVIDER_LOCAL, PROVIDER_OLLAMA):
        return raw
    return None


def is_enabled() -> bool:
    """True when a real embedding provider is configured."""
    return provider_name() is not None


def model_name() -> str:
    """Configured model name, with a per-provider default."""
    explicit = (os.environ.get("SYNAPSE_EMBEDDING_MODEL", "") or "").strip()
    if explicit:
        return explicit
    prov = provider_name()
    if prov == PROVIDER_OPENAI:
        return "text-embedding-3-small"
    if prov == PROVIDER_LOCAL:
        return "all-MiniLM-L6-v2"
    if prov == PROVIDER_OLLAMA:
        return "nomic-embed-text"
    return ""


def expected_dim() -> Optional[int]:
    """Best-effort dimension for the configured model."""
    return _DIMS.get(model_name())


def apply_role_prefix(text: str, item_type: str) -> str:
    """Prepend the offer/want role prefix (instruction-aware embedding)."""
    prefix = ROLE_PREFIX.get((item_type or "").strip().lower(), "")
    return f"{prefix}{text}"


def _embed_openai(texts: List[str]) -> List[List[float]]:
    import httpx

    api_key = (os.environ.get("OPENAI_API_KEY", "") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    base = (os.environ.get("OPENAI_BASE_URL", "") or "https://api.openai.com/v1").rstrip("/")
    resp = httpx.post(
        f"{base}/embeddings",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": model_name(), "input": texts},
        timeout=60.0,
    )
    resp.raise_for_status()
    data = resp.json().get("data", [])
    data.sort(key=lambda d: d.get("index", 0))
    return [d["embedding"] for d in data]


_ST_MODEL = None


def _embed_local(texts: List[str]) -> List[List[float]]:
    global _ST_MODEL
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "sentence-transformers is not installed; run `pip install sentence-transformers`"
        ) from exc
    if _ST_MODEL is None:
        _ST_MODEL = SentenceTransformer(model_name())
    vectors = _ST_MODEL.encode(texts, normalize_embeddings=True)
    return [list(map(float, v)) for v in vectors]


def _embed_ollama(texts: List[str]) -> List[List[float]]:
    import httpx

    base = (os.environ.get("OLLAMA_BASE_URL", "") or "http://localhost:11434").rstrip("/")
    out: List[List[float]] = []
    for text in texts:
        resp = httpx.post(
            f"{base}/api/embeddings",
            json={"model": model_name(), "prompt": text},
            timeout=60.0,
        )
        resp.raise_for_status()
        out.append(list(map(float, resp.json().get("embedding", []))))
    return out


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a batch of raw texts using the configured provider.

    Raises RuntimeError when no provider is configured or the provider fails.
    Callers should catch this and fall back to keyword scoring.
    """
    if not texts:
        return []
    prov = provider_name()
    if prov == PROVIDER_OPENAI:
        return _embed_openai(texts)
    if prov == PROVIDER_LOCAL:
        return _embed_local(texts)
    if prov == PROVIDER_OLLAMA:
        return _embed_ollama(texts)
    raise RuntimeError("no SYNAPSE_EMBEDDING_PROVIDER configured")


def embed_item(text: str, item_type: str) -> List[float]:
    """Embed a single item with its role prefix applied."""
    return embed_texts([apply_role_prefix(text, item_type)])[0]


def describe() -> dict:
    """Small status dict, useful for tools/diagnostics."""
    prov = provider_name()
    return {
        "enabled": prov is not None,
        "provider": prov,
        "model": model_name(),
        "dim": expected_dim(),
        "role_prefixes": ROLE_PREFIX,
    }
