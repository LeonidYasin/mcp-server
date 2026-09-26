"""Тесты push_multiple_files: пустой репозиторий (409) и обычный путь."""

import json
from unittest.mock import MagicMock

import pytest

from mcp_server.tools.github.batch import push_multiple_files


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def _make_client(handler):
    """client-заглушка: _request делегирует в handler(method, url, **kw)."""
    client = MagicMock()

    def _request(method, url, **kwargs):
        result = handler(method, url, **kwargs)
        if isinstance(result, Exception):
            raise result
        return FakeResponse(result)

    client._request.side_effect = _request
    return client


FILES = [
    {"path": "README.md", "content": "# Hello"},
    {"path": "src/main.py", "content": "print('hi')"},
]


def test_push_multiple_files_bootstraps_empty_repo():
    """409 на GET ref → bootstrap, инструмент НЕ падает."""
    calls = []

    def handler(method, url, **kwargs):
        calls.append((method, url, kwargs.get("json")))
        if method == "GET" and "/git/ref/heads/" in url:
            # GitHub на пустом репо отдаёт 409; client._request
            # превращает это в Exception с текстом "HTTP error 409: ..."
            return Exception("HTTP error 409: Git Repository is empty.")
        if method == "POST" and url.endswith("/git/blobs"):
            return {"sha": "blob-sha"}
        if method == "POST" and url.endswith("/git/trees"):
            return {"sha": "tree-sha"}
        if method == "POST" and url.endswith("/git/commits"):
            return {"sha": "commit-sha-12345678"}
        if method == "POST" and url.endswith("/git/refs"):
            return {"ref": "refs/heads/main", "object": {"sha": "commit-sha-12345678"}}
        raise AssertionError(f"неожиданный вызов: {method} {url}")

    client = _make_client(handler)
    result = push_multiple_files(
        client, owner="o", repo="r", branch="main", message="init", files=FILES
    )

    assert "✅" in result, result
    assert "bootstrap" in result

    methods_urls = [(m, u) for m, u, _ in calls]
    # Ветка создаётся, а не сдвигается
    assert any(m == "POST" and u.endswith("/git/refs") for m, u in methods_urls)
    assert not any(m == "PATCH" for m, _ in methods_urls)
    # GET ref был, но упал — и это не сломало инструмент
    assert any(m == "GET" and "/git/ref/heads/" in u for m, u in methods_urls)

    tree_payload = next(
        kw for m, u, kw in calls if m == "POST" and u.endswith("/git/trees")
    )
    assert "base_tree" not in tree_payload

    commit_payload = next(
        kw for m, u, kw in calls if m == "POST" and u.endswith("/git/commits")
    )
    assert "parents" not in commit_payload

    # По одному blob на каждый файл
    blob_calls = [c for c in calls if c[0] == "POST" and c[1].endswith("/git/blobs")]
    assert len(blob_calls) == len(FILES)


def test_push_multiple_files_keeps_single_commit_on_nonempty_repo():
    """Непустой репо: регресс — поведение не изменилось."""
    calls = []

    def handler(method, url, **kwargs):
        calls.append((method, url, kwargs.get("json")))
        if method == "GET" and "/git/ref/heads/" in url:
            return {"object": {"sha": "base-sha"}}
        if method == "GET" and "/git/commits/" in url:
            return {"tree": {"sha": "base-tree-sha"}}
        if method == "POST" and url.endswith("/git/blobs"):
            return {"sha": "blob-sha"}
        if method == "POST" and url.endswith("/git/trees"):
            return {"sha": "tree-sha"}
        if method == "POST" and url.endswith("/git/commits"):
            return {"sha": "commit-sha-abcdefgh"}
        if method == "PATCH" and "/git/refs/heads/" in url:
            return {"object": {"sha": "commit-sha-abcdefgh"}}
        raise AssertionError(f"неожиданный вызов: {method} {url}")

    client = _make_client(handler)
    result = push_multiple_files(
        client, owner="o", repo="r", branch="main", message="update", files=FILES
    )

    assert "✅" in result, result
    assert "bootstrap" not in result

    assert any(m == "PATCH" for m, _, _ in calls)
    assert not any(m == "POST" and u.endswith("/git/refs") for m, u, _ in calls)

    tree_payload = next(
        kw for m, u, kw in calls if m == "POST" and u.endswith("/git/trees")
    )
    assert tree_payload["base_tree"] == "base-tree-sha"

    commit_payload = next(
        kw for m, u, kw in calls if m == "POST" and u.endswith("/git/commits")
    )
    assert commit_payload["parents"] == ["base-sha"]
