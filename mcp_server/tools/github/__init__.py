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
from mcp_server.tools.github.workflows import get_workflow_logs_preview
from mcp_server.tools.github.workflow_runs import list_workflow_runs
from mcp_server.tools.github.workflow_runs import get_latest_run_id
from mcp_server.tools.github.workflow_runs import get_workflow_run_steps
from mcp_server.tools.github.workflow_runs import get_run_logs_by_step
from mcp_server.tools.github.workflow_runs import get_step_logs_via_checks
from mcp_server.tools.github.create_update_binary import create_or_update_binary_file
from mcp_server.tools.github.file_sha_ops import create_or_update_file_with_sha

# --- batch 1 additions ---
from mcp_server.tools.github.pull_requests import (
    create_pull_request,
    list_pull_requests,
    get_pull_request,
    merge_pull_request,
    close_pull_request,
    add_pr_comment,
    request_pr_review,
)
from mcp_server.tools.github.issues import (
    create_issue,
    list_issues,
    get_issue,
    close_issue,
    add_issue_comment,
    add_labels,
)
from mcp_server.tools.github.releases import (
    list_releases,
    create_release,
    get_latest_release,
)
from mcp_server.tools.github.tags import list_tags, create_tag
from mcp_server.tools.github.batch import push_multiple_files

__all__ = [
    "GitHubClient",
    # existing
    "get_file_contents",
    "create_or_update_file",
    "delete_file",
    "list_commits",
    "get_commit_status",
    "get_latest_workflow_error",
    "get_workflow_run_logs",
    "get_full_workflow_logs",
    "get_workflow_by_file",
    "get_workflow_logs_preview",
    "list_workflow_runs",
    "get_latest_run_id",
    "get_workflow_run_steps",
    "get_run_logs_by_step",
    "get_step_logs_via_checks",
    "create_or_update_binary_file",
    "create_or_update_file_with_sha",
    # batch 1
    "create_pull_request",
    "list_pull_requests",
    "get_pull_request",
    "merge_pull_request",
    "close_pull_request",
    "add_pr_comment",
    "request_pr_review",
    "create_issue",
    "list_issues",
    "get_issue",
    "close_issue",
    "add_issue_comment",
    "add_labels",
    "list_releases",
    "create_release",
    "get_latest_release",
    "list_tags",
    "create_tag",
    "push_multiple_files",
]
