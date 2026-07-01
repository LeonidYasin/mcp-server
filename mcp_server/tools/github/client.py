"""GitHub API client using httpx."""

from typing import Any

import httpx


class GitHubClient:
    """Async GitHub API client."""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: str):
        self.token = token
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def get_file(self, owner: str, repo: str, path: str, ref: str | None = None) -> dict[str, Any]:
        """Get file contents from a repository."""
        params = {}
        if ref:
            params["ref"] = ref

        resp = await self._client.get(f"/repos/{owner}/{repo}/contents/{path}", params=params)
        resp.raise_for_status()
        return resp.json()

    async def create_or_update_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: str,
        sha: str | None = None,
    ) -> dict[str, Any]:
        """Create or update a file in a repository."""
        import base64

        body: dict[str, Any] = {
            "message": message,
            "content": base64.b64encode(content.encode()).decode(),
            "branch": branch,
        }
        if sha:
            body["sha"] = sha

        resp = await self._client.put(f"/repos/{owner}/{repo}/contents/{path}", json=body)
        resp.raise_for_status()
        return resp.json()

    async def delete_file(
        self,
        owner: str,
        repo: str,
        path: str,
        message: str,
        branch: str,
        sha: str,
    ) -> dict[str, Any]:
        """Delete a file from a repository."""
        body = {
            "message": message,
            "sha": sha,
            "branch": branch,
        }

        resp = await self._client.delete(f"/repos/{owner}/{repo}/contents/{path}", json=body)
        resp.raise_for_status()
        return resp.json()
