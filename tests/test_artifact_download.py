"""#63: trusted API redirect resolution; never follow it or send PAT to CDN."""
import json
from unittest.mock import MagicMock
import httpx
import pytest
from mcp_server.tools.github.client import GitHubClient
from mcp_server.tools.github.actions import download_artifact

URL='https://productionresultssa12.blob.core.windows.net/actions-results/a.zip?sig=OPAQUE&se=2026-11-01'
TOKEN='ghp_TEST_PRIVATE_TOKEN_NOT_REAL'


def transport_client(status=302,location=URL,body=b''):
    requests=[]
    def handler(request):
        requests.append(request)
        assert request.url.host=='api.github.com', 'CDN request must never occur'
        assert request.headers['Authorization']=='Bearer '+TOKEN
        return httpx.Response(status,headers={'Location':location} if location is not None else {},content=body)
    c=GitHubClient(TOKEN);c._client.close()
    c._client=httpx.Client(base_url=c.BASE_URL,transport=httpx.MockTransport(handler),follow_redirects=True)
    return c,requests


def test_real_http_client_no_redirect_follow_or_cdn_auth(caplog):
    c,requests=transport_client()
    result=c.resolve_artifact_download('o','r',7)
    assert result['outcome']=='resolved' and result['download_url']==URL
    assert len(requests)==1 and str(requests[0].url)=='https://api.github.com/repos/o/r/actions/artifacts/7/zip'
    assert TOKEN not in json.dumps(result) and URL not in caplog.text and TOKEN not in caplog.text
    c._client.close()


@pytest.mark.parametrize('url',[
    'http://productionresultssa12.blob.core.windows.net/a?sig=x',
    'https://evil.example/a','https://127.0.0.1/a','https://[::1]/a',
    'https://productionresultssa12.blob.core.windows.net.evil.example/a',
    'https://attacker.blob.core.windows.net/a',
    'https://user:pass@productionresultssa12.blob.core.windows.net/a',
    'https://productionresultssa12.blob.core.windows.net:444/a',
    'https://productionresultssa12.blob.core.windows.net/a#fragment',
    'https://api.github.com/repos/o/r/actions/artifacts/7/zip',
    '/relative','https://productionresultssa12.blob.core.windows.net',
    'https://productionresultssa12.blob.core.windows.net/a?sig='+TOKEN,
    'https://productionresultssa12.blob.core.windows.net/a\\evil',
])
def test_untrusted_location_refused_without_leaking_it(url):
    c,requests=transport_client(location=url)
    data=c.resolve_artifact_download('o','r',7)
    assert data['outcome']=='redirect_rejected' and data['download_url'] is None
    assert url not in json.dumps(data) and TOKEN not in json.dumps(data) and len(requests)==1
    c._client.close()


@pytest.mark.parametrize('host',['objects.githubusercontent.com','pipelines.actions.githubusercontent.com',
                                  'results-receiver.actions.githubusercontent.com'])
def test_known_github_controlled_hosts(host):
    url='https://'+host+'/archive.zip?sig=OPAQUE'
    c,requests=transport_client(location=url)
    assert c.resolve_artifact_download('o','r',7)['download_url']==url
    assert len(requests)==1;c._client.close()


@pytest.mark.parametrize('status',[200,301,307,401,403,404,410,429,500])
def test_non302_never_returns_api_or_error_url(status):
    c,requests=transport_client(status=status,body=(TOKEN+' '+URL).encode())
    data=c.resolve_artifact_download('o','r',7)
    assert data['outcome']!='resolved' and data['http_status']==status
    assert data['download_url'] is None and TOKEN not in json.dumps(data) and URL not in json.dumps(data)
    assert len(requests)==1;c._client.close()


def test_missing_location_refused():
    c,requests=transport_client(location=None)
    assert c.resolve_artifact_download('o','r',7)['outcome']=='redirect_rejected'
    c._client.close()


def art(id=7,name='dist',**kw):
    row={'id':id,'name':name,'expired':False,'size_in_bytes':1234,'created_at':'2026-10-11',
         'expires_at':'2026-11-11','workflow_run':{'id':99},
         'archive_download_url':'https://evil.example/untrusted-metadata'}
    row.update(kw);return row


def mock_client(row=None,pages=None):
    c=MagicMock();calls=[]
    def request(method,url,**kw):
        calls.append((method,url,kw))
        data=pages[kw['params']['page']-1] if pages is not None else (art() if row is None else row)
        return httpx.Response(200,json=data)
    c._request.side_effect=request
    c.resolve_artifact_download.return_value={'outcome':'resolved','download_url':URL,'http_status':302,'error':None}
    return c,calls


def parse(output):return json.loads(next(l[10:] for l in output.splitlines() if l.startswith('metadata: ')))
def invoke(c,**kw):return parse(download_artifact(c,owner='o',repo='r',**kw))


def test_id_form_resolves_not_metadata_archive_url():
    c,calls=mock_client()
    data=invoke(c,artifact_id=7)
    assert data['outcome']=='resolved' and data['download_url']==URL and data['artifact_id']==7
    assert data['artifact_expires_at']=='2026-11-11' and data['url_expires_at'] is None
    assert data['requires_github_authorization'] is False
    assert 'evil.example' not in json.dumps(data)
    c.resolve_artifact_download.assert_called_once_with('o','r',7)


def test_name_run_lookup_paginated_and_exact():
    pages=[{'total_count':2,'artifacts':[art(id=8,name='other')]},
           {'total_count':2,'artifacts':[art()]}]
    c,calls=mock_client(pages=pages)
    data=invoke(c,name='dist',run_id=99)
    assert data['outcome']=='resolved' and data['artifact_id']==7 and data['lookup_complete'] is True
    assert [kw['params']['page'] for m,u,kw in calls]==[1,2]
    assert all(u=='/repos/o/r/actions/runs/99/artifacts' for m,u,kw in calls)


def test_duplicate_name_ambiguous_never_select_first():
    c,calls=mock_client(pages=[{'total_count':2,'artifacts':[art(),art(id=8)]}])
    data=invoke(c,name='dist',run_id=99)
    assert data['outcome']=='ambiguous' and data['candidate_ids']==[7,8]
    c.resolve_artifact_download.assert_not_called()


def test_lookup_cap_incomplete_no_resolution():
    c,calls=mock_client(pages=[{'total_count':2,'artifacts':[art()]}])
    data=invoke(c,name='dist',run_id=99,max_pages=1)
    assert data['outcome']=='lookup_incomplete' and not data['lookup_complete']
    c.resolve_artifact_download.assert_not_called()


def test_expired_no_download_request():
    c,calls=mock_client(row=art(expired=True))
    assert invoke(c,artifact_id=7)['outcome']=='expired'
    c.resolve_artifact_download.assert_not_called()


@pytest.mark.parametrize('row',[{},art(id=8),art(expired=None),art(size_in_bytes=True)])
def test_malformed_metadata_not_success(row):
    c,calls=mock_client(row=row)
    assert invoke(c,artifact_id=7)['outcome']=='unknown'
    c.resolve_artifact_download.assert_not_called()


@pytest.mark.parametrize('kw',[{}, {'name':'dist'}, {'artifact_id':True},{'artifact_id':-1},
                               {'name':'dist','run_id':True}, {'artifact_id':7,'max_pages':True},
                               {'artifact_id':7,'max_pages':21}])
def test_invalid_inputs_before_api(kw):
    c,calls=mock_client()
    assert invoke(c,**kw)['outcome']=='invalid_input' and not calls
    c.resolve_artifact_download.assert_not_called()


def test_api_error_no_raw_token_or_body():
    c,calls=mock_client();c._request.side_effect=RuntimeError('HTTP error 403 '+TOKEN)
    assert invoke(c,artifact_id=7)['outcome']=='unknown'
    assert TOKEN not in download_artifact(c,owner='o',repo='r',artifact_id=7)


def test_not_found_complete_lookup():
    c,calls=mock_client(pages=[{'total_count':0,'artifacts':[]}])
    data=invoke(c,name='dist',run_id=99)
    assert data['outcome']=='not_found' and data['lookup_complete']
    c.resolve_artifact_download.assert_not_called()


def test_response_body_is_not_consumed_even_for_200_zip():
    state={'closed':False}
    class UnreadBody(httpx.SyncByteStream):
        def __iter__(self):
            raise AssertionError('Download resolver must not read ZIP/error bodies')
            yield b''
        def close(self):state['closed']=True
    c=GitHubClient(TOKEN);c._client.close()
    c._client=httpx.Client(base_url=c.BASE_URL,transport=httpx.MockTransport(
        lambda req:httpx.Response(200,stream=UnreadBody())),follow_redirects=True)
    data=c.resolve_artifact_download('o','r',7)
    assert data['outcome']=='unexpected_response' and state['closed']
    c._client.close()


def test_transport_error_never_reflects_header_or_location():
    c=GitHubClient(TOKEN);c._client.close()
    def handler(req):raise RuntimeError(TOKEN+' '+URL)
    c._client=httpx.Client(base_url=c.BASE_URL,transport=httpx.MockTransport(handler))
    data=c.resolve_artifact_download('o','r',7)
    assert data['outcome']=='unknown' and data['error']=='download_request_failed'
    assert TOKEN not in json.dumps(data) and URL not in json.dumps(data)
    c._client.close()


@pytest.mark.parametrize('kwargs',[{'owner':'..','repo':'r','artifact_id':7},
                                   {'owner':'o','repo':'../r','artifact_id':7},
                                   {'owner':'o','repo':'r','artifact_id':True}])
def test_client_direct_identity_validation(kwargs):
    c,requests=transport_client()
    assert c.resolve_artifact_download(**kwargs)['outcome']=='invalid_input' and not requests
    c._client.close()


@pytest.mark.parametrize('pages',[
    [{'total_count':True,'artifacts':[]}],
    [{'total_count':2,'artifacts':[]}],
    [{'total_count':1,'artifacts':['bad']}],
    [{'total_count':2,'artifacts':[art()]},{'total_count':2,'artifacts':[art()]}],
    [{'total_count':2,'artifacts':[art()]},{'total_count':3,'artifacts':[art(id=8)]}],
])
def test_malformed_or_changing_lookup_no_resolution(pages):
    c,calls=mock_client(pages=pages)
    assert invoke(c,name='dist',run_id=99)['outcome']=='unknown'
    c.resolve_artifact_download.assert_not_called()


def test_foreign_run_refused():
    c,calls=mock_client(row=art(workflow_run={'id':100}))
    assert invoke(c,artifact_id=7,run_id=99)['outcome']=='unknown'
    c.resolve_artifact_download.assert_not_called()


def test_ambiguous_names_cap_candidate_ids():
    c,calls=mock_client(pages=[{'total_count':25,'artifacts':[art(id=i) for i in range(1,26)]}])
    data=invoke(c,name='dist',run_id=99)
    assert data['outcome']=='ambiguous' and len(data['candidate_ids'])==20 and data['candidates_truncated']
    c.resolve_artifact_download.assert_not_called()


def test_expiry_metadata_is_not_download_link_expiry():
    c,calls=mock_client()
    data=invoke(c,artifact_id=7)
    assert data['url_expires_at'] is None and data['artifact_expires_at']=='2026-11-11'
    assert data['sensitive_download_url'] is True


def test_mcp_transport_schema_and_resolved_result(monkeypatch):
    import mcp_server.server as server
    c,calls=mock_client()
    monkeypatch.setattr(server,'GitHubClient',lambda token:c)
    response=server.app.test_client().post('/mcp',headers={'Authorization':'Bearer test-not-a-real-token'},
        json={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{
            'name':'download_artifact','arguments':{'owner':'o','repo':'r','artifact_id':7}}})
    body=response.get_json();assert 'error' not in body
    data=parse(body['result']['content'][0]['text'])
    assert data['outcome']=='resolved' and data['download_url']==URL
    schema=download_artifact._mcp_tool.to_mcp_tool_definition()['inputSchema']
    assert schema['required']==['owner','repo']
    assert schema['properties']['max_pages']['type']=='integer'
