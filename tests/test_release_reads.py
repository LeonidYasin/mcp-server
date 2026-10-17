"""Release read-only metadata: fixed authority, no writes, bounded I/O and output."""
import json
import httpx
import pytest

from mcp_server.tools.github.client import GitHubClient
from mcp_server.tools.github import release_reads as reads

RELEASE = {"id": 17, "tag_name": "v1/preview", "name": "Тест", "draft": True,
           "prerelease": False, "target_commitish": "main", "created_at": "2026-01-01T00:00:00Z",
           "published_at": None, "html_url": "https://github.com/me/repo/releases/tag/v1%2Fpreview"}
ASSET = {"id": 23, "name": "input.zip", "size": 123, "state": "uploaded",
         "content_type": "application/zip", "digest": "sha256:" + "a" * 64,
         "browser_download_url": "https://github.com/me/repo/releases/download/v1/input.zip"}


@pytest.fixture
def client_factory():
    clients = []
    def make(payload=None, status=200, headers=None, handler=None, content=None):
        calls = []
        def transport(request):
            calls.append(request)
            assert request.method == "GET"
            assert request.url.host == "api.github.com"
            if handler:
                return handler(request)
            if content is not None:
                return httpx.Response(status, content=content, headers=headers)
            return httpx.Response(status, json=payload, headers=headers)
        c = GitHubClient("SYNTHETIC-SECRET-NOT-REAL")
        c._client.close()
        c._client = httpx.Client(transport=httpx.MockTransport(transport))
        c._request = lambda *a, **k: pytest.fail("legacy redirect/error transport used")
        clients.append(c)
        return c, calls
    yield make
    for c in clients:
        c._client.close()


def get(c, **kw):
    return json.loads(reads.get_release(c, owner="me", repo="repo", **kw))


def assets(c, **kw):
    return json.loads(reads.list_release_assets(c, owner="me", repo="repo", release_id=17, **kw))


def test_get_by_id_preserves_draft_and_omits_body_assets(client_factory):
    c, calls = client_factory({**RELEASE, "body": "huge private description", "assets": [ASSET]})
    r = get(c, release_id=17)
    assert r["ok"] and r["release"]["draft"] is True
    assert r["release"]["release_id"] == 17 and r["release"]["name"] == "Тест"
    assert r["assets_included"] is False and "body" not in r["release"]
    assert calls[0].url.path == "/repos/me/repo/releases/17" and len(calls) == 1


def test_get_tag_slash_is_one_encoded_segment(client_factory):
    c, calls = client_factory(RELEASE)
    assert get(c, tag="v1/preview")["ok"]
    assert calls[0].url.raw_path == b"/repos/me/repo/releases/tags/v1%2Fpreview"


@pytest.mark.parametrize("kwargs", [{}, {"tag": "x", "release_id": 17}, {"release_id": True},
    {"release_id": 0}, {"release_id": "17"}, {"tag": ""}, {"tag": ".."}, {"tag": "a/../b"},
    {"tag": "a\nb"}, {"tag": " "}, {"tag": 12}, {"tag": "x" * 1025}])
def test_selector_validation_makes_no_request(client_factory, kwargs):
    c, calls = client_factory(RELEASE)
    assert get(c, **kwargs)["error"] == "invalid_input" and not calls


@pytest.mark.parametrize("owner,repo", [("../evil", "repo"), ("x?token=a", "repo"),
    ("me", ".."), ("me", "repo/../../user"), (None, "repo"), ("me", "x" * 101)])
def test_identity_validation(client_factory, owner, repo):
    c, calls = client_factory(RELEASE)
    r = json.loads(reads.get_release(c, owner=owner, repo=repo, release_id=17))
    assert r["error"] == "invalid_input" and not calls


@pytest.mark.parametrize("status,code", [(301,"redirect_refused"),(302,"redirect_refused"),
    (401,"authentication_failed"),(403,"access_denied_or_rate_limited"),
    (404,"not_found_or_inaccessible"),(429,"rate_limited"),(500,"upstream_failure")])
def test_http_refusals_do_not_follow_or_leak(client_factory, status, code):
    c, calls = client_factory(status=status, content=b"SYNTHETIC-SECRET-NOT-REAL", headers={"Location":"https://evil.invalid/leak"})
    raw = reads.get_release(c, owner="me", repo="repo", release_id=17)
    r = json.loads(raw)
    assert r == {"ok":False,"error":code,"http_status":status}
    assert "SECRET" not in raw and "evil.invalid" not in raw and len(calls)==1


@pytest.mark.parametrize("payload", [[],None,{}, {**RELEASE,"id":18}, {**RELEASE,"id":True},
    {**RELEASE,"draft":"false"}, {**RELEASE,"name":{}}, {**RELEASE,"tag_name":None}])
def test_bad_release_metadata(client_factory, payload):
    c,_=client_factory(payload)
    assert get(c, release_id=17)["error"] == "invalid_api_response"


def test_tag_mismatch_refused(client_factory):
    c,_=client_factory(RELEASE)
    assert get(c,tag="v2")["error"] == "invalid_api_response"


@pytest.mark.parametrize("url", ["https://evil.invalid/x", "https://github.com/me/repo/releases/tag/x?token=secret",
    "http://github.com/me/repo/releases/tag/x", "https://github.com@evil.invalid/me/repo/releases/x"])
def test_untrusted_metadata_url_is_omitted(client_factory,url):
    c,_=client_factory({**RELEASE,"html_url":url})
    assert get(c,release_id=17)["release"]["html_url"] is None


def test_assets_single_page_structured_ids_and_github_digest(client_factory):
    c,calls=client_factory([ASSET])
    r=assets(c,limit=2,page=3)
    assert r["ok"] and r["assets"][0]["asset_id"]==23
    assert r["assets"][0]["digest_source"]=="github" and r["assets"][0]["size"]==123
    assert r["pagination"]=={"scope":"single_page","page":3,"per_page":2,"returned":1,"has_next":False,"next_page":None}
    assert r["total_count"] is None and r["asset_bytes_fetched"] is False
    assert str(calls[0].url).endswith('/releases/17/assets?per_page=2&page=3')


def test_missing_digest_not_invented_and_full_page_unknown(client_factory):
    c,_=client_factory([{**ASSET,"digest":None}])
    r=assets(c,limit=1)
    assert r["assets"][0]["digest"] is None and r["assets"][0]["digest_source"] is None
    assert r["pagination"]["has_next"] is None


def test_link_next_is_never_followed(client_factory):
    c,calls=client_factory([ASSET],headers={"Link":'<https://evil.invalid/>; rel="next"'})
    r=assets(c,limit=1,page=2)
    assert r["pagination"]["next_page"]==3 and len(calls)==1
    assert "evil.invalid" not in json.dumps(r)


@pytest.mark.parametrize("kwargs", [{"limit":0},{"limit":101},{"limit":True},{"page":0},{"page":"2"}])
def test_page_bounds(client_factory,kwargs):
    c,calls=client_factory([])
    assert assets(c,**kwargs)["error"]=="invalid_input" and not calls


@pytest.mark.parametrize("payload", [{},[{}],[{**ASSET,"id":True}], [{**ASSET,"size":-1}],
    [{**ASSET,"size":True}], [ASSET,ASSET], [{**ASSET,"name":"a"*257}]])
def test_bad_assets_refuse_whole_page(client_factory,payload):
    c,_=client_factory(payload)
    assert assets(c)["error"]=="invalid_api_response"


def test_asset_rows_over_requested_page_fail(client_factory):
    c,_=client_factory([ASSET,{**ASSET,"id":24}])
    assert assets(c,limit=1)["error"]=="invalid_api_response"


@pytest.mark.parametrize("content", [b'not-json',b'[]'*3,b'"SYNTHETIC-SECRET-NOT-REAL"'])
def test_invalid_response_is_sanitized(client_factory,content):
    c,_=client_factory(content=content)
    r=get(c,release_id=17)
    assert r["error"]=="invalid_api_response" and "SECRET" not in json.dumps(r)


def test_response_limit(client_factory,monkeypatch):
    monkeypatch.setattr(reads,"MAX_RESPONSE_BYTES",32)
    c,_=client_factory(RELEASE)
    assert get(c,release_id=17)["error"]=="response_too_large"


def test_output_limit(client_factory,monkeypatch):
    monkeypatch.setattr(reads,"MAX_OUTPUT_BYTES",100)
    c,_=client_factory([ASSET])
    assert assets(c)["error"]=="output_too_large_reduce_page_size"


@pytest.mark.parametrize("exc,code", [(httpx.ReadTimeout("SECRET"),"request_timeout"),(RuntimeError("SECRET"),"request_failed")])
def test_transport_errors_sanitized(client_factory,exc,code):
    def fail(request): raise exc
    c,_=client_factory(handler=fail)
    assert get(c,release_id=17)=={"ok":False,"error":code,"http_status":None}


def test_legacy_release_functions_unchanged(client_factory):
    from mcp_server.tools.github.releases import list_releases,create_release,get_latest_release
    assert all(callable(f) for f in (list_releases,create_release,get_latest_release))


def test_invalid_unicode_refused_without_traceback(client_factory):
    c,_=client_factory(content=json.dumps({**RELEASE,"name":"\ud800"}).encode())
    assert get(c,release_id=17)["error"]=="invalid_api_response"


def test_trusted_metadata_urls_preserved(client_factory):
    c,_=client_factory(RELEASE)
    assert get(c,release_id=17)["release"]["html_url"]==RELEASE["html_url"]
    c,_=client_factory([ASSET])
    assert assets(c)["assets"][0]["browser_download_url"]==ASSET["browser_download_url"]
