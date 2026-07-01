"""GitHub API tools - auto-discovered by ToolRegistry."""

from mcp_server.tools.github.client import GitHubClient
from mcp_server.tools.github import file_ops
from mcp_server.tools.github import commits
from mcp_server.tools.github import workflows

__all__ = ["GitHubClient", "file_ops", "commits", "workflows"]
