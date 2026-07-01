"""GitHub API client using httpx."""

from typing import Any
import httpx
import base64


class GitHubClient:
    """Sync GitHub API client (used within Flask request context)."""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: str):
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        with httpx.Client(timeout=30.0) as client:
            resp = client.request(method, url, headers=self._headers, **kwargs)
            resp.raise_for_status()
            return resp

    def get_file(self, owner: str, repo: str, path: str, ref: str | None = None) -> dict[str, Any]:
        params = {}
        if ref:
            params["ref"] = ref
        resp = self._request("GET", f"{self.BASE_URL}/repos/{owner}/{repo}/contents/{path}", params=params)
        return resp.json()

    def create_or_update_file(self, owner: str, repo: str, path: str, content: str, message: str, branch: str, sha: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"message": message, "content": base64.b64encode(content.encode()).decode(), "branch": branch}
        if sha:
            body["sha"] = sha
        resp = self._request("PUT", f"{self.BASE_URL}/repos/{owner}/{repo}/contents/{path}", json=body)
        return resp.json()

    def delete_file(self, owner: str, repo: str, path: str, message: str, branch: str, sha: str) -> dict[str, Any]:
        body = {"message": message, "sha": sha, "branch": branch}
        resp = self._request("DELETE", f"{self.BASE_URL}/repos/{owner}/{repo}/contents/{path}", json=body)
        return resp.json()

    def get_file_sha(self, owner: str, repo: str, path: str, ref: str | None = None) -> str | None:
        try:
            data = self.get_file(owner, repo, path, ref)
            return data.get("sha")
        except Exception:
            return None

    def list_commits(self, owner: str, repo: str, sha: str | None = None, per_page: int = 10) -> list[dict]:
        params = {"per_page": per_page}
        if sha:
            params["sha"] = sha
        resp = self._request("GET", f"{self.BASE_URL}/repos/{owner}/{repo}/commits", params=params)
        return resp.json()

    def get_workflow_runs(self, owner: str, repo: str, per_page: int = 5) -> list[dict]:
        resp = self._request("GET", f"{self.BASE_URL}/repos/{owner}/{repo}/actions/runs", params={"per_page": per_page})
        return resp.json().get("workflow_runs", [])

    def get_workflow_run(self, owner: str, repo: str, run_id: int) -> dict:
        resp = self._request("GET", f"{self.BASE_URL}/repos/{owner}/{repo}/actions/runs/{run_id}")
        return resp.json()

    def get_workflow_jobs(self, owner: str, repo: str, run_id: int) -> list[dict]:
        resp = self._request("GET", f"{self.BASE_URL}/repos/{owner}/{repo}/actions/runs/{run_id}/jobs")
        return resp.json().get("jobs", [])

    def get_job_logs(self, owner: str, repo: str, job_id: int) -> str:
        resp = self._request("GET", f"{self.BASE_URL}/repos/{owner}/{repo}/actions/jobs/{job_id}/logs")
        return resp.text

    def get_workflows(self, owner: str, repo: str) -> list[dict]:
        resp = self._request("GET", f"{self.BASE_URL}/repos/{owner}/{repo}/actions/workflows")
        return resp.json().get("workflows", [])

    def get_workflow_runs_by_id(self, owner: str, repo: str, workflow_id: int, per_page: int = 5) -> list[dict]:
        resp = self._request("GET", f"{self.BASE_URL}/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs", params={"per_page": per_page})
        return resp.json().get("workflow_runs", [])

    def get_commit_status(self, owner: str, repo: str, sha: str) -> dict:
        resp = self._request("GET", f"{self.BASE_URL}/repos/{owner}/{repo}/commits/{sha}/status")
        return resp.json()

    def get_check_runs(self, owner: str, repo: str, sha: str) -> list[dict]:
        resp = self._request("GET", f"{self.BASE_URL}/repos/{owner}/{repo}/commits/{sha}/check-runs")
        return resp.json().get("check_runs", [])

    def create_branch(self, owner: str, repo: str, branch: str, from_branch: str) -> dict:
        ref_resp = self._request("GET", f"{self.BASE_URL}/repos/{owner}/{repo}/git/ref/heads/{from_branch}")
        sha = ref_resp.json()["object"]["sha"]
        resp = self._request("POST", f"{self.BASE_URL}/repos/{owner}/{repo}/git/refs", json={"ref": f"refs/heads/{branch}", "sha": sha})
        return resp.json()
