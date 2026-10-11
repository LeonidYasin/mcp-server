"""#62 regression tests. All merge writes are mocked, never live GitHub mutations."""
import json
from copy import deepcopy
from unittest.mock import MagicMock

import pytest
from mcp_server.tools.github import pull_requests as pr

HEAD='a'*40
BASE='b'*40
MERGED='c'*40
ARGS={'owner':'o','repo':'r','number':1}


def snapshot(**extra):
    row=dict(number=1,title='test',state='open',merged=False,draft=False,
             mergeable=True,mergeable_state='clean',merge_commit_sha=MERGED,
             created_at='2026-10-01T00:00:00Z',updated_at='2026-10-02T00:00:00Z',
             closed_at=None,merged_at=None,html_url='https://github.com/o/r/pull/1',
             head={'sha':HEAD,'ref':'fix','repo':{'full_name':'o/r'}},
             base={'sha':BASE,'ref':'main','repo':{'full_name':'o/r'}},user={'login':'o'})
    row.update(extra)
    return row


def make_client(*,row=None,repo=None,put=None,put_error=None,read_error=False):
    calls=[];client=MagicMock()
    row=snapshot() if row is None else row
    repo={'allow_merge_commit':True,'allow_squash_merge':True,'allow_rebase_merge':False} if repo is None else repo
    def request(method,url,**kw):
        calls.append((method,url,kw))
        if method=='PUT':
            if put_error: raise put_error
            return MagicMock(json=lambda: {'merged':True,'sha':MERGED,'message':'merged'} if put is None else put)
        if read_error: raise RuntimeError('HTTP error 403: Bearer ghp_PRIVATE')
        data=repo if url=='/repos/o/r' else row
        return MagicMock(json=lambda:deepcopy(data))
    client._request.side_effect=request
    return client,calls


def parse(text):
    return json.loads(next(l[10:] for l in text.splitlines() if l.startswith('metadata: ')))


@pytest.fixture(autouse=True)
def checks(monkeypatch):
    def status(client,owner,repo,sha,**kwargs):
        return 'metadata: '+json.dumps({'head_sha':sha,'aggregate_state':'success','complete':True,
                                      'counts':{'success':1},'merge_eligibility':'not_evaluated'})
    monkeypatch.setattr(pr,'get_commit_status',status,raising=False)


def merge(client,**extra):
    return parse(pr.merge_pull_request(client=client,**ARGS,**{'expected_head_sha':HEAD,**extra}))


def writes(calls): return [c for c in calls if c[0]!='GET']


def test_get_exposes_full_metadata_without_inventing_merge_eligibility():
    client,_=make_client()
    data=parse(pr.get_pull_request(client=client,**ARGS))
    assert data['head']['sha']==HEAD and data['base']['sha']==BASE
    assert data['draft'] is False and data['mergeable'] is True
    assert data['mergeable_state']=='clean' and data['merge_commit_sha']==MERGED
    assert data['html_url']=='https://github.com/o/r/pull/1'
    assert data['allowed_merge_methods']==['merge','squash']
    assert data['merge_eligibility']=='not_evaluated'


@pytest.mark.parametrize('value',[None,False,True])
def test_mergeable_tristate_not_collapsed(value):
    client,_=make_client(row=snapshot(mergeable=value))
    assert parse(pr.get_pull_request(client=client,**ARGS))['mergeable'] is value


def test_closed_not_merged_differs_from_merged():
    client,_=make_client(row=snapshot(state='closed',merged=False))
    data=parse(pr.get_pull_request(client=client,**ARGS))
    assert data['state']=='closed' and data['merged'] is False
    client,calls=make_client(row=snapshot(state='closed',merged=False))
    assert merge(client)['outcome']=='closed'
    assert not writes(calls)


def test_new_head_returns_conflict_without_put():
    row=snapshot();row['head']['sha']=BASE
    client,calls=make_client(row=row)
    data=merge(client)
    assert data['outcome']=='head_conflict' and data['http_status']==409
    assert data['head_sha']==BASE and not writes(calls)


@pytest.mark.parametrize('guard',[None,'abc','z'*40,True])
def test_guard_required_and_validated_before_reads(guard):
    client,calls=make_client()
    data=merge(client,expected_head_sha=guard)
    assert data['outcome']=='invalid_input' and not calls


@pytest.mark.parametrize('method',['bad','',None,True])
def test_invalid_method_rejected_before_reads(method):
    client,calls=make_client()
    assert merge(client,merge_method=method)['outcome']=='invalid_input'
    assert not calls


def test_disallowed_repo_method_no_put():
    client,calls=make_client()
    assert merge(client,merge_method='rebase')['outcome']=='method_not_allowed'
    assert not writes(calls)


def test_unknown_repo_policy_no_put():
    client,calls=make_client(repo={})
    assert merge(client)['outcome']=='policy_unknown' and not writes(calls)


@pytest.mark.parametrize('row,outcome',[(snapshot(draft=True),'draft'),(snapshot(draft=None),'preflight_unknown'),
                                     (snapshot(mergeable=None),'mergeability_unknown'),
                                     (snapshot(mergeable=False),'not_mergeable')])
def test_unsafe_pr_state_no_put(row,outcome):
    client,calls=make_client(row=row)
    assert merge(client)['outcome']==outcome and not writes(calls)


@pytest.mark.parametrize('state,complete',[('failure',True),('pending',True),('unknown',True),('success',False)])
def test_non_success_checks_no_put(monkeypatch,state,complete):
    monkeypatch.setattr(pr,'get_commit_status',lambda *a,**kw:'metadata: '+json.dumps(
        {'head_sha':HEAD,'aggregate_state':state,'complete':complete}))
    client,calls=make_client()
    assert merge(client)['outcome']=='checks_not_ready' and not writes(calls)


def test_foreign_checks_sha_not_trusted(monkeypatch):
    monkeypatch.setattr(pr,'get_commit_status',lambda *a,**kw:'metadata: '+json.dumps(
        {'head_sha':BASE,'aggregate_state':'success','complete':True}))
    client,calls=make_client()
    assert merge(client)['outcome']=='checks_not_ready' and not writes(calls)


def test_guard_payload_and_precise_success_sha():
    client,calls=make_client()
    data=merge(client,merge_method='squash',commit_title='Title',commit_message='Body')
    assert data['merged'] is True and data['sha']==MERGED and data['outcome']=='merged'
    assert writes(calls)==[('PUT','/repos/o/r/pulls/1/merge',{'json':{
        'sha':HEAD,'merge_method':'squash','commit_title':'Title','commit_message':'Body'}})]


def test_uppercase_guard_normalized():
    client,calls=make_client()
    assert merge(client,expected_head_sha=HEAD.upper())['outcome']=='merged'
    assert writes(calls)[0][2]['json']['sha']==HEAD


def test_already_merged_is_read_only():
    client,calls=make_client(row=snapshot(state='closed',merged=True,merged_at='2026-10-03T00:00:00Z'))
    data=merge(client)
    assert data['outcome']=='already_merged' and data['sha']==MERGED and not writes(calls)


def test_success_response_missing_sha_is_unconfirmed():
    client,calls=make_client(put={'merged':True,'message':'ok'})
    data=merge(client)
    assert data['outcome']=='unconfirmed' and data['merged'] is None and len(writes(calls))==1


def test_timeout_is_unconfirmed_never_retried_or_false_failure():
    client,calls=make_client(put_error=RuntimeError('timeout ghp_PRIVATE'))
    data=merge(client)
    assert data['outcome']=='unconfirmed' and data['merged'] is None and len(writes(calls))==1
    assert 'ghp_PRIVATE' not in json.dumps(data)


def test_github_409_is_conflict_not_auto_retry():
    client,calls=make_client(put_error=RuntimeError('HTTP error 409: head mismatch'))
    data=merge(client)
    assert data['outcome']=='head_conflict' and data['http_status']==409 and len(writes(calls))==1


def test_github_merged_false_not_success():
    client,_=make_client(put={'merged':False,'message':'not allowed'})
    data=merge(client)
    assert data['outcome']=='rejected' and data['merged'] is False and data['sha'] is None


def test_read_api_error_no_raw_secrets_or_put():
    client,calls=make_client(read_error=True)
    data=merge(client)
    assert data['outcome']=='preflight_unknown' and not writes(calls)
    assert 'ghp_PRIVATE' not in json.dumps(data)


@pytest.mark.parametrize('bad',[{},[],None,{'number':1}])
def test_malformed_pr_never_mutates(bad):
    client,calls=make_client(row=bad if bad is not None else [])
    assert merge(client)['outcome']=='preflight_unknown' and not writes(calls)


def test_recheck_head_after_checks_prevents_write():
    client,calls=make_client()
    original=client._request.side_effect
    reads=0
    def request(method,url,**kwargs):
        nonlocal reads
        if method=='GET' and url.endswith('/pulls/1'):
            reads+=1
            if reads==2:
                row=snapshot();row['head']['sha']=BASE
                calls.append((method,url,kwargs))
                return MagicMock(json=lambda:row)
        return original(method,url,**kwargs)
    client._request.side_effect=request
    data=merge(client)
    assert data['outcome']=='head_conflict' and not writes(calls)


@pytest.mark.parametrize('field,value',[('draft',True),('state','closed'),('mergeable',None)])
def test_recheck_pr_state_after_checks_prevents_write(field,value):
    client,calls=make_client()
    original=client._request.side_effect;reads=0
    def request(method,url,**kwargs):
        nonlocal reads
        if method=='GET' and url.endswith('/pulls/1'):
            reads+=1
            if reads==2:
                calls.append((method,url,kwargs))
                return MagicMock(json=lambda:snapshot(**{field:value}))
        return original(method,url,**kwargs)
    client._request.side_effect=request
    assert merge(client)['outcome'] in ('draft','closed','mergeability_unknown')
    assert not writes(calls)


@pytest.mark.parametrize('code',[401,403,404,405,422])
def test_known_refusal_returns_rejected_without_fallback(code):
    client,calls=make_client(put_error=RuntimeError(f'HTTP error {code}: Bearer ghp_PRIVATE'))
    data=merge(client,merge_method='merge')
    assert data['outcome']=='rejected' and data['http_status']==code
    assert len(writes(calls))==1 and 'ghp_PRIVATE' not in json.dumps(data)


def test_http500_body_claiming_409_is_still_unconfirmed():
    client,calls=make_client(put_error=RuntimeError('HTTP error 500: HTTP error 409: pretend'))
    assert merge(client)['outcome']=='unconfirmed' and len(writes(calls))==1


def test_repo_read_failure_does_not_break_get_but_blocks_merge():
    client,calls=make_client();original=client._request.side_effect
    def request(method,url,**kwargs):
        if url=='/repos/o/r':
            calls.append((method,url,kwargs))
            raise RuntimeError('HTTP error 403: ghp_PRIVATE')
        return original(method,url,**kwargs)
    client._request.side_effect=request
    data=parse(pr.get_pull_request(client=client,**ARGS))
    assert data['head']['sha']==HEAD and not data['merge_methods_complete']
    assert data['allowed_merge_methods']==[] and data['merge_method_flags']['merge'] is None
    assert merge(client)['outcome']=='policy_unknown' and not writes(calls)


def test_no_checks_is_not_fabricated_success_but_api_can_enforce_policy(monkeypatch):
    monkeypatch.setattr(pr,'get_commit_status',lambda *a,**kw:'metadata: '+json.dumps(
        {'head_sha':HEAD,'aggregate_state':'no_checks','complete':True,'counts':{}}))
    client,calls=make_client()
    data=merge(client)
    assert data['outcome']=='merged' and data['checks']['aggregate_state']=='no_checks'
    assert len(writes(calls))==1


@pytest.mark.parametrize('field,value',[('number',True),('number',0),('number','1'),
                                       ('owner','..'),('repo','..'),('repo','r/other')])
def test_invalid_pr_identity_no_api(field,value):
    client,calls=make_client();args={**ARGS,field:value,'expected_head_sha':HEAD}
    assert parse(pr.merge_pull_request(client=client,**args))['outcome']=='invalid_input'
    assert not calls


@pytest.mark.parametrize('field,value',[('commit_title',None),('commit_message',True),('commit_message','x'*10001)])
def test_invalid_optional_commit_text_no_api(field,value):
    client,calls=make_client()
    assert merge(client,**{field:value})['outcome']=='invalid_input' and not calls


def test_unknown_mergeable_state_not_clean():
    client,calls=make_client(row=snapshot(mergeable_state='future-state'))
    assert merge(client)['outcome']=='mergeability_unknown' and not writes(calls)


def test_malformed_check_metadata_fail_closed(monkeypatch):
    monkeypatch.setattr(pr,'get_commit_status',lambda *a,**kw:'not metadata')
    client,calls=make_client()
    assert merge(client)['outcome']=='checks_not_ready' and not writes(calls)


def test_http_schema_required_guard_and_negative_transport(monkeypatch):
    import mcp_server.server as server
    client,calls=make_client()
    monkeypatch.setattr(server,'GitHubClient',lambda token:client)
    response=server.app.test_client().post('/mcp',
        headers={'Authorization':'Bearer test-not-a-real-token'},
        json={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{
            'name':'merge_pull_request','arguments':{**ARGS,'expected_head_sha':BASE}}})
    body=response.get_json()
    assert 'error' not in body
    data=parse(body['result']['content'][0]['text'])
    assert data['outcome']=='head_conflict' and not writes(calls)
    schema=pr.merge_pull_request._mcp_tool.to_mcp_tool_definition()['inputSchema']
    assert schema['required']==['owner','repo','number','expected_head_sha']
    assert schema['properties']['merge_method']['enum']==['merge','squash','rebase']


def test_concurrent_merge_on_final_read_is_confirmed_without_put():
    client,calls=make_client();original=client._request.side_effect;reads=0
    def request(method,url,**kwargs):
        nonlocal reads
        if method=='GET' and url.endswith('/pulls/1'):
            reads+=1
            if reads==2:
                calls.append((method,url,kwargs))
                return MagicMock(json=lambda:snapshot(state='closed',merged=True))
        return original(method,url,**kwargs)
    client._request.side_effect=request
    data=merge(client)
    assert data['outcome']=='already_merged' and data['merged'] is True and data['sha']==MERGED
    assert not writes(calls)


def test_valid_call_uses_real_status_aggregation_not_only_stub(monkeypatch):
    from mcp_server.tools.github.commits import get_commit_status
    monkeypatch.setattr(pr,'get_commit_status',get_commit_status)
    client,calls=make_client();original=client._request.side_effect
    def request(method,url,**kwargs):
        if '/commits/' in url:
            calls.append((method,url,kwargs))
            if url.endswith('/status'):
                data={'sha':HEAD,'total_count':0,'statuses':[],'state':'pending'}
            elif url.endswith('/check-runs'):
                data={'total_count':1,'check_runs':[{'id':1,'head_sha':HEAD,'name':'ci',
                       'status':'completed','conclusion':'success'}]}
            else: data={'sha':HEAD}
            return MagicMock(json=lambda:data,headers={})
        return original(method,url,**kwargs)
    client._request.side_effect=request
    data=merge(client)
    assert data['outcome']=='merged' and data['checks']['aggregate_state']=='success'
    assert data['checks']['counts']['success']==1 and len(writes(calls))==1
