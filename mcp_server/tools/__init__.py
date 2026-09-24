"""MCP tools - auto-discovered by ToolRegistry.

The registry scans subpackages of this package via pkgutil.iter_modules.
Importing them here (or in each subpackage's __init__) makes them discoverable.
"""

# Subpackages with @mcp_tool-decorated functions in their __init__ chains.
from mcp_server.tools import github  # noqa: F401
from mcp_server.tools import meta  # noqa: F401
from mcp_server.tools import web  # noqa: F401
from mcp_server.tools import utils  # noqa: F401
