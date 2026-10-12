"""#69 adapters use pinned bounded transport, never first-job guesses/main writes."""
from unittest.mock import MagicMock
import pytest
from test_workflow_attempts import client, job, run
from mcp_server.tools.github import workflow_attempt_logs as logs
from mcp_server.tools.github import workflows as wf
from mcp_server.tools.github import build_logs as builds
from mcp_server.tools.build import build_logs as legacy_builds
from mcp_server.tools.build.build_watch import watch_build,auto_fix_build
from mcp_server.tools.github.workflow_runs import get_step_logs_via_checks
from mcp_server.tools.github.client import GitHubClient


def setup(monkeypatch,files=None,pages=None,latest=None):
    c,calls=client(pages=pages,latest=latest);c._headers={}
    load=MagicMock(return_value=files if files is not None else {'build/1_Compile.txt':'first\nerror: broken\nlast'})
    monkeypatch.setattr(logs,'download',load)
    return c,calls,load


def args(**kw):return {'owner':'o','repo':'r','run_id':99,'run_attempt':1}|kw


def test_legacy_build_exports_are_same_functions_not_separate_registry_code():
    assert builds.get_android_build_error is legacy_builds.get_android_build_error
    assert builds.get_ios_build_error is legacy_builds.get_ios_build_error


@pytest.mark.parametrize('function',[builds.get_android_build_error,builds.get_ios_build_error])
def test_platform_report_old_attempt_identity_no_unbounded_job_download(monkeypatch,function):
    c,calls,load=setup(monkeypatch)
    out=function(c,**args())
    assert out['run_attempt']==1 and out['job_id']==101 and out['job_conclusion']=='failure'
    assert out['matches']==1 and out['no_matches_means_success'] is False
    assert all('/attempts/1' in url for method,url,kw in calls)
    load.assert_called_once_with(c,'o','r',99,1)
    c.get_job_logs.assert_not_called();c.get_workflow_jobs.assert_not_called()


def test_explicit_job_prefers_unique_exact_then_no_prefix_leak(monkeypatch):
    pages=[{'total_count':2,'jobs':[job(id=201,name='build'),job(id=202,name='build-other')]}]
    c,_,_=setup(monkeypatch,pages=pages,files={'build/1_Compile.txt':'error: ONE','build-other/1_Compile.txt':'error: TWO'})
    out=builds.get_android_build_error(c,**args(run_attempt=2,job_name='build'))
    assert out['job_id']==201 and out['matches']==1 and 'TWO' not in str(out)


def test_ambiguous_platform_hints_do_not_pick_first(monkeypatch):
    pages=[{'total_count':2,'jobs':[job(id=201,name='build-one'),job(id=202,name='build-two')]}]
    c,_,load=setup(monkeypatch,pages=pages)
    out=builds.get_android_build_error(c,**args(run_attempt=2))
    assert out['error']=='job_selection_ambiguous';load.assert_not_called()


def test_explicit_substring_ambiguous_no_download(monkeypatch):
    pages=[{'total_count':2,'jobs':[job(id=201,name='build-one'),job(id=202,name='build-two')]}]
    c,_,load=setup(monkeypatch,pages=pages)
    assert builds.get_android_build_error(c,**args(run_attempt=2,job_name='build'))['error']=='job_selection_ambiguous'
    load.assert_not_called()


def test_failed_run_without_error_match_is_not_success(monkeypatch):
    c,_,_=setup(monkeypatch,files={'build/1_Compile.txt':'warning only'})
    out=builds.get_android_build_error(c,**args())
    assert out['error']=='no_matching_text' and out['job_conclusion']=='failure' and out['no_matches_means_success'] is False


@pytest.mark.parametrize('function',[wf.get_full_workflow_logs,wf.get_workflow_logs_preview,wf.get_workflow_run_logs])
def test_log_wrappers_pin_old_attempt_and_global_limits(monkeypatch,function):
    c,calls,load=setup(monkeypatch)
    out=function(c,**args(max_lines=1,max_chars=5))
    assert out['run_attempt']==1 and out['returned_lines']==1 and out['output_truncated']
    assert len(out['logs'][0])<=5
    assert all('/attempts/1' in url for method,url,kw in calls)
    c.get_job_logs.assert_not_called();c.get_workflow_run_logs_files.assert_not_called()


def test_full_name_honestly_bounded(monkeypatch):
    c,_,_=setup(monkeypatch)
    out=wf.get_full_workflow_logs(c,**args(max_lines=1))
    assert out['legacy_full_name_bounded'] and out['output_truncated']


def test_preview_limit_global_not_per_job(monkeypatch):
    c,_,_=setup(monkeypatch,files={'a/1_X.txt':'a\na2','b/1_X.txt':'b\nb2'})
    out=wf.get_workflow_logs_preview(c,**args(limit=1))
    assert out['returned_lines']==1


def test_run_logs_grep_takes_precedence_without_second_tail_download(monkeypatch):
    c,_,load=setup(monkeypatch)
    out=wf.get_workflow_run_logs(c,**args(grep_pattern='broken',tail_lines=0))
    assert out['matches']==1 and out['conclusion']=='failure' and out['no_matches_means_success'] is False
    assert load.call_count==1


def test_run_logs_metadata_only_never_downloads(monkeypatch):
    c,_,load=setup(monkeypatch)
    out=wf.get_workflow_run_logs(c,**args(tail_lines=0))
    assert out['conclusion']=='failure' and out['complete'];load.assert_not_called()


@pytest.mark.parametrize('kw',[{'tail_lines':101},{'tail_lines':True},{'grep_context':21},{'max_chars':0}, {'context_before':201}])
def test_invalid_run_logs_bounds_before_source(monkeypatch,kw):
    c,calls,load=setup(monkeypatch)
    assert wf.get_workflow_run_logs(c,**args(**kw))['error']=='invalid_input' and not calls
    load.assert_not_called()


def test_checks_legacy_name_does_not_return_sha_wide_other_attempt(monkeypatch):
    c,calls,load=setup(monkeypatch)
    out=get_step_logs_via_checks(c,**args(step_name='Compile',max_lines=1))
    assert out['run_attempt']==1 and out['source']=='attempt_step_logs_not_checks' and out['deprecated_alias']
    c.get_check_runs.assert_not_called()


def test_watch_build_single_snapshot_no_log_download_or_polling(monkeypatch):
    c,calls,load=setup(monkeypatch)
    out=watch_build(c,**args(interval=1,timeout=900))
    assert out['monitoring_mode']=='single_snapshot' and out['interval_timeout_ignored']
    assert len(calls)==2 and out['conclusion']=='failure';load.assert_not_called()


def test_latest_error_queued_empty_jobs_not_all_success(monkeypatch):
    c,calls,load=setup(monkeypatch,latest=run(status='queued',conclusion=None),pages=[{'total_count':0,'jobs':[]}])
    # Latest attempt GET must agree with root state for this fixture.
    old=c._request.side_effect
    def request(method,url,**kw):
        if url.endswith('/attempts/2'):
            import httpx
            calls.append((method,url,kw));return httpx.Response(200,json=run(status='queued',conclusion=None))
        return old(method,url,**kw)
    c._request.side_effect=request;c.get_workflow_runs.return_value=[run()]
    out=wf.get_latest_workflow_error(c,'o','r')
    assert out['status']=='queued' and out['conclusion'] is None and out['total_jobs']==0
    assert 'Все проверки' not in str(out);load.assert_not_called()


def test_latest_empty_or_api_error_no_raw_token(monkeypatch):
    c,_,_=setup(monkeypatch);c.get_workflow_runs.return_value=[]
    assert wf.get_latest_workflow_error(c,'o','r')['error']=='no_workflow_runs'
    c.get_workflow_runs.side_effect=RuntimeError('Bearer ghp_DO_NOT_ECHO')
    out=wf.get_latest_workflow_error(c,'o','r')
    assert out['error']=='latest_run_unavailable_or_invalid' and 'ghp_DO_NOT_ECHO' not in str(out)


def test_job_identity_changed_between_selection_and_download_refused(monkeypatch):
    c,calls,load=setup(monkeypatch,latest=run())
    old=c._request.side_effect;reads=0
    def request(method,url,**kw):
        nonlocal reads
        if url.endswith('/jobs'):
            reads+=1
            if reads==2:
                import httpx
                calls.append((method,url,kw));return httpx.Response(200,json={'total_count':1,'jobs':[job(id=999)]})
        return old(method,url,**kw)
    c._request.side_effect=request
    out=builds.get_android_build_error(c,**args(run_attempt=2))
    assert out['error']=='job_identity_changed';load.assert_not_called()


def test_auto_fix_is_noop_no_main_write_or_network():
    c=MagicMock();out=auto_fix_build(c,owner='o',repo='r',run_id=99,platform='android')
    assert out['error']=='auto_fix_requires_reviewed_pr' and out['writes_performed'] is False
    assert c.mock_calls==[]


@pytest.mark.parametrize('method,values',[
    ('get_job_logs',('o','r',1)),('get_workflow_run_logs',('o','r',1)),
    ('get_workflow_run_logs_files',('o','r',1)),('get_workflow_run_logs_text',('o','r',1))])
def test_old_transport_helpers_fail_closed_without_http(method,values):
    c=GitHubClient('not-real');c._client.close();c._client=MagicMock()
    with pytest.raises(RuntimeError,match='legacy_log_transport_disabled'):
        getattr(c,method)(*values)
    assert c._client.mock_calls==[]
