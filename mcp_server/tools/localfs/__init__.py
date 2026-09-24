"""MCP local filesystem tools package.

These tools are DISABLED by default. They are only registered when the
environment variable ENABLE_LOCAL_TOOLS is truthy ("1", "true", "yes", "on").

All paths are restricted to LOCAL_TOOLS_ROOT (env var, defaults to
~/workspace). Paths outside the root are refused.

See SANDBOX.md for safe deployment instructions (Linux + WSL2).
"""

import os

_TRUTHY = {"1", "true", "yes", "on"}


def _enabled() -> bool:
    return (os.environ.get("ENABLE_LOCAL_TOOLS", "").strip().lower() in _TRUTHY)


if _enabled():
    from mcp_server.tools.localfs.files import (
        read_local_file,
        write_local_file,
        list_local_dir,
        search_in_files,
    )

    __all__ = [
        "read_local_file",
        "write_local_file",
        "list_local_dir",
        "search_in_files",
    ]
else:
    __all__ = []
