"""Build tools for Android and iOS."""

# Import decorated functions so ToolRegistry can find them
from mcp_server.tools.build.build_logs import get_android_build_error
from mcp_server.tools.build.build_logs import get_ios_build_error
from mcp_server.tools.build.build_watch import watch_build
from mcp_server.tools.build.build_watch import auto_fix_build

__all__ = [
    "get_android_build_error",
    "get_ios_build_error",
    "watch_build",
    "auto_fix_build",
]
