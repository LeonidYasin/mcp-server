"""Offline regression for oversized recursive-tree recovery; never runs repo code."""
import base64
import hashlib
import json

import httpx
import pytest

from mcp_server.tools.github import repository_evidence as module
from mcp_server.tools.github.repo import get_repo_info

HEAD, ROOT, BACKEND, APP = (c * 40 for c in "abcd")
PATH = "backend/app/main.py"
OTHER = "backend/app/extra.py"


def blob(path, text="def calculate():\n    return 42\n"):
    raw = text.encode()
    return {"type": "file", "path": path, "encoding": "base64", "size": len(raw),
            "sha": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest(),
            "content": base64.b64encode(raw).decode()}


def entry(path, sha, kind="tree", mode="040000"):
    return {"path": path, "sha": sha, "type": kind, "mode": mode}


class Corpus:
    def __init__(self):
        self.calls = []
        self.override = None
        self.files = {PATH: blob(PATH), OTHER: blob(OTHER, "extra\n")}
        self.trees = {ROOT: [entry("backend", BACKEND)], BACKEND: [entry("app", APP)],
                      APP: [entry(p.rsplit("/", 1)[1], f["sha"], "blob", "100644")
                            for p, f in self.files.items()]}
        self._headers = {"Authorization": "Bearer SYNTHETIC_GATE_ONLY"}
        self._client = httpx.Client(transport=httpx.MockTransport(self.handle),
                                   headers={"Authorization": "SYNTHETIC_GATE_ONLY"},
                                   cookies={"private": "synthetic"}, params={"leaked": "synthetic"})

    def handle(self, request):
        self.calls.append(request)
        if self.override:
            response = self.override(request)
            if response is not None:
                return response
        path = request.url.path
        if "/git/trees/" in path:
            if request.url.params.get("recursive") == "1":
                return httpx.Response(200, content=b"x" * (module.BODY_CAP + 1))
            sha = path.rsplit("/", 1)[1]
            return httpx.Response(200, json={"sha": sha, "truncated": False, "tree": self.trees[sha]})
        if "/contents/" in path:
            return httpx.Response(200, json=self.files[path.split("/contents/", 1)[1]])
        if "/commits/" in path:
            return httpx.Response(200, json={"sha": HEAD, "commit": {"tree": {"sha": ROOT}}})
        return httpx.Response(200, json={"id": 1, "full_name": "alice/tiny", "private": False,
                                         "fork": False, "default_branch": "main", "stargazers_count": 0})


@pytest.fixture
def corpus():
    value = Corpus()
    yield value
    value._client.close()


def run(corpus, **kwargs):
    args = {"owner": "alice", "repo": "tiny", "mode": "public_evidence", "ref": HEAD,
            "evidence_files": [{"path": PATH}], **kwargs}
    return json.loads(get_repo_info(corpus, **args))


def test_explicit_nested_file_recovers_without_raising_caps(corpus):
    result = run(corpus)
    assert result["state"] == "observed" and result["error"] is None and not result["gaps"]
    assert result["files"][0]["text"] == "def calculate():\n    return 42"
    assert result["files"][0]["blob_sha"] == corpus.files[PATH]["sha"]
    assert result["files"][0]["url"].endswith(f"/{HEAD}/{PATH}#L1-L2")
    selection = result["selection_tree"]
    assert selection["strategy"] == "explicit_path_walk_v1"
    assert selection["recursive_tree_source"] == 2 and selection["source"] == 3
    assert [x["sha"] for x in selection["traversed_trees"]] == [ROOT, BACKEND, APP]
    assert result["sources"][2]["error"] == "body_budget"
    assert result["budget"]["requests"] == 7
    assert result["budget"]["per_response_cap_bytes"] == 262144
    assert result["budget"]["max_requests"] == 12
    assert not any(result["coverage"].values())
    for request in corpus.calls:
        assert request.method == "GET" and request.url.host == "api.github.com"
        assert not ({"authorization", "cookie"} & set(request.headers))
        assert "leaked" not in request.url.params
    assert dict(corpus.calls[-1].url.params) == {"ref": HEAD}


def test_shared_directories_are_read_once(corpus):
    result = run(corpus, evidence_files=[{"path": PATH}, {"path": OTHER}])
    assert result["state"] == "observed" and len(result["files"]) == 2
    assert result["budget"]["requests"] == 8
    assert len(result["selection_tree"]["traversed_trees"]) == 3
    assert sum("/git/trees/" in r.url.path and not r.url.params for r in corpus.calls) == 3


@pytest.mark.parametrize("level,change", [
    (ROOT, {"type": "blob", "mode": "100644"}),
    (ROOT, {"type": "blob", "mode": "120000"}),
    (ROOT, {"type": "commit", "mode": "160000"}),
    (ROOT, {"type": "tree", "mode": "100644"}),
    (APP, {"type": "blob", "mode": "120000"}),
    (APP, {"type": "commit", "mode": "160000"}),
    (APP, {"type": "tree", "mode": "040000"}),
])
def test_never_resolves_symlink_submodule_or_wrong_mode(corpus, level, change):
    corpus.trees[level][0].update(change)
    result = run(corpus)
    assert result["state"] == "partial" and not result["files"]
    assert result["gaps"][0]["error"] == "regular_file_not_verified_in_tree"
    assert not any("/contents/" in r.url.path for r in corpus.calls)


@pytest.mark.parametrize("change", [{"sha": "e" * 40}, {"truncated": True},
                                      {"truncated": 0}, {"tree": None}])
def test_invalid_path_tree_is_not_evidence(corpus, change):
    def override(request):
        if request.url.path.endswith("/git/trees/" + ROOT) and not request.url.params:
            return httpx.Response(200, json={"sha": ROOT, "tree": corpus.trees[ROOT],
                                             "truncated": False, **change})
    corpus.override = override
    result = run(corpus)
    assert result["state"] == "unavailable" and result["error"] == "path_tree_unverified"
    assert len(corpus.calls) == 4 and not result["files"]


@pytest.mark.parametrize("level", [ROOT, APP])
def test_ambiguous_path_component_is_refused(corpus, level):
    corpus.trees[level].append(dict(corpus.trees[level][0]))
    result = run(corpus)
    assert result["state"] == "unavailable" and result["error"] == "ambiguous_tree"
    assert not any("/contents/" in r.url.path for r in corpus.calls)


def test_missing_component_is_unknown_not_contents_fallback(corpus):
    corpus.trees[BACKEND] = []
    result = run(corpus)
    assert result["state"] == "partial" and not result["files"]
    assert not any("/contents/" in r.url.path for r in corpus.calls)


def test_auto_does_not_claim_selection_from_path_subset(corpus):
    result = run(corpus, file_selection="auto", evidence_files=None)
    # Auto forbids evidence_files even when null: use the actual valid auto shape.
    result = json.loads(get_repo_info(corpus, owner="alice", repo="tiny", mode="public_evidence",
                                     ref=HEAD, file_selection="auto"))
    assert result["state"] == "unavailable" and result["error"] == "body_budget"
    assert len(corpus.calls) == 3


def test_oversized_path_tree_does_not_recurse_into_another_fallback(corpus):
    corpus.override = lambda r: httpx.Response(200, content=b"x" * (module.BODY_CAP + 1)) if (
        "/git/trees/" in r.url.path and not r.url.params) else None
    result = run(corpus)
    assert result["error"] == "body_budget" and len(corpus.calls) == 4


@pytest.mark.parametrize("status", [302, 403, 429, 500])
def test_http_refusal_is_never_retried_as_path_walk(corpus, status):
    corpus.override = lambda r: httpx.Response(status) if r.url.params.get("recursive") == "1" else None
    result = run(corpus)
    assert result["state"] == "unavailable" and len(corpus.calls) == 3
    assert not result["files"]


def test_quota_zero_on_oversized_recursive_response_stops(corpus):
    corpus.override = lambda r: httpx.Response(200, content=b"x" * (module.BODY_CAP + 1),
        headers={"x-ratelimit-remaining": "0"}) if r.url.params.get("recursive") == "1" else None
    result = run(corpus)
    assert result["error"] == "body_budget" and len(corpus.calls) == 3


def test_quota_zero_during_walk_stops_before_child_request(corpus):
    def override(request):
        if request.url.path.endswith("/git/trees/" + ROOT) and not request.url.params:
            return httpx.Response(200, json={"sha": ROOT, "truncated": False, "tree": corpus.trees[ROOT]},
                                  headers={"x-ratelimit-remaining": "0"})
    corpus.override = override
    result = run(corpus)
    assert result["error"] == "observed_rate_budget" and len(corpus.calls) == 4


def test_request_cap_still_bounds_deep_paths(corpus):
    depth = 14
    for i in range(depth):
        sha = ROOT if i == 0 else f"{i:040x}"
        corpus.trees[sha] = [entry(f"d{i}", f"{i + 1:040x}")]
    path = "/".join([f"d{i}" for i in range(depth)] + ["main.py"])
    result = run(corpus, evidence_files=[{"path": path}])
    assert result["error"] == "budget_exhausted"
    assert len(corpus.calls) == result["budget"]["requests"] == 12
    assert not any("/contents/" in r.url.path for r in corpus.calls)


def test_total_byte_budget_is_not_reset_for_fallback(corpus, monkeypatch):
    monkeypatch.setattr(module, "TOTAL_CAP", module.BODY_CAP)
    result = run(corpus)
    assert result["error"] == "body_budget" and len(corpus.calls) == 3


def test_leaf_blob_integrity_still_checked(corpus):
    corpus.files[PATH]["content"] = base64.b64encode(b"different bytes").decode()
    result = run(corpus)
    assert result["state"] == "partial" and not result["files"]
    assert result["gaps"][0]["error"] == "file_decode_or_integrity_failed"
