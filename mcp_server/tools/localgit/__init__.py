"""MCP local git tools package.

Disabled by default. Registered only when ENABLE_LOCAL_TOOLS is truthy.
All repositories must live inside LOCAL_TOOLS_ROOT (env, defaults to
~/workspace). See SANDBOX.md for safe deployment.
"""

import os

_TRUTHY = {"1", "true", "yes", "on"}


def _enabled() -> bool:
    return (os.environ.get("ENABLE_LOCAL_TOOLS", "").strip().lower() in _TRUTHY)


if _enabled():
    from mcp_server.tools.localgit.git_ops import (
        git_status,
        git_log,
        git_diff,
        git_commit,
        git_push,
        git_pull,
    )

    __all__ = [
        "git_status",
        "git_log",
        "git_diff",
        "git_commit",
        "git_push",
        "git_pull",
    ]
else:
    __all__ = []
