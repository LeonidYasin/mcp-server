"""GitHub API tools - auto-discovered by ToolRegistry."""

from mcp_server.tools.github.client import GitHubClient

# Import decorated functions so ToolRegistry can find them
from mcp_server.tools.github.file_ops import get_file_contents
from mcp_server.tools.github.file_ops import create_or_update_file
from mcp_server.tools.github.file_ops import delete_file
from mcp_server.tools.github.commits import list_commits
from mcp_server.tools.github.commits import get_commit_status
from mcp_server.tools.github.workflows import get_latest_workflow_error
from mcp_server.tools.github.workflows import get_workflow_run_logs
from mcp_server.tools.github.workflows import get_full_workflow_logs
from mcp_server.tools.github.workflows import get_workflow_by_file
from mcp_server.tools.github.create_update_binary import create_or_update_binary_file
from mcp_server.tools.github.file_sha_ops import create_or_update_file_with_sha

__all__ = [
    "GitHubClient",
    "get_file_contents",
    "create_or_update_file",
    "delete_file",
    "list_commits",
    "get_commit_status",
    "get_latest_workflow_error",
    "get_workflow_run_logs",
    "get_full_workflow_logs",
    "get_workflow_by_file",
    "create_or_update_binary_file",
    "create_or_update_file_with_sha",
]
