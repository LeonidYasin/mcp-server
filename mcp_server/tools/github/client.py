"""GitHub API client using httpx with improved error handling and encoding support."""

from typing import Any, Optional, List, Dict
import httpx
import base64
import json
import io
import zipfile
import re
from urllib.parse import urlsplit, unquote, quote


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
        # base_url обязателен: часть инструментов передаёт относительные пути
        # вида "/repos/..."; без base_url httpx падает с UnsupportedProtocol
        # ("Request URL is missing an 'http://' or 'https://' protocol").
        self._client = httpx.Client(
            base_url=self.BASE_URL,
            timeout=30.0,
            follow_redirects=True,
        )

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Execute HTTP request with error handling.

        ВАЖНО: если вызывающий передал headers=..., они МЕРЖАТСЯ с базовыми
        (Authorization, Accept и т.д.), а не заменяют их и не дублируются.
        Иначе httpx получает headers дважды и падает с
        'got multiple values for keyword argument headers'
        (так ломался search_code и все *_search инструменты).
        """
        try:
            # Вынимаем пользовательские заголовки ДО вызова, чтобы не было дубля
            extra_headers = kwargs.pop("headers", None)
            headers = dict(self._headers)
            if extra_headers:
                headers.update(extra_headers)

            if "json" in kwargs:
                kwargs["json"] = self._ensure_utf8_dict(kwargs["json"])

            resp = self._client.request(method, url, headers=headers, **kwargs)
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

    def resolve_artifact_download(self, owner: str, repo: str, artifact_id: int) -> dict:
        """Resolve only the fixed GitHub API redirect; never fetch its destination/body."""
        result = {"outcome": "unknown", "download_url": None, "http_status": None, "error": None}
        if (not isinstance(owner, str) or not re.fullmatch(r"[A-Za-z0-9-]+", owner)
                or not isinstance(repo, str) or repo in (".", "..")
                or not re.fullmatch(r"[A-Za-z0-9_.-]+", repo)
                or type(artifact_id) is not int or artifact_id < 1):
            return {**result, "outcome": "invalid_input", "error": "invalid_identity"}
        path = f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/actions/artifacts/{artifact_id}/zip"
        try:
            # _request calls raise_for_status (302 raises in httpx), and ordinary
            # client requests follow redirects. Neither path is safe for this purpose.
            with self._client.stream("GET", path, headers=dict(self._headers), follow_redirects=False) as response:
                result["http_status"] = response.status_code
                if response.status_code != 302:
                    return {**result, "outcome": "api_refused" if response.status_code >= 400 else "unexpected_response",
                            "error": "download_endpoint_not_302"}
                location = response.headers.get("Location", "")
                if not isinstance(location, str) or not location or len(location) > 16384:
                    raise ValueError("invalid redirect")
                if any(ord(c) < 33 or ord(c) > 126 for c in location) or "\\" in location:
                    raise ValueError("invalid redirect characters")
                parts = urlsplit(location)
                host = parts.hostname or ""
                allowed = (host == "objects.githubusercontent.com"
                           or re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)*\.actions\.githubusercontent\.com", host)
                           or re.fullmatch(r"productionresultssa[0-9]+\.blob\.core\.windows\.net", host))
                if (parts.scheme != "https" or not allowed or parts.port not in (None, 443)
                        or parts.username is not None or parts.password is not None or parts.fragment
                        or not parts.path.startswith("/")):
                    raise ValueError("untrusted redirect")
                # A signed CDN capability may be returned, but never reflect our PAT.
                auth = self._headers.get("Authorization", "")
                token = auth[7:] if auth.startswith("Bearer ") else ""
                if token and (token in location or token in unquote(location)):
                    raise ValueError("credential reflected in redirect")
                return {**result, "outcome": "resolved", "download_url": location}
        except ValueError:
            return {**result, "outcome": "redirect_rejected", "error": "untrusted_or_missing_location"}
        except Exception:
            return {**result, "error": "download_request_failed"}

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

    def get_workflows(self, owner: str, repo: str, per_page: int = 100) -> List[dict]:
        """List workflows in a repository.

        GET /repos/{owner}/{repo}/actions/workflows → поле 'workflows'.
        Используется инструментом get_workflow_by_file.
        """
        params = {"per_page": per_page}
        resp = self._request("GET", f"{self.BASE_URL}/repos/{owner}/{repo}/actions/workflows", params=params)
        return self._safe_json(resp.json()).get("workflows", [])

    def get_workflow_runs_by_id(self, owner: str, repo: str, workflow_id: int, per_page: int = 10) -> List[dict]:
        """List runs for a specific workflow id.

        GET /repos/{owner}/{repo}/actions/workflows/{id}/runs → 'workflow_runs'.
        Используется инструментом get_workflow_by_file.
        """
        params = {"per_page": per_page}
        resp = self._request("GET", f"{self.BASE_URL}/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs", params=params)
        return self._safe_json(resp.json()).get("workflow_runs", [])

    def get_check_runs(self, owner: str, repo: str, ref: str, per_page: int = 100) -> List[dict]:
        """Get check-runs for a commit ref (GitHub Checks API).

        Используется get_step_logs_via_checks. Прямой REST-запрос
        GET /repos/{owner}/{repo}/commits/{ref}/check-runs.
        """
        params = {"per_page": per_page}
        resp = self._request(
            "GET",
            f"{self.BASE_URL}/repos/{owner}/{repo}/commits/{ref}/check-runs",
            params=params,
        )
        return self._safe_json(resp.json()).get("check_runs", [])

    def get_job_logs(self, owner: str, repo: str, job_id: int) -> str:
        """Get logs for a specific job."""
        resp = self._request("GET", f"{self.BASE_URL}/repos/{owner}/{repo}/actions/jobs/{job_id}/logs")
        try:
            return resp.text
        except UnicodeDecodeError:
            return resp.content.decode('utf-8', errors='replace')

    def get_workflow_run_logs(self, owner: str, repo: str, run_id: int) -> bytes:
        """Download workflow run logs as raw bytes.

        ВНИМАНИЕ: GitHub отдаёт это как ZIP-архив. Для текста используй
        get_workflow_run_logs_text() / get_workflow_run_logs_files().

        Returns:
            Raw ZIP content as bytes
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/actions/runs/{run_id}/logs"

        # First request to get redirect URL
        resp = self._client.get(url, headers=self._headers, follow_redirects=False)

        if resp.status_code == 302:
            redirect_url = resp.headers.get("Location")
            if redirect_url:
                log_resp = self._client.get(redirect_url, follow_redirects=True)
                if log_resp.status_code == 200:
                    return log_resp.content
                raise Exception(f"Failed to download logs: {log_resp.status_code}")
            raise Exception("Redirect URL not found")
        raise Exception(f"Unexpected status code: {resp.status_code}")

    def get_workflow_run_logs_files(self, owner: str, repo: str, run_id: int) -> Dict[str, str]:
        """Скачать ZIP-логи и распаковать в {filename: text}.

        GitHub отдаёт /actions/runs/{id}/logs как ZIP. Раньше инструменты
        декодировали ZIP как UTF-8 → мусор 'PK\\x03\\x04'. Здесь распаковываем.
        """
        raw = self.get_workflow_run_logs(owner, repo, run_id)  # bytes (ZIP)
        if isinstance(raw, str):
            raw = raw.encode("utf-8", errors="replace")
        out: Dict[str, str] = {}
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                for name in zf.namelist():
                    if name.endswith("/"):
                        continue
                    try:
                        out[name] = zf.read(name).decode("utf-8", errors="replace")
                    except Exception:
                        continue
        except zipfile.BadZipFile:
            out["(raw)"] = raw.decode("utf-8", errors="replace")
        return out

    def get_workflow_run_logs_text(self, owner: str, repo: str, run_id: int) -> str:
        """Распакованные логи, склеенные в текст с заголовками файлов."""
        files = self.get_workflow_run_logs_files(owner, repo, run_id)
        parts = []
        for name, text in files.items():
            parts.append(f"===== {name} =====")
            parts.append(text)
        return "\n".join(parts)

    def get_commit_status(self, owner: str, repo: str, ref: str) -> dict:
        """Get combined commit status."""
        resp = self._request("GET", f"{self.BASE_URL}/repos/{owner}/{repo}/commits/{ref}/status")
        return self._safe_json(resp.json())
