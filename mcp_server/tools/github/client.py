"""GitHub API client for MCP server."""

import json
import os
from typing import Any, Dict, List, Optional

import requests


class GitHubClient:
    """Client for GitHub API."""

    def __init__(self, token: Optional[str] = None):
        """Initialize GitHub client.

        Args:
            token: GitHub personal access token. If not provided, will try to read
                  from GITHUB_TOKEN environment variable.
        """
        self.token = token or os.environ.get("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("GitHub token is required. Set GITHUB_TOKEN environment variable.")
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def _make_request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make a request to GitHub API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, PATCH)
            path: API path (will be appended to base_url)
            params: Query parameters
            data: Request body

        Returns:
            JSON response or None for 204 responses

        Raises:
            Exception: If API returns error status
        """
        url = f"{self.base_url}{path}"
        response = self.session.request(
            method=method,
            url=url,
            params=params,
            json=data,
            timeout=30,
        )

        if response.status_code >= 400:
            error_msg = f"HTTP error {response.status_code}: {response.text}"
            raise Exception(error_msg)

        if response.status_code == 204:
            return None

        return response.json()

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Make GET request."""
        return self._make_request("GET", path, params)

    def post(self, path: str, data: Optional[Dict[str, Any]] = None) -> Any:
        """Make POST request."""
        return self._make_request("POST", path, data=data)

    def put(self, path: str, data: Optional[Dict[str, Any]] = None) -> Any:
        """Make PUT request."""
        return self._make_request("PUT", path, data=data)

    def patch(self, path: str, data: Optional[Dict[str, Any]] = None) -> Any:
        """Make PATCH request."""
        return self._make_request("PATCH", path, data=data)

    def delete(self, path: str) -> Any:
        """Make DELETE request."""
        return self._make_request("DELETE", path)

    def get_paginated(self, path: str, params: Optional[Dict[str, Any]] = None) -> List[Any]:
        """Make paginated GET request.

        Args:
            path: API path
            params: Query parameters

        Returns:
            List of all items from paginated results
        """
        items = []
        page = 1
        per_page = 100

        if params is None:
            params = {}
        params["per_page"] = per_page

        while True:
            params["page"] = page
            result = self.get(path, params)

            if isinstance(result, list):
                items.extend(result)
                if len(result) < per_page:
                    break
            else:
                # If response is not a list (some endpoints return object with items)
                if isinstance(result, dict) and "items" in result:
                    items.extend(result["items"])
                    if len(result["items"]) < per_page:
                        break
                else:
                    # Single page response
                    items.append(result)
                    break

            page += 1

        return items

    def get_workflow_run_logs(self, owner: str, repo: str, run_id: int) -> Optional[bytes]:
        """Download workflow run logs as bytes.

        Args:
            owner: Repository owner
            repo: Repository name
            run_id: Workflow run ID

        Returns:
            Raw log content as bytes
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/actions/runs/{run_id}/logs"
        response = self.session.get(url, headers=self.headers, stream=True, timeout=60)

        if response.status_code >= 400:
            error_msg = f"HTTP error {response.status_code}: {response.text}"
            raise Exception(error_msg)

        if response.status_code == 302:
            # Follow redirect to get actual logs
            redirect_url = response.headers.get("Location")
            if redirect_url:
                log_response = self.session.get(redirect_url, timeout=60)
                if log_response.status_code == 200:
                    return log_response.content
                raise Exception(f"Failed to download logs from redirect: {log_response.status_code}")
            raise Exception("Redirect URL not found in response")

        return response.content

    def get_workflow_run(self, owner: str, repo: str, run_id: int) -> Dict[str, Any]:
        """Get workflow run details.

        Args:
            owner: Repository owner
            repo: Repository name
            run_id: Workflow run ID

        Returns:
            Workflow run details
        """
        path = f"/repos/{owner}/{repo}/actions/runs/{run_id}"
        return self.get(path)

    def get_workflow_run_jobs(self, owner: str, repo: str, run_id: int) -> List[Dict[str, Any]]:
        """Get jobs for a workflow run.

        Args:
            owner: Repository owner
            repo: Repository name
            run_id: Workflow run ID

        Returns:
            List of jobs
        """
        path = f"/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
        result = self.get(path)
        if isinstance(result, dict) and "jobs" in result:
            return result["jobs"]
        return []

    def get_job_logs(self, owner: str, repo: str, job_id: int) -> Optional[bytes]:
        """Download job logs as bytes.

        Args:
            owner: Repository owner
            repo: Repository name
            job_id: Job ID

        Returns:
            Raw log content as bytes
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/actions/jobs/{job_id}/logs"
        response = self.session.get(url, headers=self.headers, stream=True, timeout=60)

        if response.status_code >= 400:
            error_msg = f"HTTP error {response.status_code}: {response.text}"
            raise Exception(error_msg)

        if response.status_code == 302:
            redirect_url = response.headers.get("Location")
            if redirect_url:
                log_response = self.session.get(redirect_url, timeout=60)
                if log_response.status_code == 200:
                    return log_response.content
                raise Exception(f"Failed to download logs from redirect: {log_response.status_code}")
            raise Exception("Redirect URL not found in response")

        return response.content

    def get_workflow_runs(
        self,
        owner: str,
        repo: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """List workflow runs.

        Args:
            owner: Repository owner
            repo: Repository name
            params: Query parameters (branch, event, status, etc.)

        Returns:
            List of workflow runs
        """
        path = f"/repos/{owner}/{repo}/actions/runs"
        if params is None:
            params = {}
        result = self.get(path, params)
        if isinstance(result, dict) and "workflow_runs" in result:
            return result["workflow_runs"]
        return []

    def get_workflow_by_name(self, owner: str, repo: str, filename: str) -> Optional[Dict[str, Any]]:
        """Get workflow by filename.

        Args:
            owner: Repository owner
            repo: Repository name
            filename: Workflow file name (e.g., 'build.yml')

        Returns:
            Workflow details or None if not found
        """
        path = f"/repos/{owner}/{repo}/actions/workflows"
        result = self.get(path)
        if isinstance(result, dict) and "workflows" in result:
            for workflow in result["workflows"]:
                if workflow.get("path", "").endswith(filename):
                    return workflow
        return None

    def get_workflow_runs_by_file(
        self,
        owner: str,
        repo: str,
        filename: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Get workflow runs by filename.

        Args:
            owner: Repository owner
            repo: Repository name
            filename: Workflow file name
            limit: Maximum number of runs to return

        Returns:
            List of workflow runs
        """
        workflow = self.get_workflow_by_name(owner, repo, filename)
        if not workflow:
            return []

        workflow_id = workflow["id"]
        path = f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs"
        result = self.get(path, {"per_page": limit})
        if isinstance(result, dict) and "workflow_runs" in result:
            return result["workflow_runs"]
        return []

    def get_commit(self, owner: str, repo: str, sha: str) -> Dict[str, Any]:
        """Get commit details.

        Args:
            owner: Repository owner
            repo: Repository name
            sha: Commit SHA

        Returns:
            Commit details
        """
        path = f"/repos/{owner}/{repo}/commits/{sha}"
        return self.get(path)

    def get_commit_statuses(self, owner: str, repo: str, sha: str) -> List[Dict[str, Any]]:
        """Get commit statuses.

        Args:
            owner: Repository owner
            repo: Repository name
            sha: Commit SHA

        Returns:
            List of statuses
        """
        path = f"/repos/{owner}/{repo}/commits/{sha}/statuses"
        return self.get_paginated(path)

    def get_file_contents(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get file contents from repository.

        Args:
            owner: Repository owner
            repo: Repository name
            path: Path to file
            ref: Branch or commit SHA

        Returns:
            File contents
        """
        api_path = f"/repos/{owner}/{repo}/contents/{path}"
        params = {}
        if ref:
            params["ref"] = ref
        return self.get(api_path, params)

    def create_or_update_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: str = "main",
        sha: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create or update a file.

        Args:
            owner: Repository owner
            repo: Repository name
            path: Path to file
            content: File content (will be base64 encoded)
            message: Commit message
            branch: Branch name
            sha: SHA of existing file (required for update)

        Returns:
            API response
        """
        import base64

        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        data = {
            "message": message,
            "content": encoded_content,
            "branch": branch,
        }
        if sha:
            data["sha"] = sha

        api_path = f"/repos/{owner}/{repo}/contents/{path}"
        return self.put(api_path, data)

    def delete_file(
        self,
        owner: str,
        repo: str,
        path: str,
        message: str,
        branch: str = "main",
        sha: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Delete a file.

        Args:
            owner: Repository owner
            repo: Repository name
            path: Path to file
            message: Commit message
            branch: Branch name
            sha: SHA of file (required)

        Returns:
            API response
        """
        if not sha:
            # Get file SHA first
            try:
                file_data = self.get_file_contents(owner, repo, path, ref=branch)
                sha = file_data.get("sha")
            except Exception:
                raise Exception(f"File {path} not found on branch {branch}")

        data = {
            "message": message,
            "sha": sha,
            "branch": branch,
        }

        api_path = f"/repos/{owner}/{repo}/contents/{path}"
        return self.delete(api_path, data)

    def get_check_runs_for_commit(
        self,
        owner: str,
        repo: str,
        sha: str,
    ) -> List[Dict[str, Any]]:
        """Get check runs for a commit.

        Args:
            owner: Repository owner
            repo: Repository name
            sha: Commit SHA

        Returns:
            List of check runs
        """
        path = f"/repos/{owner}/{repo}/commits/{sha}/check-runs"
        result = self.get(path)
        if isinstance(result, dict) and "check_runs" in result:
            return result["check_runs"]
        return []

    def get_check_run_annotations(
        self,
        owner: str,
        repo: str,
        check_run_id: int,
    ) -> List[Dict[str, Any]]:
        """Get check run annotations.

        Args:
            owner: Repository owner
            repo: Repository name
            check_run_id: Check run ID

        Returns:
            List of annotations
        """
        path = f"/repos/{owner}/{repo}/check-runs/{check_run_id}/annotations"
        return self.get_paginated(path)

    def get_repo(self, owner: str, repo: str) -> Dict[str, Any]:
        """Get repository details.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Repository details
        """
        path = f"/repos/{owner}/{repo}"
        return self.get(path)

    def get_workflow_run_attempts(
        self,
        owner: str,
        repo: str,
        run_id: int,
    ) -> List[Dict[str, Any]]:
        """Get workflow run attempts.

        Args:
            owner: Repository owner
            repo: Repository name
            run_id: Workflow run ID

        Returns:
            List of attempts
        """
        path = f"/repos/{owner}/{repo}/actions/runs/{run_id}/attempts"
        return self.get_paginated(path)

    def get_check_run(self, owner: str, repo: str, check_run_id: int) -> Dict[str, Any]:
        """Get a specific check run.

        Args:
            owner: Repository owner
            repo: Repository name
            check_run_id: Check run ID

        Returns:
            Check run details
        """
        path = f"/repos/{owner}/{repo}/check-runs/{check_run_id}"
        return self.get(path)

    def list_commits(
        self,
        owner: str,
        repo: str,
        sha: Optional[str] = None,
        per_page: int = 30,
        page: int = 1,
    ) -> List[Dict[str, Any]]:
        """List commits in repository.

        Args:
            owner: Repository owner
            repo: Repository name
            sha: Branch or commit SHA
            per_page: Results per page
            page: Page number

        Returns:
            List of commits
        """
        path = f"/repos/{owner}/{repo}/commits"
        params = {"per_page": per_page, "page": page}
        if sha:
            params["sha"] = sha
        return self.get_paginated(path, params)

    def get_latest_run_id(self, owner: str, repo: str, workflow_name: Optional[str] = None) -> Optional[int]:
        """Get the latest workflow run ID.

        Args:
            owner: Repository owner
            repo: Repository name
            workflow_name: Optional workflow name filter

        Returns:
            Latest run ID or None
        """
        params = {"per_page": 1, "status": "completed"}
        if workflow_name:
            # Try to find workflow by name
            workflows = self.get("/repos/{owner}/{repo}/actions/workflows")
            if isinstance(workflows, dict) and "workflows" in workflows:
                for wf in workflows["workflows"]:
                    if wf.get("name") == workflow_name:
                        params["workflow_id"] = wf["id"]
                        break

        path = f"/repos/{owner}/{repo}/actions/runs"
        result = self.get(path, params)
        if isinstance(result, dict) and "workflow_runs" in result and result["workflow_runs"]:
            return result["workflow_runs"][0]["id"]
        return None
