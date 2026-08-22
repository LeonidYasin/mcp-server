"""GitHub API клиент для MCP сервера."""

import os
import requests
import zipfile
import io
from typing import Optional, Dict, Any, List


class GitHubClient:
    """Клиент для работы с GitHub API."""

    def __init__(self, token: Optional[str] = None):
        """
        Инициализация клиента.

        Args:
            token: GitHub Personal Access Token. Если не указан, берется из GITHUB_TOKEN.
        """
        self.token = token or os.getenv("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("GITHUB_TOKEN not set")
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json"
        }

    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Выполняет запрос к GitHub API."""
        url = f"{self.base_url}{path}"
        headers = self.headers.copy()
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        response = requests.request(method, url, headers=headers, **kwargs)
        response.raise_for_status()
        return response.json()

    def get_workflow_run_logs(self, owner: str, repo: str, run_id: int) -> bytes:
        """
        Скачивает архив с логами workflow run.

        Args:
            owner: Владелец репозитория
            repo: Имя репозитория
            run_id: ID запуска workflow

        Returns:
            bytes: Содержимое ZIP-архива с логами
        """
        path = f"/repos/{owner}/{repo}/actions/runs/{run_id}/logs"
        url = f"{self.base_url}{path}"
        headers = self.headers.copy()
        headers["Accept"] = "application/vnd.github+json"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.content

    def get_jobs_for_run(self, owner: str, repo: str, run_id: int) -> List[Dict[str, Any]]:
        """
        Получает список jobs для workflow run.

        Args:
            owner: Владелец репозитория
            repo: Имя репозитория
            run_id: ID запуска workflow

        Returns:
            List[Dict]: Список jobs
        """
        path = f"/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
        data = self._request("GET", path)
        return data.get("jobs", [])

    def get_run_info(self, owner: str, repo: str, run_id: int) -> Dict[str, Any]:
        """
        Получает информацию о workflow run.

        Args:
            owner: Владелец репозитория
            repo: Имя репозитория
            run_id: ID запуска workflow

        Returns:
            Dict: Информация о запуске
        """
        path = f"/repos/{owner}/{repo}/actions/runs/{run_id}"
        return self._request("GET", path)

    def get_check_runs_for_commit(self, owner: str, repo: str, commit_sha: str) -> List[Dict[str, Any]]:
        """
        Получает check-runs для коммита.

        Args:
            owner: Владелец репозитория
            repo: Имя репозитория
            commit_sha: SHA коммита

        Returns:
            List[Dict]: Список check-runs
        """
        path = f"/repos/{owner}/{repo}/commits/{commit_sha}/check-runs"
        data = self._request("GET", path, params={"per_page": 100})
        return data.get("check_runs", [])
