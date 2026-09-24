"""MCP shell tools package.

Disabled by default. Registered only when ENABLE_LOCAL_SHELL is truthy.
All commands run with cwd inside LOCAL_TOOLS_ROOT (env, defaults to
~/workspace). See SANDBOX.md for safe deployment.

This is the most dangerous tool category: never enable it outside an
isolated sandbox (separate Linux user, WSL2 without automount, bwrap or
Docker). See SANDBOX.md for isolation levels.
"""

import os

_TRUTHY = {"1", "true", "yes", "on"}


def _enabled() -> bool:
    return (os.environ.get("ENABLE_LOCAL_SHELL", "").strip().lower() in _TRUTHY)


if _enabled():
    from mcp_server.tools.shell.shell_ops import (  # noqa: F401
        run_command,
        run_python,
    )

    __all__ = [
        "run_command",
        "run_python",
    ]
else:
    __all__ = []
