"""GitHub API client using httpx with improved error handling and encoding support."""

from typing import Any, Optional, List, Dict
import httpx
import base64
import json


class GitHubClient:
    """Sync GitHub API client with improved error handling and UTF-8 support."""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: str):
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json; charset=utf-8",
        }
        self._client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
        )

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Execute HTTP request with error handling."""
        try:
            # Ensure JSON responses are properly encoded
            if "json" in kwargs:
                kwargs["json"] = self._ensure_utf8_dict(kwargs["json"])
            
            resp = self._client.request(method, url, headers=self._headers, **kwargs)
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as e:
            # Try to extract error message from response
            try:
                error_data = e.response.json()
                error_msg = error_data.get("message", str(e))
                raise Exception(f"GitHub API error: {error_msg}")
            except:
                raise Exception(f"HTTP error {e.response.status_code}: {e.response.text[:200]}")
        except httpx.TimeoutException:
            raise Exception("Request timeout after 30 seconds")
        except Exception as e:
            raise Exception(f"Request failed: {str(e)}")

    def _ensure_utf8_dict(self, data: dict) -> dict:
        """Ensure all string values in dict are properly encoded as UTF-8."""
        if not data:
            return data
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = value.encode('utf-8', errors='replace').decode('utf-8')
            elif isinstance(value, dict):
                result[key] = self._ensure_utf8_dict(value)
            elif isinstance(value, list):
                result[key] = [self._ensure_utf8_dict(item) if isinstance(item, dict) else item for item in value]
            else:
                result[key] = value
        return result

    def _safe_json(self, data: dict) -> dict:
        """Safely convert dict to JSON with UTF-8 support."""
        try:
            return data
        except Exception:
            # Fallback: replace problematic characters
            return json.loads(json.dumps(data, ensure_ascii=False, default=str))

    def get_file(self, owner: str, repo: str, path: str, ref: Optional[str] = None) -> dict:
        """Get file contents from repository."""
        params = {}
        if ref:
            params["ref"] = ref
        resp = self._request("GET", f"{self.BASE_URL}/repos/{owner}/{repo}/contents/{path}", params=params)
        return self._safe_json(resp.json())

    def create_or_update_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: str,
        sha: Optional[str] = None
    ) -> dict:
        """Create or update a file in the repository."""
        # Ensure content is UTF-8 encoded for base64
        content_encoded = content.encode('utf-8', errors='replace').decode('utf-8')
        body = {
            "message": message,
            "content": base64.b64encode(content_encoded.encode()).decode(),
            "branch": branch,
        }
        if sha:
            body["sha"] = sha
        resp = self._request("PUT", f"{self.BASE_URL}/repos/{owner}/{repo}/contents/{path}", json=body)
        return self._safe_json(resp.json())

    def delete_file(self, owner: str, repo: str, path: str, message: str, branch: str, sha: str) -> dict:
        """Delete a file from repository."""
        body = {"message": message, "sha": sha, "branch": branch}
        resp = self._request("DELETE", f"{self.BASE_URL}/repos/{owner}/{repo}/contents/{path}", json=body)
        return self._safe_json(resp.json())

    def get_file_sha(self, owner: str, repo: str, path: str, ref: Optional[str] = None) -> Optional[str]:
        """Get SHA of a file."""
        try:
            data = self.get_file(owner, repo, path, ref)
            return data.get("sha")
        except Exception:
            return None

    def list_commits(self, owner: str, repo: str, sha: Optional[str] = None, per_page: int = 10, page: int = 1) -> List[dict]:
        """List commits with pagination support."""
        params = {"per_page": per_page, "page": page}
        if sha:
            params["sha"] = sha
        resp = self._request("GET", f"{self.BASE_URL}/repos/{owner}/{repo}/commits", params=params)
        return self._safe_json(resp.json())

    def get_workflow_runs(self, owner: str, repo: str, per_page: int = 5, page: int = 1, status: Optional[str] = None) -> List[dict]:
        """Get workflow runs with optional status filter."""
        params = {"per_page": per_page, "page": page}
        if status:
            params["status"] = status
        resp = self._request("GET", f"{self.BASE_URL}/repos/{owner}/{repo}/actions/runs", params=params)
        return self._safe_json(resp.json()).get("workflow_runs", [])

    def get_workflow_run(self, owner: str, repo: str, run_id: int) -> dict:
        """Get specific workflow run details."""
        resp = self._request("GET", f"{self.BASE_URL}/repos/{owner}/{repo}/actions/runs/{run_id}")
        return self._safe_json(resp.json())

    def get_workflow_jobs(self, owner: str, repo: str, run_id: int, per_page: int = 50) -> List[dict]:
        """Get jobs for a workflow run."""
        params = {"per_page": per_page}
        resp = self._request("GET", f"{self.BASE_URL}/repos/{owner}/{repo}/actions/runs/{run_id}/jobs", params=params)
        return self._safe_json(resp.json()).get("jobs", [])

    def get_job_logs(self, owner: str, repo: str, job_id: int) -> str:
        """Get logs for a specific job."""
        resp = self._request("GET", f"{self.BASE_URL}/repos/{owner}/{repo}/actions/jobs/{job_id}/logs")
        # Try to decode with UTF-8, fallback to replace
        try:
            return resp.text
        except UnicodeDecodeError:
            return resp.content.decode('utf-8', errors='replace')

    def get_workflows(self, owner: str, repo: str) -> List[dict]:
        """Get all workflows in repository."""
        resp = self._request("GET", f"{self.BASE_URL}/repos/{owner}/{repo}/actions/workflows")
        return self._safe_json(resp.json()).get("workflows", [])

    def get_workflow_runs_by_id(self, owner: str, repo: str, workflow_id: int, per_page: int = 5) -> List[dict]:
        """Get workflow runs by workflow ID."""
        params = {"per_page": per_page}
        resp = self._request("GET", f"{self.BASE_URL}/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs", params=params)
        return self._safe_json(resp.json()).get("workflow_runs", [])

    def get_commit_status(self, owner: str, repo: str, sha: str) -> dict:
        """Get commit status."""
        resp = self._request("GET", f"{self.BASE_URL}/repos/{owner}/{repo}/commits/{sha}/status")
        return self._safe_json(resp.json())

    def get_check_runs(self, owner: str, repo: str, sha: str) -> List[dict]:
        """Get check runs for a commit."""
        params = {"per_page": 100}
        resp = self._request("GET", f"{self.BASE_URL}/repos/{owner}/{repo}/commits/{sha}/check-runs", params=params)
        return self._safe_json(resp.json()).get("check_runs", [])

    def get_step_logs_via_checks(
        self,
        owner: str,
        repo: str,
        run_id: int,
        step_name: str
    ) -> dict:
        """
        Get logs for a specific step via GitHub Checks API.
        Fast way to get errors without downloading the entire ZIP archive.
        
        Args:
            owner: Repository owner
            repo: Repository name
            run_id: Workflow run ID
            step_name: Step name (partial match, case insensitive)
            
        Returns:
            dict with check run data including output
        """
        # 1. Get run info to get commit SHA
        run_data = self.get_workflow_run(owner, repo, run_id)
        commit_sha = run_data.get("head_sha")
        if not commit_sha:
            raise Exception("No commit SHA found")
        
        # 2. Get check-runs for this commit
        check_runs = self.get_check_runs(owner, repo, commit_sha)
        
        # 3. Find check-run with the step name
        found_check = None
        for check in check_runs:
            check_name = check.get("name", "").lower()
            if step_name.lower() in check_name:
                found_check = check
                break
        
        if not found_check:
            raise Exception(
                f"No check-run found for step: {step_name}"
            )
        
        # 4. Return check-run data
        return {
            "run_id": run_id,
            "step_name": step_name,
            "commit_sha": commit_sha,
            "check_run": {
                "name": found_check.get("name"),
                "status": found_check.get("status"),
                "conclusion": found_check.get("conclusion"),
                "started_at": found_check.get("started_at"),
                "completed_at": found_check.get("completed_at"),
                "output": {
                    "title": found_check.get("output", {}).get("title"),
                    "summary": found_check.get("output", {}).get("summary"),
                    "text": found_check.get("output", {}).get("text"),
                    "annotations_count": len(found_check.get("output", {}).get("annotations", []))
                }
            },
            "note": "Checks API returns truncated output (up to 65535 characters). For full logs, use get_run_logs_by_step."
        }
