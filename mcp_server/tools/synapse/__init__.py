"""MCP Synapse tools package.

Disabled by default. Registered only when ENABLE_SYNAPSE is truthy.

Synapse is the people-findability layer: a portable JSON profile,
mutual-consent contact requests, and semantic search over profiles and
personal notes.

This is batch 7a — the protocol skeleton WITHOUT embeddings.
`search_people` / `search_notes` do keyword scoring, honestly labelled as
MVP. Batch 7b adds real embeddings (`model_me`, `find_my_match`).

Data lives in SYNAPSE_DATA_DIR (env, defaults to ~/workspace/synapse).
"""

import os

_TRUTHY = {"1", "true", "yes", "on"}


def _enabled() -> bool:
    return (os.environ.get("ENABLE_SYNAPSE", "").strip().lower() in _TRUTHY)


if _enabled():
    from mcp_server.tools.synapse.synapse_ops import (  # noqa: F401
        publish_profile,
        search_people,
        propose_contact,
        save_note,
        search_notes,
        index_github,
    )

    __all__ = [
        "publish_profile",
        "search_people",
        "propose_contact",
        "save_note",
        "search_notes",
        "index_github",
    ]
else:
    __all__ = []
