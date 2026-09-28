"""MCP process-manager tools package.

Disabled by default — same gate as the shell tools (ENABLE_LOCAL_SHELL),
because starting/stopping background processes is the same danger class
as running arbitrary commands (in fact a superset: a backgrounded process
keeps running after the tool call returns). See SANDBOX.md.

All processes are started detached (new session) so they survive the
individual MCP request, but they still run as whatever OS user runs this
server — no additional privilege boundary is added here.
"""

import os

_TRUTHY = {"1", "true", "yes", "on"}


def _enabled() -> bool:
    return os.environ.get("ENABLE_LOCAL_SHELL", "").strip().lower() in _TRUTHY


if _enabled():
    from mcp_server.tools.process.process_ops import (  # noqa: F401
        start_background,
        stop_process,
        process_status,
        tail_log,
    )

    __all__ = [
        "start_background",
        "stop_process",
        "process_status",
        "tail_log",
    ]
else:
    __all__ = []
