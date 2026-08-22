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
            if "json" in kwargs:
                kwargs["json"] = self._ensure_utf8_dict(kwargs["json"])
            
            resp = self._client.request(method, url, headers=self._headers, **kwargs)
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as e:
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
        try:
            return resp.text
        except UnicodeDecodeError:
            return resp.content.decode('utf-8', errors='replace')

    def get_workflow_run_logs(self, owner: str, repo: str, run_id: int) -> bytes:
        """Download workflow run logs as bytes.
        
        Args:
            owner: Repository owner
            repo: Repository name
            run_id: Workflow run ID
            
        Returns:
            Raw log content as bytes
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/actions/runs/{run_id}/logs"
        
        # First request to get redirect URL
        resp = self._client.get(url, headers=self._headers, follow_redirects=False)
        
        if resp.status_code == 302:
            redirect_url = resp.headers.get("Location")
            if redirect_url:
                # Download logs from redirect URL
                log_resp = self._client.get(redirect_url, follow_redirects=True)
                if log_resp.status_code == 200:
                    return log_resp.content
                raise Exception(f"Failed to download logs: {log_resp.status_code}")
            raise Exception("Redirect URL not found")
        elif resp.status_code == 200:
            return resp.content
        else:
            raise Exception(f"Failed to download logs: {resp.status_code}")

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
        resp = self._request("GET", f"{self.BASE_URL}/repos/{owner}/{repo}/commits/{sha}/check-runs")
        return self._safe_json(resp.json()).get("check_runs", [])

    def get_check_run_annotations(self, owner: str, repo: str, check_run_id: int) -> List[dict]:
        """Get check run annotations."""
        resp = self._request("GET", f"{self.BASE_URL}/repos/{owner}/{repo}/check-runs/{check_run_id}/annotations")
        return self._safe_json(resp.json())

    def get_repo(self, owner: str, repo: str) -> dict:
        """Get repository details."""
        resp = self._request("GET", f"{self.BASE_URL}/repos/{owner}/{repo}")
        return self._safe_json(resp.json())

    def get_workflow_run_attempts(self, owner: str, repo: str, run_id: int) -> List[dict]:
        """Get workflow run attempts."""
        resp = self._request("GET", f"{self.BASE_URL}/repos/{owner}/{repo}/actions/runs/{run_id}/attempts")
        return self._safe_json(resp.json())

    def get_check_run(self, owner: str, repo: str, check_run_id: int) -> dict:
        """Get a specific check run."""
        resp = self._request("GET", f"{self.BASE_URL}/repos/{owner}/{repo}/check-runs/{check_run_id}")
        return self._safe_json(resp.json())

    def get_latest_run_id(self, owner: str, repo: str, workflow_name: Optional[str] = None) -> Optional[int]:
        """Get the latest workflow run ID."""
        runs = self.get_workflow_runs(owner, repo, per_page=1)
        if runs:
            return runs[0].get("id")
        return None

    def get_workflow_runs_with_params(self, owner: str, repo: str, params: Optional[Dict[str, Any]] = None) -> List[dict]:
        """Get workflow runs with custom parameters."""
        if params is None:
            params = {}
        resp = self._request("GET", f"{self.BASE_URL}/repos/{owner}/{repo}/actions/runs", params=params)
        return self._safe_json(resp.json()).get("workflow_runs", [])
