"""#83: validated timeline + root runner groups, never broad job-as-step output."""
from copy import deepcopy
from unittest.mock import MagicMock
import pytest
from mcp_server.tools.github import workflow_attempt_logs as queries
from mcp_server.tools.github.workflow_step_boundaries import select
from mcp_server.tools.github.workflow_log_archive import LogError
from mcp_server.tools.github.workflow_runs import get_run_logs_by_step, grep_run_logs, read_run_logs_offset

FILE='0_build.txt'
# Shape mirrors TunXBox: identical action names in 4KB/16KB; display names are
# NOT present in Run headings. Fractional markers disambiguate shared API second.
TEXT='\n'.join([
 '2026-10-11T02:31:07.1000000Z ##[group]Run emulator@sha',
 '2026-10-11T02:31:07.2000000Z ##[endgroup]',
 '2026-10-11T02:36:03.9000000Z FOUR_KB_ONLY',
 '2026-10-11T02:36:04.3101678Z ##[group]Run emulator@sha',
 '2026-10-11T02:36:04.3110533Z ##[endgroup]',
 '2026-10-11T02:36:04.3789114Z ##[group]Configure emulator',
 '2026-10-11T02:36:04.3790000Z ##[group]Run nested command',
 '2026-10-11T02:36:04.3790100Z ##[endgroup]',
 '2026-10-11T02:36:04.3801450Z ##[endgroup]',
 '2026-10-11T02:36:05.0000000Z error SIXTEEN_KB_ONLY',
 '2026-10-11T02:40:20.7910952Z target cleanup',
 '2026-10-11T02:40:21.7514523Z ##[group]Run upload-artifact@v4',
 '2026-10-11T02:40:21.7520897Z ##[endgroup]',
 '2026-10-11T02:40:22.0000000Z UPLOAD_ONLY',
])


def step(number,name,start,end,**kw):
    return dict(number=number,name=name,started_at='2026-10-11T'+start+'Z',
                completed_at='2026-10-11T'+end+'Z',status='completed',conclusion='success')|kw


def identity():
    return dict(complete=True,output_truncated=False,run_attempt=2,head_sha='a'*40,
        jobs=[dict(id=202,name='build',status='completed',steps=[
            step(1,'Android smoke (4KB)','02:31:07','02:36:04'),
            step(2,'Android smoke (16KB)','02:36:04','02:40:21',conclusion='failure'),
            step(3,'Upload','02:40:21','02:40:24'),
        ])])


def get(text=TEXT,meta=None,needle='16KB',filename=FILE,job='build'):
    return select(filename,text,job,needle,identity() if meta is None else meta)


def test_real_marker_shape_and_timeline_preserves_exact_source_line_boundaries():
    out=get();assert len(out)==1
    item=out[0];assert item['job_id']==202 and item['step_number']==2
    assert item['filter_mode']=='combined_step' and item['boundary_complete']
    assert item['line_offset']==3 and item['source_start_line']==4 and item['source_end_line']==11
    assert 'FOUR_KB_ONLY' not in str(item) and 'UPLOAD_ONLY' not in str(item)
    assert 'SIXTEEN_KB_ONLY' in str(item) and 'target cleanup' in str(item)


def test_nested_run_group_is_not_new_step_boundary():
    assert get()[0]['source_start_line']==4


def test_repeated_action_titles_do_not_assign_display_step_names():
    out=get(needle='4KB')[0]
    assert 'FOUR_KB_ONLY' in str(out) and 'SIXTEEN_KB_ONLY' not in str(out)


@pytest.mark.parametrize('change',[
    lambda m:m.update(output_truncated=True),
    lambda m:m['jobs'].clear(),
    lambda m:m['jobs'][0].update(status='in_progress'),
    lambda m:m['jobs'][0]['steps'][1].update(started_at=None),
    lambda m:m['jobs'][0]['steps'][1].update(completed_at='2026-10-11T02:36:04Z'),
    lambda m:m['jobs'][0]['steps'][1].update(status='in_progress'),
    lambda m:m['jobs'][0]['steps'][2].update(started_at='2026-10-11T02:40:22Z'),
    lambda m:m['jobs'][0]['steps'][0].update(completed_at='2026-10-11T02:36:05Z'),
    lambda m:m['jobs'][0]['steps'].pop(),
    lambda m:m['jobs'][0]['steps'][2].update(number=4),
])
def test_unknown_incomplete_or_overlapping_timeline_is_never_guessed(change):
    meta=identity();change(meta)
    with pytest.raises(LogError):get(meta=meta)


def test_duplicate_job_names_are_ambiguous():
    meta=identity();meta['jobs'].append(deepcopy(meta['jobs'][0]));meta['jobs'][1]['id']=203
    with pytest.raises(LogError,match='step_boundaries_ambiguous'):get(meta=meta)


def test_two_active_steps_in_same_second_are_ambiguous():
    meta=identity();meta['jobs'][0]['steps'].insert(1,step(4,'instant','02:36:04','02:36:04'))
    with pytest.raises(LogError):get(meta=meta)


@pytest.mark.parametrize('text',[
    TEXT.replace('##[group]Run emulator@sha','##[group]Configure emulator'),
    TEXT.replace('2026-10-11T02:36:05.0000000Z error SIXTEEN_KB_ONLY','untimestamped text'),
    TEXT.replace('2026-10-11T02:36:05.0000000Z','2026-10-11T02:36:03.0000000Z'),
    TEXT.replace('2026-10-11T02:36:05.0000000Z','2026-10-11T02:40:22.0000000Z'),
    TEXT+'\n2026-10-11T02:40:23.0000000Z ##[endgroup]',
    TEXT+'\n2026-10-11T02:40:23.0000000Z ##[group]unfinished',
    TEXT.replace('2026-10-11T02:36:05.0000000Z error SIXTEEN_KB_ONLY',
        '2026-10-11T02:36:05.0000000Z ##[group]Run injected\n2026-10-11T02:36:06.0000000Z ##[endgroup]'),
])
def test_unproven_marker_format_or_extra_boundaries_fail_closed(text):
    with pytest.raises(LogError):get(text=text)


def mock_query(monkeypatch,files=None,meta=None):
    c=MagicMock();c._headers={}
    monkeypatch.setattr(queries,'snapshot',MagicMock(return_value=identity() if meta is None else meta))
    monkeypatch.setattr(queries,'download',MagicMock(return_value={FILE:TEXT} if files is None else files))
    return c


def test_grep_context_cannot_cross_step_even_with_large_context(monkeypatch):
    c=mock_query(monkeypatch)
    out=grep_run_logs(c,owner='o',repo='r',run_id=99,step_name='16KB',pattern='SIXTEEN',context=20)
    assert out['complete'] and out['matches']==1
    assert 'FOUR_KB_ONLY' not in str(out) and 'UPLOAD_ONLY' not in str(out)
    item=out['segments'][0]
    assert item['lines'][0]['line']==4 and item['lines'][-1]['line']==11
    assert item['run_attempt']==2 and item['job_id']==202 and item['step_number']==2


def test_head_tail_and_offset_respect_step_source_lines(monkeypatch):
    c=mock_query(monkeypatch)
    args=dict(owner='o',repo='r',run_id=99,step_name='16KB',max_lines=1)
    head=get_run_logs_by_step(c,**args);tail=get_run_logs_by_step(c,**args,direction='tail')
    assert head['segments'][0]['lines'][0]['line']==4
    assert tail['segments'][0]['lines'][0]['line']==11
    assert 'UPLOAD_ONLY' not in str(tail)
    offset=read_run_logs_offset(c,**args,offset=5)
    assert offset['segments'][0]['lines'][0]['line']==9


def test_multiple_steps_same_file_keep_separate_segment_identity(monkeypatch):
    c=mock_query(monkeypatch)
    out=get_run_logs_by_step(c,owner='o',repo='r',run_id=99,step_name='Android smoke')
    assert len(out['segments'])==2
    assert [s['step_number'] for s in out['segments']]==[1,2]
    assert out['segments'][0]['source_end_line']==3 and out['segments'][1]['source_start_line']==4


def test_same_step_names_across_different_jobs_keep_ids(monkeypatch):
    meta=identity();meta['jobs'].append(deepcopy(meta['jobs'][0]));meta['jobs'][1].update(name='build-other',id=203)
    c=mock_query(monkeypatch,files={FILE:TEXT,'0_build-other.txt':TEXT},meta=meta)
    out=grep_run_logs(c,owner='o',repo='r',run_id=99,step_name='16KB',pattern='SIXTEEN',context=20)
    assert out['matches']==2 and {s['job_id'] for s in out['segments']}=={202,203}
    assert all('FOUR_KB_ONLY' not in str(s) for s in out['segments'])


def test_unknown_step_distinct_from_unknown_bounds(monkeypatch):
    c=mock_query(monkeypatch)
    out=get_run_logs_by_step(c,owner='o',repo='r',run_id=99,step_name='NOT_A_STEP')
    assert out['error']=='step_not_found' and out['complete']


def test_skipped_target_has_no_execution():
    meta=identity();meta['jobs'][0]['steps'][1]['conclusion']='skipped'
    with pytest.raises(LogError,match='step_has_no_execution'):get(meta=meta)


def test_global_output_caps_after_segmentation(monkeypatch):
    c=mock_query(monkeypatch)
    out=grep_run_logs(c,owner='o',repo='r',run_id=99,step_name='16KB',pattern='SIXTEEN',context=20,max_lines=1,max_chars=5)
    assert out['returned_lines']==1 and out['output_truncated'] and out['complete']
    assert sum(len(l['text']) for s in out['segments'] for l in s['lines'])<=5



def test_mixed_archive_complete_per_step_copy_not_double_counted(monkeypatch):
    c=mock_query(monkeypatch,files={FILE:TEXT,'build/2_Android smoke (16KB).txt':'error ONLY_COPY'})
    out=grep_run_logs(c,owner='o',repo='r',run_id=99,step_name='16KB',pattern='error')
    assert out['matches']==1 and len(out['segments'])==1
    assert out['segments'][0]['filter_mode']=='per_step'
    assert out['segments'][0]['job_id']==202 and out['segments'][0]['lines'][0]['line']==1


def test_mixed_archive_incomplete_step_copies_not_silently_dropped(monkeypatch):
    c=mock_query(monkeypatch,files={FILE:TEXT,'build/1_Android smoke (4KB).txt':'error FOUR'})
    out=grep_run_logs(c,owner='o',repo='r',run_id=99,step_name='Android smoke',pattern='error')
    assert out['error']=='step_boundaries_ambiguous' and not out['complete']
