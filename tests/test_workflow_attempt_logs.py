"""#69 part 2: attempt-only transport, honest combined fallback and bounded queries."""
import io
import json
import logging
import stat
import zipfile
from unittest.mock import MagicMock

import httpx
import pytest
from mcp_server.tools.github import workflow_attempt_logs as logs
from mcp_server.tools.github import workflow_log_archive as archive
from mcp_server.tools.github.client import GitHubClient
from mcp_server.tools.github.workflow_runs import grep_run_logs, read_run_logs_offset, get_run_logs_by_step
from mcp_server.tools.github.workflow_logs_grep import grep_workflow_logs

URL='https://productionresultssa12.blob.core.windows.net/logs.zip?sig=OPAQUE_SECRET'
TOKEN='ghp_TEST_ONLY_NOT_REAL'


def zip_bytes(files):
    raw=io.BytesIO()
    with zipfile.ZipFile(raw,'w',zipfile.ZIP_DEFLATED) as z:
        for name,text in files.items():z.writestr(name,text)
    return raw.getvalue()


def transport(monkeypatch, api_status=302, location=URL, cdn_status=200, raw=None, headers=None):
    requests=[];real=httpx.Client
    def api(req):
        requests.append(req)
        assert req.headers['Authorization']=='Bearer '+TOKEN
        return httpx.Response(api_status,headers={'Location':location} if location is not None else {},content=b'body ignored '+TOKEN.encode())
    def cdn(req):
        requests.append(req)
        assert 'Authorization' not in req.headers and 'Cookie' not in req.headers
        return httpx.Response(cdn_status,content=raw if raw is not None else zip_bytes({'build/1_Compile.txt':'ok'}),headers=headers)
    client=GitHubClient(TOKEN);client._client.close()
    client._client=real(base_url=client.BASE_URL,transport=httpx.MockTransport(api),cookies={'secret':'cookie'})
    monkeypatch.setattr(archive.httpx,'Client',lambda **kw: real(transport=httpx.MockTransport(cdn),**kw))
    return client,requests


def test_attempt_url_no_cdn_auth_or_cookies_and_signed_query_not_logged(monkeypatch,caplog):
    c,requests=transport(monkeypatch)
    with caplog.at_level(logging.INFO,logger='httpx'):
        files=archive.download(c,'o','r',99,2)
    assert files=={'build/1_Compile.txt':'ok'}
    assert len(requests)==2
    assert requests[0].url.path=='/repos/o/r/actions/runs/99/attempts/2/logs'
    assert 'OPAQUE_SECRET' not in caplog.text and TOKEN not in caplog.text
    c._client.close()


@pytest.mark.parametrize('destination',[
    'http://productionresultssa12.blob.core.windows.net/a','https://evil.example/a',
    'https://127.0.0.1/a','https://productionresultssa12.blob.core.windows.net.evil/a',
    'https://attacker.blob.core.windows.net/a','https://u:p@objects.githubusercontent.com/a',
    'https://objects.githubusercontent.com:444/a','https://objects.githubusercontent.com/a#x',
    'https://objects.githubusercontent.com/a?sig='+TOKEN,'/relative',None,
])
def test_redirect_rejected_before_cdn_request(monkeypatch,destination):
    c,requests=transport(monkeypatch,location=destination)
    with pytest.raises(archive.LogError,match='redirect_rejected'):
        archive.download(c,'o','r',99,1)
    assert len(requests)==1;c._client.close()


@pytest.mark.parametrize('status',[200,301,307,401,403,404,410,429,500])
def test_api_refusal_not_empty_success(monkeypatch,status):
    c,requests=transport(monkeypatch,api_status=status)
    with pytest.raises(archive.LogError) as error:archive.download(c,'o','r',99,1)
    assert error.value.code=='logs_unavailable' and error.value.status==status
    assert len(requests)==1;c._client.close()


def test_cdn_redirect_not_followed(monkeypatch):
    c,requests=transport(monkeypatch,cdn_status=302,headers={'Location':'https://evil.example/a'})
    with pytest.raises(archive.LogError,match='logs_download_failed'):archive.download(c,'o','r',99,2)
    assert len(requests)==2;c._client.close()


def test_size_headers_and_stream_cap(monkeypatch):
    c,requests=transport(monkeypatch,headers={'Content-Length':str(archive.MAX_DOWNLOAD+1)})
    with pytest.raises(archive.LogError,match='archive_limit_exceeded'):archive.download(c,'o','r',99,2)
    c._client.close()


@pytest.mark.parametrize('name',['../secret.txt','/absolute.txt','x/../../secret.txt','x\\secret.txt','x:secret.txt','x.bin'])
def test_unsafe_zip_entry_refused_no_extraction(name):
    with pytest.raises(archive.LogError,match='archive_invalid'):archive.unpack(zip_bytes({name:'hello'}))


def test_duplicate_and_symlink_entries_refused():
    for kind in ('duplicate','symlink'):
        raw=io.BytesIO()
        with zipfile.ZipFile(raw,'w') as z:
            if kind=='duplicate':
                z.writestr('x.txt','a')
                with pytest.warns(UserWarning):z.writestr('x.txt','b')
            else:
                info=zipfile.ZipInfo('x.txt');info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16
                z.writestr(info,'/etc/passwd')
        with pytest.raises(archive.LogError,match='archive_invalid'):archive.unpack(raw.getvalue())


def test_zip_bomb_and_file_count_budget(monkeypatch):
    monkeypatch.setattr(archive,'MAX_FILE',20)
    with pytest.raises(archive.LogError,match='archive_limit_exceeded'):archive.unpack(zip_bytes({'x.txt':'a'*21}))
    monkeypatch.setattr(archive,'MAX_FILES',1)
    with pytest.raises(archive.LogError,match='archive_limit_exceeded'):archive.unpack(zip_bytes({'x.txt':'a','y.txt':'b'}))


@pytest.mark.parametrize('raw',[b'plain text',b'PKbroken',b''])
def test_bad_archive_not_decoded_as_successful_plain_text(raw):
    with pytest.raises(archive.LogError,match='archive_invalid'):archive.unpack(raw)


def mock_query(monkeypatch,files=None,identity_error=None):
    c=MagicMock();c._headers={'Authorization':'Bearer '+TOKEN}
    data={'complete':True,'run_id':99,'run_attempt':2,'head_sha':'a'*40,'selection':'explicit',
          'status':'completed','conclusion':'failure','completed_at':None}
    if identity_error:data.update(complete=False,error=identity_error)
    snap=MagicMock(return_value=data);load=MagicMock(return_value=files if files is not None else {'build/1_Compile.txt':'before\nerror ONE\nafter'})
    monkeypatch.setattr(logs,'snapshot',snap);monkeypatch.setattr(logs,'download',load)
    return c,snap,load


def invoke(c,**kw):return grep_run_logs(c,owner='o',repo='r',run_id=99,run_attempt=2,pattern='error',**kw)


def test_grep_attempt_and_metadata(monkeypatch):
    c,snap,load=mock_query(monkeypatch);data=invoke(c,step_name='Compile')
    assert data['complete'] and data['run_attempt']==2 and data['matches']==1
    assert data['segments'][0]['job']=='build' and data['segments'][0]['step']=='Compile'
    load.assert_called_once_with(c,'o','r',99,2)


def test_combined_logs_explicit_unsupported_not_no_files(monkeypatch):
    c,_,_=mock_query(monkeypatch,{'0_build.txt':'error 4KB\nerror 16KB','build/system.txt':'runner'})
    data=invoke(c,job_name='build',step_name='16KB')
    assert data['error']=='step_filter_unsupported' and not data['complete']
    assert data['fallback']['omit']=='step_name' and data['fallback']['run_attempt']==2
    broad=invoke(c,job_name='build');assert broad['matches']==2 and broad['complete']


def test_step_filter_does_not_match_job_name(monkeypatch):
    c,_,_=mock_query(monkeypatch,{'Compile-job/1_Setup.txt':'error'})
    assert invoke(c,step_name='Compile')['error']=='no_matching_log_files'


def test_same_step_across_jobs_context_does_not_cross_boundary(monkeypatch):
    c,_,_=mock_query(monkeypatch,{'a/1_Compile.txt':'a\nerror A','b/1_Compile.txt':'B\nerror B'})
    data=invoke(c,step_name='Compile',context=20)
    assert data['matches']==2 and len(data['segments'])==2
    assert all(len(s['lines'])==2 for s in data['segments'])
    scoped=invoke(c,step_name='Compile',job_name='a');assert scoped['matches']==1


def test_zero_hits_empty_files_and_no_matching_files_are_distinct(monkeypatch):
    c,_,_=mock_query(monkeypatch,{'a/1_Setup.txt':'hello'})
    assert invoke(c)['error']=='no_matching_text'
    assert invoke(c,step_name='missing')['error']=='no_matching_log_files'
    c,_,_=mock_query(monkeypatch,{})
    assert invoke(c)['error']=='empty_archive'


def test_identity_unavailable_never_downloads_latest(monkeypatch):
    c,_,load=mock_query(monkeypatch,identity_error='run_identity_unavailable_or_invalid')
    assert invoke(c)['error']=='run_identity_unavailable_or_invalid';load.assert_not_called()


def test_api404_vs_empty_match(monkeypatch):
    c,_,load=mock_query(monkeypatch);load.side_effect=archive.LogError('logs_unavailable',404)
    data=invoke(c);assert data['http_status']==404 and not data['complete'] and data['error']=='logs_unavailable'


@pytest.mark.parametrize('kw',[{'context':21},{'context':True},{'max_lines':0},{'max_chars':65537},
    {'max_matches':0},{'offset':-1},{'pattern':'x'*257},{'case_sensitive':'yes'},{'step_name':''}])
def test_invalid_inputs_no_source_calls(monkeypatch,kw):
    c,snap,load=mock_query(monkeypatch)
    data=logs.query(c,'grep',owner='o',repo='r',run_id=99,**({'pattern':'error'}|kw))
    assert data['error']=='invalid_input';snap.assert_not_called();load.assert_not_called()


def test_invalid_regex_before_api(monkeypatch):
    c,snap,load=mock_query(monkeypatch)
    assert logs.query(c,'grep',owner='o',repo='r',run_id=99,pattern='[')['error']=='invalid_pattern'
    snap.assert_not_called()


def test_global_line_char_match_limits(monkeypatch):
    c,_,_=mock_query(monkeypatch,{'a/1_X.txt':'error '+'x'*100+'\nerror TWO','b/1_X.txt':'error THREE'})
    data=invoke(c,max_lines=1,max_chars=7,max_matches=1)
    assert data['complete'] and data['output_truncated'] and data['matches']==3 and data['returned_lines']==1
    assert sum(len(l['text']) for s in data['segments'] for l in s['lines'])<=7


def test_redaction_before_search_and_output(monkeypatch):
    c,_,_=mock_query(monkeypatch,{'a/1_X.txt':'error '+TOKEN+' '+URL})
    data=invoke(c);text=json.dumps(data)
    assert TOKEN not in text and 'OPAQUE_SECRET' not in text and '[redacted]' in text


def test_offset_and_tail_compatibility(monkeypatch):
    c,_,_=mock_query(monkeypatch,{'a/1_X.txt':'one\ntwo\nthree'})
    data=read_run_logs_offset(c,owner='o',repo='r',run_id=99,offset=1,limit=1)
    assert data['logs']==['two'] and data['output_truncated']
    data=get_run_logs_by_step(c,owner='o',repo='r',run_id=99,step_name='X',max_lines=1,direction='tail')
    assert data['logs']==['three'] and data['run_attempt']==2


def test_start_marker_missing_not_success(monkeypatch):
    c,_,_=mock_query(monkeypatch)
    data=get_run_logs_by_step(c,owner='o',repo='r',run_id=99,step_name='Compile',start_time='missing')
    assert data['error']=='start_time_not_found' and data['returned_lines']==0


def test_legacy_grep_alias_and_path_filter(monkeypatch):
    c,_,_=mock_query(monkeypatch)
    data=grep_workflow_logs(c,owner='o',repo='r',run_id=99)
    assert data['matches']==1 and data['run_attempt']==2
    assert grep_workflow_logs(c,owner='o',repo='r',run_id=99,file_filter='build')['matches']==1
    assert grep_workflow_logs(c,owner='o',repo='r',run_id=99,file_filter='missing')['error']=='no_matching_log_files'


def test_catastrophic_regex_is_bounded_worker_timeout(monkeypatch):
    c,_,_=mock_query(monkeypatch,{'a/1_X.txt':'a'*10000+'!'})
    data=logs.query(c,'grep',owner='o',repo='r',run_id=99,pattern='(a+)+$')
    assert data['error']=='search_timeout' and data['complete'] is False



def test_real_attempt_resolution_then_exact_download_endpoint(monkeypatch):
    from test_workflow_attempts import client
    from mcp_server.tools.github.workflow_attempts import snapshot
    monkeypatch.setattr(logs,'snapshot',snapshot)
    c,calls=client();c._headers={}
    load=MagicMock(return_value={'build/1_Compile.txt':'error attempt'})
    monkeypatch.setattr(logs,'download',load)
    data=read_run_logs_offset(c,owner='o',repo='r',run_id=99,limit=1)
    assert data['run_attempt']==2 and data['selection']=='latest_at_resolution'
    assert calls[0][1]=='/repos/o/r/actions/runs/99'
    assert all('/attempts/2' in url for method,url,kw in calls[1:])
    load.assert_called_once_with(c,'o','r',99,2)
    c,calls=client();c._headers={};load.reset_mock()
    data=read_run_logs_offset(c,owner='o',repo='r',run_id=99,run_attempt=1,limit=1)
    assert data['run_attempt']==1 and all('/attempts/1' in url for method,url,kw in calls)
    load.assert_called_once_with(c,'o','r',99,1)


def test_stream_actual_bytes_bound_without_content_length(monkeypatch):
    c,requests=transport(monkeypatch,raw=b'X'*200)
    monkeypatch.setattr(archive,'MAX_DOWNLOAD',100)
    with pytest.raises(archive.LogError,match='archive_limit_exceeded'):
        archive.download(c,'o','r',99,1)
    c._client.close()


def test_job_filter_does_not_match_step_name():
    assert logs.segments({'job/1_Compile.txt':'error'},job_name='Compile')==[]


def test_partial_mixed_archive_does_not_silently_skip_combined_job(monkeypatch):
    c,_,_=mock_query(monkeypatch,{'a/1_Compile.txt':'error A','0_b.txt':'error B'})
    assert invoke(c,step_name='Compile')['error']=='step_filter_unsupported'
    scoped=invoke(c,step_name='Compile',job_name='a')
    assert scoped['complete'] and scoped['matches']==1


def test_process_failure_never_successful_empty(monkeypatch):
    c,_,_=mock_query(monkeypatch)
    monkeypatch.setattr(logs.subprocess,'run',MagicMock(return_value=MagicMock(returncode=1)))
    assert invoke(c)['error']=='search_failed'
