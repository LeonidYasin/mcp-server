"""MCP Synapse tools package.

Disabled by default. Registered only when ENABLE_SYNAPSE is truthy.

Synapse is the people-findability layer: a portable JSON profile,
mutual-consent contact requests, and semantic search over profiles and
personal notes.

Batch 7a — protocol skeleton WITHOUT embeddings:
  publish_profile, search_people, propose_contact, save_note, search_notes,
  index_github.

Batch 7b — item-model + embeddings (this branch):
  submit_offer, submit_want, list_my_items, deactivate_item  (items.py)
  model_me, find_my_match, draft_profile_from_dialog, report_match_outcome
  (matching.py)

Embedding provider is selected via SYNAPSE_EMBEDDING_PROVIDER
(openai | local | ollama). When unset, matching falls back to keyword
scoring (honestly labelled in tool output).

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
    from mcp_server.tools.synapse.items import (  # noqa: F401
        submit_offer,
        submit_want,
        list_my_items,
        deactivate_item,
    )
    from mcp_server.tools.synapse.matching import (  # noqa: F401
        model_me,
        find_my_match,
        draft_profile_from_dialog,
        report_match_outcome,
    )

    __all__ = [
        # batch 7a
        "publish_profile",
        "search_people",
        "propose_contact",
        "save_note",
        "search_notes",
        "index_github",
        # batch 7b — items
        "submit_offer",
        "submit_want",
        "list_my_items",
        "deactivate_item",
        # batch 7b — matching
        "model_me",
        "find_my_match",
        "draft_profile_from_dialog",
        "report_match_outcome",
    ]
else:
    __all__ = []
