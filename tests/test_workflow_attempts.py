"""#69 part 1: pin snapshot/job identity to a selected workflow attempt."""
from unittest.mock import MagicMock
import httpx
import pytest
from mcp_server.tools.github import workflow_runs as wr

SHA='a'*40
RUN=99


def run(attempt=2,**kw):
    r={'id':RUN,'run_attempt':attempt,'head_sha':SHA,'head_branch':'main',
       'status':'completed','conclusion':'success' if attempt==2 else 'failure',
       'created_at':'2026-10-01T00:00:00Z','updated_at':'2026-10-02T00:01:00Z',
       'run_started_at':f'2026-10-0{attempt}T00:00:00Z',
       'html_url':f'https://github.com/o/r/actions/runs/{RUN}/attempts/{attempt}'}
    r.update(kw);return r


def job(id=201,attempt=2,**kw):
    r={'id':id,'run_id':RUN,'run_attempt':attempt,'head_sha':SHA,'name':'build',
       'status':'completed','conclusion':'success' if attempt==2 else 'failure',
       'started_at':'2026-10-02T00:00:00Z','completed_at':'2026-10-02T00:01:00Z',
       'steps':[{'number':1,'name':'Compile','status':'completed','conclusion':'success' if attempt==2 else 'failure',
                 'started_at':'2026-10-02T00:00:00Z','completed_at':'2026-10-02T00:01:00Z'}]}
    r.update(kw);return r


def client(latest=None,attempt_rows=None,pages=None,error=None):
    c=MagicMock();calls=[]
    def request(method,url,**kw):
        calls.append((method,url,kw));assert method=='GET'
        if error:raise error
        if url.endswith('/runs/99'): data=run() if latest is None else latest
        elif url.endswith('/jobs'):
            attempt=int(url.split('/attempts/')[1].split('/')[0]);page=kw['params']['page']
            data=pages[page-1] if pages is not None else {'total_count':1,'jobs':[job(attempt=attempt,id=attempt*100+1)]}
        else:
            attempt=int(url.rsplit('/',1)[1]);data=attempt_rows[attempt] if attempt_rows is not None else run(attempt)
        return httpx.Response(200,json=data)
    c._request.side_effect=request
    return c,calls


def status(c,**kw):return wr.get_workflow_run_status(c,'o','r',RUN,**kw)
def steps(c,**kw):return wr.get_workflow_run_steps(c,'o','r',RUN,**kw)


def test_latest_pins_attempt_before_jobs():
    c,calls=client();data=status(c)
    assert data['run_attempt']==2 and data['selection']=='latest_at_resolution'
    assert data['head_sha']==SHA and data['complete'] is True
    assert [u for m,u,k in calls]==['/repos/o/r/actions/runs/99',
        '/repos/o/r/actions/runs/99/attempts/2','/repos/o/r/actions/runs/99/attempts/2/jobs']
    assert data['jobs'][0]['id']==201 and data['jobs'][0]['run_attempt']==2


def test_explicit_old_attempt_does_not_fetch_latest_or_mix_jobs():
    c,calls=client();data=status(c,run_attempt=1)
    assert data['run_attempt']==1 and data['conclusion']=='failure' and data['selection']=='explicit'
    assert data['jobs'][0]['id']==101 and data['failed_steps']==['build / Compile']
    assert len(calls)==2 and all('/attempts/1' in u for m,u,k in calls)


def test_steps_are_attempt_labeled_with_timestamps():
    c,_=client();data=steps(c,run_attempt=1)
    assert data['run_attempt']==1 and data['steps'][0]['run_attempt']==1
    assert data['steps'][0]['job_id']==101 and data['steps'][0]['completed_at']=='2026-10-02T00:01:00Z'
    assert data['created_at']=='2026-10-01T00:00:00Z'
    assert data['completed_at'] is None  # do not invent workflow completion from updated_at


@pytest.mark.parametrize('attempt',[0,-1,True,'2'])
def test_invalid_attempt_before_api(attempt):
    c,calls=client();data=status(c,run_attempt=attempt)
    assert data['error']=='invalid_input' and not calls


@pytest.mark.parametrize('kw',[{'max_pages':0},{'max_pages':21},{'max_pages':True},
                              {'max_jobs':-1},{'max_jobs':101},{'max_steps':501},{'max_steps':True}])
def test_invalid_bounds_before_api(kw):
    c,calls=client();assert status(c,**kw)['error']=='invalid_input' and not calls


@pytest.mark.parametrize('bad',[run(run_attempt=None),run(run_attempt=True),run(id=100),run(head_sha='bad')])
def test_missing_invalid_latest_identity_not_guessed(bad):
    c,calls=client(latest=bad);data=status(c)
    assert data['complete'] is False and data['error']=='run_identity_unavailable_or_invalid'
    assert len(calls)==1


@pytest.mark.parametrize('bad',[run(1),run(2,id=100),run(2,head_sha='b'*40)])
def test_pinned_endpoint_identity_mismatch_refused(bad):
    c,calls=client(attempt_rows={2:bad});data=status(c)
    assert not data['complete'] and data['error']=='run_identity_unavailable_or_invalid'
    assert not any(u.endswith('/jobs') for m,u,k in calls)


@pytest.mark.parametrize('field,value',[('run_id',100),('run_attempt',1),('head_sha','b'*40),('id',True)])
def test_foreign_or_invalid_job_marks_snapshot_incomplete(field,value):
    c,_=client(pages=[{'total_count':1,'jobs':[job(**{field:value})]}]);data=status(c)
    assert not data['complete'] and data['error']=='jobs_unavailable_or_invalid'


def test_pagination_uses_only_selected_attempt_endpoint():
    c,calls=client(pages=[{'total_count':2,'jobs':[job(id=201)]}, {'total_count':2,'jobs':[job(id=202)]}])
    data=status(c)
    assert data['complete'] and data['total_jobs']==2 and data['fetched_jobs']==2
    assert [kw['params']['page'] for m,u,kw in calls if u.endswith('/jobs')]==[1,2]


def test_source_page_cap_is_incomplete_not_complete_empty():
    c,_=client(pages=[{'total_count':2,'jobs':[job()]}]);data=status(c,max_pages=1)
    assert not data['complete'] and data['truncated'] and data['fetched_jobs']==1


def test_output_cap_does_not_change_source_completeness():
    c,_=client(pages=[{'total_count':2,'jobs':[job(id=201),job(id=202,conclusion='failure')]}])
    data=status(c,max_jobs=1,max_steps=0)
    assert data['complete'] and data['truncated'] and data['returned_jobs']==1
    assert data['jobs'][0]['id']==202 and data['jobs'][0]['steps']==[]
    assert data['failed_step_count']==0


def test_empty_jobs_complete_is_not_claim_of_workflow_success():
    c,_=client(latest=run(status='queued',conclusion=None),attempt_rows={2:run(status='queued',conclusion=None)},
               pages=[{'total_count':0,'jobs':[]}])
    data=status(c)
    assert data['complete'] and data['total_jobs']==0 and data['status']=='queued' and data['conclusion'] is None


def test_api_error_does_not_echo_pat_or_raw_body():
    c,_=client(error=RuntimeError('HTTP error 403: Bearer ghp_DO_NOT_ECHO'))
    data=status(c)
    assert data['error']=='run_identity_unavailable_or_invalid' and 'ghp_DO_NOT_ECHO' not in str(data)


def test_same_job_names_across_attempts_stay_distinct():
    c,_=client()
    a=status(c,run_attempt=1);b=status(c,run_attempt=2)
    assert a['jobs'][0]['name']==b['jobs'][0]['name']
    assert a['jobs'][0]['id']!=b['jobs'][0]['id'] and a['run_attempt']!=b['run_attempt']


def test_list_and_latest_expose_attempt_without_extra_gets():
    c=MagicMock();c.get_workflow_runs.return_value=[run(2)]
    assert wr.list_workflow_runs(c,'o','r')['runs'][0]['run_attempt']==2
    data=wr.get_latest_run_id(c,'o','r');assert data['run_attempt']==2 and data['run_started_at']
    c._request.assert_not_called()


@pytest.mark.parametrize('owner,repo,run_id',[('../o','r',99),('o','..',99),('o','r',True),('o','r',0)])
def test_invalid_path_identity(owner,repo,run_id):
    c,calls=client()
    assert wr.get_workflow_run_status(c,owner,repo,run_id)['error']=='invalid_input'
    assert not calls


@pytest.mark.parametrize('pages',[
    [{'total_count':2,'jobs':[job()]},{'total_count':3,'jobs':[job(id=202)]}],
    [{'total_count':2,'jobs':[job()]},{'total_count':2,'jobs':[job()]}],
    [{'total_count':2,'jobs':[job()]},{'total_count':2,'jobs':[]}],
    [{'total_count':True,'jobs':[]}],
    [{'total_count':1,'jobs':[job(steps=[{'number':1},{'number':1}])]}],
    [{'total_count':1,'jobs':[job(steps=[{'number':True}])]}],
    [{'total_count':1,'jobs':[job(steps=[{'number':i+1} for i in range(501)])]}],
])
def test_invalid_pages_fail_closed(pages):
    c,_=client(pages=pages);data=status(c)
    assert not data['complete'] and data['error']=='jobs_unavailable_or_invalid'


def test_failed_steps_first_with_global_budget_and_secrets_redacted():
    ok={'number':1,'name':'ok','status':'completed','conclusion':'success'}
    bad={'number':2,'name':'Bearer ghp_DO_NOT_ECHO','status':'completed','conclusion':'failure'}
    c,_=client(pages=[{'total_count':1,'jobs':[job(steps=[ok,bad])]}])
    data=status(c,max_steps=1)
    assert data['complete'] and data['output_truncated'] and data['failed_step_count']==1
    assert data['jobs'][0]['steps'][0]['number']==2 and 'ghp_DO_NOT_ECHO' not in str(data)


def test_missing_job_identity_fields_uses_endpoint_provenance_not_guess():
    row=job()
    for key in ('run_id','run_attempt','head_sha'):row.pop(key)
    c,_=client(pages=[{'total_count':1,'jobs':[row]}]);data=status(c)
    assert data['complete'] and data['identity_source']=='attempt_endpoint'
    assert data['jobs'][0]['run_attempt']==2 and data['atomic_snapshot'] is False


def test_metadata_only_caps_preserve_counts():
    c,_=client();data=steps(c,max_jobs=0,max_steps=0)
    assert data['complete'] and data['fetched_jobs']==1 and data['fetched_steps']==1
    assert data['steps']==[] and data['output_truncated']
