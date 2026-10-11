"""Conservative completed-step segmentation of timestamped GitHub runner logs.

Display names come from the exact attempt timeline, never from `Run ...` titles.
Only unique top-level runner Run markers tied to contiguous timeline seconds are
supported. This is format/provenance validation, not authenticity of user logs.
"""
import re
from datetime import datetime, timezone

from .workflow_log_archive import LogError

_PREFIX = re.compile(r'^\ufeff?(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?Z (.*)$')
_SECOND = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z')


def _time(value):
    if not isinstance(value, str) or not _SECOND.fullmatch(value):
        raise LogError('step_timeline_incomplete')
    try:
        return int(datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc).timestamp())
    except ValueError:
        raise LogError('step_timeline_incomplete') from None


def _parse(lines):
    """Return timestamps and top-level Run candidates; nested groups can't match."""
    parsed, candidates, depth = [], [], 0
    for index, line in enumerate(lines):
        match = _PREFIX.fullmatch(line)
        if not match:
            raise LogError('step_filter_unsupported')
        sec = _time(match[1]+'Z')
        stamp = sec*10**9 + int((match[2] or '').ljust(9,'0'))
        body = match[3]
        if body.startswith('##[group]'):
            if depth == 0 and body.startswith('##[group]Run '):
                candidates.append((index,sec,stamp))
            depth += 1
            if depth > 64:
                raise LogError('step_boundaries_ambiguous')
        elif body.startswith('##[endgroup]'):
            if depth == 0:
                raise LogError('step_boundaries_ambiguous')
            depth -= 1
        parsed.append((stamp,depth))
    if depth:
        raise LogError('step_boundaries_ambiguous')
    return parsed,candidates


def select(filename, text, job_name, needle, identity):
    if not identity or identity.get('output_truncated'):
        raise LogError('step_filter_unsupported')
    jobs = [j for j in identity.get('jobs',[]) if j.get('name')==job_name]
    if len(jobs)!=1:
        raise LogError('step_filter_unsupported' if not jobs else 'step_boundaries_ambiguous')
    job = jobs[0]
    if job.get('status')!='completed' or type(job.get('id')) is not int:
        raise LogError('step_timeline_incomplete')
    steps = sorted(job.get('steps',[]),key=lambda s:s['number'])
    targets = [s for s in steps if needle.casefold() in (s.get('name') or '').casefold()]
    if not targets:
        return []
    active = [s for s in steps if s.get('conclusion')!='skipped']
    previous_end = None
    for step in active:
        if step.get('status')!='completed':
            raise LogError('step_timeline_incomplete')
        start,finish = _time(step.get('started_at')),_time(step.get('completed_at'))
        if finish<start or (previous_end is not None and start<previous_end):
            raise LogError('step_boundaries_ambiguous')
        previous_end = finish
    lines = text.splitlines()
    if len(lines)>100000:
        raise LogError('log_line_limit_exceeded')
    parsed,candidates = _parse(lines)
    result = []
    for target in targets:
        if target.get('conclusion')=='skipped':
            raise LogError('step_has_no_execution')
        if target.get('status')!='completed':
            raise LogError('step_timeline_incomplete')
        begin,end = _time(target.get('started_at')),_time(target.get('completed_at'))
        if end<=begin:
            raise LogError('step_boundaries_ambiguous')
        if any(s is not target and _time(s.get('started_at'))==begin for s in active):
            raise LogError('step_boundaries_ambiguous')
        following = [s for s in active if s['number']>target['number']]
        if not following:
            # Job completion/footer is not proof of the last step's log boundary.
            raise LogError('step_timeline_incomplete')
        next_step = following[0]
        numbers = {s['number'] for s in steps}
        if any(n not in numbers for n in range(target['number']+1,next_step['number'])):
            raise LogError('step_timeline_incomplete')
        next_time = _time(next_step.get('started_at'))
        if next_time!=end or next_step.get('status')!='completed':
            raise LogError('step_boundaries_ambiguous')
        if any(s is not next_step and _time(s.get('started_at'))==next_time for s in active):
            raise LogError('step_boundaries_ambiguous')
        starts=[c for c in candidates if c[1]==begin]
        ends=[c for c in candidates if c[1]==next_time]
        if len(starts)!=1 or len(ends)!=1:
            raise LogError('step_boundaries_ambiguous')
        left,_,left_stamp=starts[0]
        right,_,right_stamp=ends[0]
        if left>=right or parsed[right-1][1]!=0:
            raise LogError('step_boundaries_ambiguous')
        # Reject hidden top-level Run boundaries within the selected region.
        if any(left<c[0]<right for c in candidates):
            raise LogError('step_boundaries_ambiguous')
        stamps=[t for t,d in parsed[left:right]]
        if (any(t<left_stamp or t>=right_stamp for t in stamps)
                or any(a>b for a,b in zip(stamps,stamps[1:]))):
            raise LogError('step_boundaries_ambiguous')
        result.append({'file':filename,'job':job_name,'job_id':job['id'],
            'step':target['name'],'step_number':target['number'],
            'started_at':target['started_at'],'completed_at':target['completed_at'],
            'filter_mode':'combined_step','boundary_source':'attempt_timeline_unique_top_level_run_markers',
            'boundary_complete':True,'line_offset':left,'source_start_line':left+1,
            'source_end_line':right,'lines':lines[left:right]})
    return result
