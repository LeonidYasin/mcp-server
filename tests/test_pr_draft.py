"""#67: no REST draft writes or false success; mocked GitHub mutations only."""
import json
from copy import deepcopy
from unittest.mock import MagicMock
import pytest
from mcp_server.tools.github import pull_requests as pr

ARGS={'owner':'o','repo':'r','number':1}
NODE='PR_test_node'


def row(draft=True,**kw):
    data={'number':1,'node_id':NODE,'state':'open','merged':False,'draft':draft}
    data.update(kw)
    return data


def client(before=True,after=False,*,initial=None,readback=None,gql=None,gql_error=None,readback_error=None,patch_error=None):
    calls=[];c=MagicMock();reads=0
    initial=row(before) if initial is None else initial
    readback=row(after) if readback is None else readback
    mutation='convertPullRequestToDraft' if after else 'markPullRequestReadyForReview'
    gql={'data':{mutation:{'pullRequest':{'id':NODE,'number':1,'isDraft':after,'state':'OPEN'}}}} if gql is None else gql
    def request(method,url,**kw):
        nonlocal reads
        calls.append((method,url,kw))
        if method=='GET':
            reads+=1
            if reads>1 and readback_error: raise readback_error
            data=initial if reads==1 else readback
        elif url=='/graphql':
            if gql_error: raise gql_error
            data=gql
        elif method=='PATCH':
            if patch_error: raise patch_error
            data={}
        else: data={}
        return MagicMock(json=lambda:deepcopy(data))
    c._request.side_effect=request
    return c,calls


def parse(text): return json.loads(next(l[10:] for l in text.splitlines() if l.startswith('metadata: ')))
def update(c,**kw): return parse(pr.update_pull_request(client=c,**ARGS,**kw))
def writes(calls): return [c for c in calls if c[0]!='GET']


@pytest.mark.parametrize('before,target,mutation',[(True,False,'markPullRequestReadyForReview'),(False,True,'convertPullRequestToDraft')])
def test_both_transitions_graphql_and_readback(before,target,mutation):
    c,calls=client(before,target)
    data=update(c,draft=target)
    assert data['outcome']=='updated' and data['draft_outcome']=='applied'
    assert data['requested_draft'] is target and data['actual_draft'] is target
    assert data['draft_applied'] is True
    assert [m for m,u,k in calls]==['GET','POST','GET']
    assert writes(calls)[0][1]=='/graphql'
    payload=writes(calls)[0][2]['json']
    assert mutation in payload['query'] and payload['variables']=={'pullRequestId':NODE}
    assert all(m!='PATCH' for m,u,k in calls)


@pytest.mark.parametrize('target',[True,False])
def test_idempotent_target_state_no_write(target):
    c,calls=client(target,target)
    data=update(c,draft=target)
    assert data['outcome']=='no_op' and data['draft_outcome']=='no_op'
    assert data['actual_draft'] is target and not writes(calls)


@pytest.mark.parametrize('initial',[row(state='closed'),row(state='closed',merged=True),row(merged=True)])
def test_closed_or_merged_refused_before_any_write(initial):
    c,calls=client(initial=initial)
    data=update(c,draft=False,title='must not change')
    assert data['outcome']=='rejected' and not writes(calls)


@pytest.mark.parametrize('value',['false',0,1,[],{}])
def test_invalid_draft_type_before_api(value):
    c,calls=client()
    assert update(c,draft=value)['outcome']=='invalid_input' and not calls


@pytest.mark.parametrize('initial',[{},row(draft=None),row(number=2),row(node_id=''),row(state='future')])
def test_bad_initial_snapshot_refused(initial):
    c,calls=client(initial=initial)
    assert update(c,draft=False)['outcome'] in ('rejected','unconfirmed') and not writes(calls)


def test_graphql_permission_error_not_success_or_secret_echo():
    c,calls=client(after=True,gql={'errors':[{'message':'FORBIDDEN Bearer ghp_SECRET'}]})
    # initial true -> target false, separate readback stays true
    data=update(c,draft=False)
    assert data['outcome']!='updated' and data['draft_outcome']=='rejected'
    assert data['actual_draft'] is True and data['draft_applied'] is False
    assert 'ghp_SECRET' not in json.dumps(data)


def test_graphql_errors_with_matching_readback_are_unconfirmed():
    c,calls=client(gql={'errors':[{'message':'could be partial'}]})
    data=update(c,draft=False)
    assert data['outcome']=='unconfirmed' and data['actual_draft'] is False
    assert data['draft_applied'] is None and len(writes(calls))==1


def test_timeout_readback_reports_observed_state_without_retry():
    c,calls=client(gql_error=RuntimeError('timeout Bearer ghp_SECRET'))
    data=update(c,draft=False)
    assert data['outcome']=='unconfirmed' and data['actual_draft'] is False
    assert len(writes(calls))==1 and 'ghp_SECRET' not in json.dumps(data)


def test_success_reply_but_rest_draft_unchanged_not_success():
    gql={'data':{'markPullRequestReadyForReview':{'pullRequest':{'id':NODE,'number':1,'isDraft':False,'state':'OPEN'}}}}
    c,calls=client(after=True,gql=gql)
    data=update(c,draft=False)
    assert data['outcome']!='updated' and data['actual_draft'] is True
    assert data['draft_outcome']=='unconfirmed' and len(writes(calls))==1


def test_readback_failure_is_unconfirmed_no_retry():
    c,calls=client(readback_error=RuntimeError('HTTP error 403 ghp_SECRET'))
    data=update(c,draft=False)
    assert data['outcome']=='unconfirmed' and data['actual_draft'] is None
    assert len(writes(calls))==1 and 'ghp_SECRET' not in json.dumps(data)


@pytest.mark.parametrize('gql',[{}, {'data':{}}, {'data':{'markPullRequestReadyForReview':None}},
                              {'data':{'markPullRequestReadyForReview':{'pullRequest':{'id':'other','isDraft':False}}}}])
def test_malformed_graphql_success_never_updated(gql):
    c,calls=client(gql=gql)
    data=update(c,draft=False)
    assert data['outcome']=='unconfirmed' and len(writes(calls))==1


def test_mixed_rest_patch_never_contains_draft():
    c,calls=client()
    data=update(c,draft=False,title='T',body='B',base='develop')
    assert data['outcome']=='updated'
    patch=next(k['json'] for m,u,k in calls if m=='PATCH')
    assert patch=={'title':'T','body':'B','base':'develop'}
    assert data['changes']==['title','body','base','draft']


def test_mixed_partial_failure_does_not_hide_title_change():
    c,calls=client(after=True,gql={'errors':[{'message':'forbidden'}]})
    data=update(c,draft=False,title='T')
    assert data['outcome']=='partial' and data['changes']==['title']
    assert data['draft_outcome']=='rejected'


def test_contradictory_close_and_draft_refused_before_api():
    c,calls=client()
    assert update(c,draft=False,state='closed')['outcome']=='invalid_input' and not calls


def test_rest_failure_stops_before_graphql():
    c,calls=client(patch_error=RuntimeError('HTTP error 403 ghp_SECRET'))
    data=update(c,draft=False,title='T')
    assert data['outcome']=='unconfirmed'
    assert not any(u=='/graphql' for m,u,k in calls)
    assert 'ghp_SECRET' not in json.dumps(data)


@pytest.mark.parametrize('value',[None,False,True])
def test_bad_merged_tristate_cannot_be_assumed_open(value):
    initial=row(merged=value)
    c,calls=client(initial=initial)
    if value is False:
        assert update(c,draft=False)['outcome']=='updated'
    else:
        assert update(c,draft=False)['outcome'] in ('rejected','unconfirmed')
        assert not writes(calls)


@pytest.mark.parametrize('readback',[row(number=2),row(node_id='OTHER'),row(draft=None),{},row(state='closed')])
def test_bad_readback_never_claims_transition_confirmed(readback):
    c,calls=client(readback=readback)
    data=update(c,draft=False)
    assert data['outcome']=='unconfirmed' and data['draft_applied'] is None
    assert len(writes(calls))==1


@pytest.mark.parametrize('patch',[
    {'id':NODE,'number':1,'isDraft':True,'state':'OPEN'},
    {'id':NODE,'number':2,'isDraft':False,'state':'OPEN'},
    {'id':NODE,'number':1,'isDraft':False,'state':'CLOSED'},
    {'id':NODE,'number':True,'isDraft':False,'state':'OPEN'},
])
def test_graphql_echo_must_match_id_number_target_and_open(patch):
    c,calls=client(gql={'data':{'markPullRequestReadyForReview':{'pullRequest':patch}}})
    data=update(c,draft=False)
    assert data['outcome']=='unconfirmed' and data['actual_draft'] is False


def test_graphql_errors_with_partial_data_not_success():
    c,calls=client(gql={'errors':[{'message':'forbidden ghp_SECRET'}],
        'data':{'markPullRequestReadyForReview':{'pullRequest':{
            'id':NODE,'number':1,'isDraft':False,'state':'OPEN'}}}})
    data=update(c,draft=False)
    assert data['outcome']=='unconfirmed' and data['draft_applied'] is None
    assert 'ghp_SECRET' not in json.dumps(data)


def test_initial_read_error_no_writes():
    c=MagicMock();c._request.side_effect=RuntimeError('HTTP error 403 ghp_SECRET')
    data=update(c,draft=False)
    assert data['outcome']=='unconfirmed'
    assert c._request.call_count==1 and 'ghp_SECRET' not in json.dumps(data)


def test_same_target_draft_with_title_only_rest_patch():
    c,calls=client(before=False,after=False)
    data=update(c,draft=False,title='T')
    assert data['outcome']=='updated' and data['draft_outcome']=='no_op'
    assert data['changes']==['title']
    assert writes(calls)==[('PATCH','/repos/o/r/pulls/1',{'json':{'title':'T'}})]


def test_missing_node_for_noop_is_not_reason_to_mutate():
    c,calls=client(initial=row(draft=False,node_id=None))
    data=update(c,draft=False)
    assert data['outcome']=='no_op' and not writes(calls)


def test_draft_none_is_omitted_not_false():
    c,calls=client()
    data=update(c,draft=None,title='T')
    assert data['requested_draft'] is None and data['draft_outcome'] is None
    assert writes(calls)==[('PATCH','/repos/o/r/pulls/1',{'json':{'title':'T'}})]


def test_reviewers_follow_confirmed_draft_transition():
    c,calls=client()
    data=update(c,draft=False,reviewers=['reviewer'])
    assert data['outcome']=='updated'
    assert [u for m,u,k in writes(calls)]==['/graphql','/repos/o/r/pulls/1/requested_reviewers']
    assert writes(calls)[1][2]['json']=={'reviewers':['reviewer']}


def test_reviewers_not_requested_after_draft_failure():
    c,calls=client(after=True,gql={'errors':[{'message':'forbidden'}]})
    data=update(c,draft=False,reviewers=['reviewer'])
    assert data['outcome']=='rejected'
    assert not any('requested_reviewers' in u for m,u,k in calls)


def test_reviewer_failure_records_partial_draft_success():
    c,calls=client();original=c._request.side_effect
    def request(method,url,**kw):
        if 'requested_reviewers' in url:
            calls.append((method,url,kw))
            raise RuntimeError('HTTP error 403 ghp_SECRET')
        return original(method,url,**kw)
    c._request.side_effect=request
    data=update(c,draft=False,reviewers=['reviewer'])
    assert data['outcome']=='partial' and data['changes']==['draft']
    assert data['draft_applied'] is True and 'ghp_SECRET' not in json.dumps(data)


@pytest.mark.parametrize('kwargs',[{'state':'future'},{'title':True},{'reviewers':True},
                                   {'reviewers':['bad/user']},{'number':True}])
def test_invalid_mixed_args_no_incidental_mutation(kwargs):
    c,calls=client();args={**ARGS,'draft':False,**kwargs}
    assert parse(pr.update_pull_request(client=c,**args))['outcome']=='invalid_input' and not calls


def test_graphql_node_id_used_as_variable_never_query_interpolation():
    # Even a synthetic unusual node string cannot escape the query into another mutation.
    node='PR_special"} mutation Evil {'
    c,calls=client(initial=row(node_id=node),readback=row(draft=False,node_id=node),gql={
        'data':{'markPullRequestReadyForReview':{'pullRequest':{
            'id':node,'number':1,'isDraft':False,'state':'OPEN'}}}})
    assert update(c,draft=False)['outcome']=='updated'
    payload=writes(calls)[0][2]['json']
    assert node not in payload['query'] and payload['variables']['pullRequestId']==node


def test_flask_mcp_transport_transition_and_schema(monkeypatch):
    import mcp_server.server as server
    c,calls=client()
    monkeypatch.setattr(server,'GitHubClient',lambda token:c)
    response=server.app.test_client().post('/mcp',headers={'Authorization':'Bearer test-not-a-real-token'},
        json={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{
            'name':'update_pull_request','arguments':{**ARGS,'draft':False}}})
    body=response.get_json();assert 'error' not in body
    assert parse(body['result']['content'][0]['text'])['draft_applied'] is True
    assert all(m!='PATCH' for m,u,k in calls)
    schema=pr.update_pull_request._mcp_tool.to_mcp_tool_definition()['inputSchema']
    assert schema['required']==['owner','repo','number']
    assert schema['properties']['draft']['type']=='boolean'
