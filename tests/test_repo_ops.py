"""Тесты repo_ops: create_repo, list_my_repos, update_repo."""

import json
from unittest.mock import MagicMock

import pytest

from mcp_server.tools.github.repo_ops import (
    create_repo,
    list_my_repos,
    update_repo,
)


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def _make_client(handler):
    client = MagicMock()

    def _request(method, url, **kwargs):
        result = handler(method, url, **kwargs)
        if isinstance(result, Exception):
            raise result
        return FakeResponse(result)

    client._request.side_effect = _request
    return client


REPO_PAYLOAD = {
    "full_name": "me/test-repo",
    "html_url": "https://github.com/me/test-repo",
    "default_branch": "main",
    "clone_url": "https://github.com/me/test-repo.git",
    "private": False,
}


def test_create_repo_personal_with_auto_init():
    calls = []

    def handler(method, url, **kwargs):
        calls.append((method, url, kwargs.get("json")))
        if method == "POST" and url == "/user/repos":
            return REPO_PAYLOAD
        raise AssertionError(f"неожиданный вызов: {method} {url}")

    client = _make_client(handler)
    result = create_repo(client, name="test-repo")

    assert "me/test-repo" in result
    assert "main" in result

    method, url, payload = calls[0]
    assert method == "POST" and url == "/user/repos"
    assert payload["name"] == "test-repo"
    assert payload["private"] is False
    assert payload["auto_init"] is True


def test_create_repo_with_auto_init_false():
    calls = []
    empty_repo = {**REPO_PAYLOAD, "default_branch": "main"}

    def handler(method, url, **kwargs):
        calls.append((method, url, kwargs.get("json")))
        if method == "POST" and url == "/user/repos":
            return empty_repo
        raise AssertionError(f"неожиданный вызов: {method} {url}")

    client = _make_client(handler)
    result = create_repo(client, name="test-repo", auto_init=False)

    assert "me/test-repo" in result
    _, _, payload = calls[0]
    assert payload["auto_init"] is False


def test_create_repo_in_org():
    calls = []
    org_repo = {**REPO_PAYLOAD, "full_name": "some-org/test-repo"}

    def handler(method, url, **kwargs):
        calls.append((method, url, kwargs.get("json")))
        if method == "POST" and url == "/orgs/some-org/repos":
            return org_repo
        raise AssertionError(f"неожиданный вызов: {method} {url}")

    client = _make_client(handler)
    result = create_repo(client, name="test-repo", org="some-org")

    assert "some-org/test-repo" in result
    method, url, _ = calls[0]
    assert method == "POST" and url == "/orgs/some-org/repos"


def test_create_repo_403_gives_scope_hint():
    def handler(method, url, **kwargs):
        return Exception("HTTP error 403: Resource not accessible by integration")

    client = _make_client(handler)
    with pytest.raises(PermissionError) as ei:
        create_repo(client, name="test-repo")

    msg = str(ei.value)
    assert "scope" in msg.lower()
    assert "repo" in msg


def test_list_my_repos_returns_key_fields():
    def handler(method, url, **kwargs):
        if method == "GET" and url == "/user/repos":
            return [
                {"full_name": "me/a", "private": False, "updated_at": "2026-01-01T00:00:00Z"},
                {"full_name": "me/b", "private": True, "updated_at": "2026-02-02T00:00:00Z"},
            ]
        raise AssertionError(f"неожиданный вызов: {method} {url}")

    client = _make_client(handler)
    result = list_my_repos(client)

    assert "me/a" in result
    assert "me/b" in result
    assert "2026-01-01T00:00:00Z" in result
    assert "2026-02-02T00:00:00Z" in result


def test_update_repo_only_description():
    calls = []

    def handler(method, url, **kwargs):
        calls.append((method, url, kwargs.get("json")))
        if method == "PATCH" and url == "/repos/me/test-repo":
            return {**REPO_PAYLOAD, "description": "new"}
        raise AssertionError(f"неожиданный вызов: {method} {url}")

    client = _make_client(handler)
    result = update_repo(client, owner="me", repo="test-repo", description="new")

    assert "me/test-repo" in result
    assert "description" in result

    method, url, payload = calls[0]
    assert method == "PATCH" and url == "/repos/me/test-repo"
    assert payload == {"description": "new"}


def test_update_repo_no_fields_returns_warning():
    client = _make_client(lambda *a, **k: (_ for _ in ()).throw(AssertionError("no call expected")))
    result = update_repo(client, owner="me", repo="test-repo")
    assert "❌" in result
