"""#61 regression tests: aggregate statuses/checks without false success."""
import json
from unittest.mock import MagicMock

import pytest

from mcp_server.tools.github.commits import get_commit_status

SHA='a'*40
OTHER='b'*40


class Response:
    def __init__(self,data,link=''):
        self.data=data
        self.headers={'Link':link}
    def json(self): return self.data


def check(status='completed',conclusion='success',id=1,**extra):
    return dict(id=id,name='build',status=status,conclusion=conclusion,
                head_sha=SHA,html_url='https://github.com/o/r/checks/1',
                app={'id':1,'slug':'actions'},**extra)


def legacy(state='success',id=1):
    return dict(id=id,context=f'ci/{id}',state=state,description='test',
                target_url='https://ci.example/job')


def make_client(statuses=(),checks=(),*,status_pages=None,check_pages=None,
                status_error=None,check_error=None,resolve_error=None,
                reported_state='pending',link='',check_total=None):
    calls=[]
    client=MagicMock()
    status_pages=status_pages or [Response({'statuses':list(statuses),'total_count':len(statuses),
                                           'sha':SHA,'state':reported_state})]
    check_pages=check_pages or [Response({'check_runs':list(checks),'total_count':
                                         len(checks) if check_total is None else check_total},link)]
    def request(method,url,**kwargs):
        calls.append((method,url,kwargs))
        assert method=='GET'
        if url.endswith('/commits/feature%2Fbranch'):
            if resolve_error: raise resolve_error
            return Response({'sha':SHA,'html_url':'https://github.com/o/r/commit/'+SHA})
        if url.endswith('/status'):
            if status_error: raise status_error
            assert url.endswith('/commits/'+SHA+'/status')
            return status_pages[kwargs['params']['page']-1]
        if url.endswith('/check-runs'):
            if check_error: raise check_error
            assert url.endswith('/commits/'+SHA+'/check-runs')
            assert kwargs['params']['filter']=='latest'
            return check_pages[kwargs['params']['page']-1]
        raise AssertionError(url)
    client._request.side_effect=request
    return client,calls


def call(client,**kwargs):
    output=get_commit_status(client,owner='o',repo='r',sha='feature/branch',**kwargs)
    return output,json.loads(next(l[10:] for l in output.splitlines() if l.startswith('metadata: ')))


def test_empty_legacy_pending_does_not_override_successful_checks():
    client,_=make_client(checks=[check()],reported_state='pending')
    output,data=call(client)
    assert data['aggregate_state']=='success'
    assert data['complete'] is True and data['truncated'] is False
    assert data['head_sha']==SHA and data['legacy_statuses']==[]
    assert '📊 Статус: success' in output


def test_both_empty_is_no_checks():
    client,_=make_client()
    _,data=call(client)
    assert data['aggregate_state']=='no_checks' and data['complete'] is True


@pytest.mark.parametrize('conclusion',['failure','cancelled','timed_out','action_required','stale','startup_failure'])
def test_non_success_terminal_conclusions_not_hidden(conclusion):
    client,_=make_client(checks=[check(conclusion=conclusion)])
    _,data=call(client)
    assert data['aggregate_state']=='failure'
    assert data['counts']['failure']==1
    assert data['check_runs'][0]['conclusion']==conclusion


@pytest.mark.parametrize('status',['queued','requested','pending','waiting','in_progress'])
def test_nonterminal_statuses_pending(status):
    client,_=make_client(checks=[check(status=status,conclusion=None)])
    _,data=call(client)
    assert data['aggregate_state']=='pending'
    assert data['counts']['pending']==1


@pytest.mark.parametrize('conclusion',['success','neutral','skipped'])
def test_success_and_documented_nonblocking_policy(conclusion):
    client,_=make_client(checks=[check(conclusion=conclusion)])
    _,data=call(client)
    assert data['aggregate_state']=='success'
    assert data['counts'][conclusion]==1
    assert data['neutral_skipped_policy']=='non_blocking'
    assert data['merge_eligibility']=='not_evaluated'


@pytest.mark.parametrize('state,aggregate',[('success','success'),('failure','failure'),('error','failure'),('pending','pending')])
def test_legacy_states_are_aggregated(state,aggregate):
    client,_=make_client(statuses=[legacy(state)])
    _,data=call(client)
    assert data['aggregate_state']==aggregate
    assert data['legacy_statuses'][0]['state']==state


def test_failure_wins_over_pending_and_success():
    client,_=make_client(statuses=[legacy('pending')],checks=[check(conclusion='failure'),check(id=2)])
    _,data=call(client)
    assert data['aggregate_state']=='failure'


@pytest.mark.parametrize('status,conclusion',[('completed',None),('completed','future-result'),('future-status','success')])
def test_unknown_fields_do_not_become_success(status,conclusion):
    client,_=make_client(checks=[check(status=status,conclusion=conclusion)])
    _,data=call(client)
    assert data['aggregate_state']=='unknown'


@pytest.mark.parametrize('source',['status','checks','resolve'])
def test_api_error_unknown_and_secret_not_echoed(source):
    secret='ghp_DO_NOT_ECHO_THIS_SECRET'
    error=RuntimeError('HTTP error 403: Bearer '+secret)
    kwargs={'status_error':error} if source=='status' else ({'check_error':error} if source=='checks' else {'resolve_error':error})
    client,_=make_client(checks=[check()],**kwargs)
    output,data=call(client)
    assert data['aggregate_state']=='unknown' and data['complete'] is False
    assert secret not in output and 'Bearer ' not in output


def test_both_sources_paginated():
    statuses=[Response({'statuses':[legacy(id=1)],'total_count':2,'sha':SHA,'state':'success'},'<https://evil.example/secret>; rel="next"'),
              Response({'statuses':[legacy(id=2)],'total_count':2,'sha':SHA,'state':'success'})]
    checks=[Response({'check_runs':[check(id=1)],'total_count':2},'<https://api.github.com/next>; rel="next"'),
            Response({'check_runs':[check(id=2)],'total_count':2})]
    client,calls=make_client(status_pages=statuses,check_pages=checks)
    _,data=call(client)
    assert data['aggregate_state']=='success' and data['complete'] is True
    assert len(data['legacy_statuses'])==len(data['check_runs'])==2
    assert all(url.startswith('/repos/o/r/commits/') for _,url,_ in calls)
    assert [k['params']['page'] for _,u,k in calls if u.endswith('/status')]==[1,2]


def test_page_cap_incomplete_never_success():
    checks=[check(id=i) for i in range(1,101)]
    client,_=make_client(checks=checks,check_total=101,link='<https://api.github.com/next>; rel="next"')
    _,data=call(client,max_pages=1)
    assert data['aggregate_state']=='unknown' and data['complete'] is False
    assert data['sources']['check_runs']['truncated'] is True


def test_output_cap_does_not_change_complete_aggregate():
    client,_=make_client(checks=[check(id=1),check(id=2)])
    _,data=call(client,max_rows=1)
    assert data['aggregate_state']=='success' and data['complete'] is True
    assert data['output_truncated'] is True and data['truncated'] is True
    assert data['counts']['success']==2 and len(data['check_runs'])==1


def test_metadata_only_output():
    client,_=make_client(checks=[check()])
    _,data=call(client,max_rows=0)
    assert data['aggregate_state']=='success' and data['check_runs']==[]
    assert data['output_truncated'] is True


def test_failure_row_prioritized_when_output_truncated():
    client,_=make_client(checks=[check(id=1),check(id=2,conclusion='failure')])
    _,data=call(client,max_rows=1)
    assert data['check_runs'][0]['id']==2
    assert data['aggregate_state']=='failure'


def test_same_name_different_apps_not_deduplicated():
    a=check(id=1);b=check(id=2,conclusion='failure');b['app']={'id':2,'slug':'other'}
    client,_=make_client(checks=[a,b])
    _,data=call(client)
    assert data['aggregate_state']=='failure' and len(data['check_runs'])==2


def test_foreign_check_sha_not_counted_as_success():
    c=check();c['head_sha']=OTHER
    client,_=make_client(checks=[c])
    _,data=call(client)
    assert data['aggregate_state']=='unknown' and data['complete'] is False


@pytest.mark.parametrize('payload',[{}, {'check_runs':[],'total_count':True}, {'check_runs':[],'total_count':-1},
                                    {'check_runs':['bad'],'total_count':1}])
def test_malformed_source_not_empty_success(payload):
    client,_=make_client(check_pages=[Response(payload)])
    _,data=call(client)
    assert data['aggregate_state']=='unknown' and data['complete'] is False


def test_empty_page_before_total_not_complete():
    client,_=make_client(check_total=2)
    _,data=call(client)
    assert data['aggregate_state']=='unknown'


def test_changing_total_during_pagination_unknown():
    pages=[Response({'check_runs':[check(id=1)],'total_count':2}),
           Response({'check_runs':[check(id=2)],'total_count':3})]
    client,_=make_client(check_pages=pages)
    _,data=call(client)
    assert data['aggregate_state']=='unknown' and data['complete'] is False


def test_duplicate_check_id_does_not_hide_pagination_error():
    pages=[Response({'check_runs':[check(id=1)],'total_count':2}),
           Response({'check_runs':[check(id=1)],'total_count':2})]
    client,_=make_client(check_pages=pages)
    _,data=call(client)
    assert data['aggregate_state']=='unknown'


def test_target_url_credentials_and_tokens_sanitized():
    row=legacy();row['target_url']='https://user:password@ci.example/job?token=secret#fragment'
    client,_=make_client(statuses=[row])
    output,data=call(client)
    assert data['legacy_statuses'][0]['target_url']=='https://ci.example/job'
    assert 'password' not in output and '?token' not in output


@pytest.mark.parametrize('name,value',[('max_pages',0),('max_pages',21),('max_pages',True),('max_pages','2'),
                                      ('max_rows',-1),('max_rows',101),('max_rows',True)])
def test_invalid_limits_before_api(name,value):
    client=MagicMock()
    with pytest.raises(ValueError,match=name): call(client,**{name:value})
    client._request.assert_not_called()


def test_refs_resolved_before_sources_use_immutable_sha():
    client,calls=make_client(checks=[check()])
    _,data=call(client)
    assert calls[0][1].endswith('/commits/feature%2Fbranch')
    assert data['head_sha']==SHA
    assert len(calls)==3


@pytest.mark.parametrize('payload',[{'sha':OTHER,'statuses':[],'total_count':0},
                                    {'sha':SHA,'statuses':[],'total_count':'0'}])
def test_bad_legacy_source_is_unknown(payload):
    client,_=make_client(status_pages=[Response(payload)],checks=[check()])
    _,data=call(client)
    assert data['aggregate_state']=='unknown' and not data['complete']


@pytest.mark.parametrize('value',[None,'abc',OTHER[:39],{},'z'*40])
def test_invalid_resolution_no_sources_read(value):
    client=MagicMock()
    client._request.return_value=Response({'sha':value})
    _,data=call(client)
    assert data['head_sha'] is None and data['aggregate_state']=='unknown'
    assert client._request.call_count==1


def test_error_on_later_page_preserves_partial_rows_but_not_success():
    client,_=make_client(check_pages=[Response({'check_runs':[check()],'total_count':2})])
    _,data=call(client)  # fixture raises IndexError on page 2
    assert data['aggregate_state']=='unknown' and not data['complete']
    assert data['counts']['success']==1
    assert data['sources']['check_runs']['error']=='api_or_decode_error'


def test_legacy_page_cap_is_also_unknown():
    client,_=make_client(status_pages=[Response({'sha':SHA,'statuses':[legacy()], 'total_count':2})])
    _,data=call(client,max_pages=1)
    assert data['aggregate_state']=='unknown' and data['sources']['legacy_statuses']['truncated']


def test_unknown_legacy_state_is_not_success():
    client,_=make_client(statuses=[legacy('future-result')],checks=[check()])
    _,data=call(client)
    assert data['aggregate_state']=='unknown' and data['counts']['unknown']==1


def test_payload_texts_are_bounded_and_common_token_formats_redacted():
    row=legacy();row['description']='ghp_SECRET github_pat_SECRET Bearer SECRET '+('x'*1000)
    client,_=make_client(statuses=[row])
    output,data=call(client)
    assert 'SECRET' not in output and len(data['legacy_statuses'][0]['description'])<=200


def test_pending_with_terminal_conclusion_is_unknown():
    client,_=make_client(checks=[check(status='queued',conclusion='success')])
    _,data=call(client)
    assert data['aggregate_state']=='unknown'


def test_counts_larger_than_actual_rows_are_not_complete():
    client,_=make_client(check_total=0,checks=[check()])
    _,data=call(client)
    assert data['aggregate_state']=='unknown'


def test_registered_schema_and_http_metadata(monkeypatch):
    import mcp_server.server as server
    client,_=make_client(checks=[check()])
    monkeypatch.setattr(server,'GitHubClient',lambda token: client)
    response=server.app.test_client().post('/mcp',
        headers={'Authorization':'Bearer test-not-a-real-token'},
        json={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{
            'name':'get_commit_status','arguments':{
                'owner':'o','repo':'r','sha':'feature/branch','max_rows':0}}})
    body=response.get_json()
    assert 'error' not in body
    text=body['result']['content'][0]['text']
    data=json.loads(next(l[10:] for l in text.splitlines() if l.startswith('metadata: ')))
    assert data['aggregate_state']=='success' and data['output_truncated']
    schema=get_commit_status._mcp_tool.to_mcp_tool_definition()['inputSchema']
    assert schema['required']==['owner','repo','sha']
    assert schema['properties']['max_pages']['type']=='integer'
    assert schema['properties']['max_rows']['type']=='integer'
