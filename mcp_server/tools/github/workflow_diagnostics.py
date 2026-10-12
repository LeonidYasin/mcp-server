"""Read-only, attempt-pinned diagnostic adapters; no absence-as-success inference."""
import re
from .workflow_attempts import snapshot, _integer
from .workflow_attempt_logs import query

DEFAULT_ERROR_PATTERN = r'e: file|error:|FAILURE|Exception|Unresolved reference|fatal error'


def platform_report(client, owner, repo, run_id, platform, job_name=None,
                    run_attempt=None, max_pages=5, max_lines=100, max_chars=16000,
                    step_name=None):
    if (not _integer(max_lines,1,1000) or not _integer(max_chars,1,65536)
            or any(v is not None and (not isinstance(v,str) or not v.strip() or len(v)>256)
                   for v in (job_name,step_name))):
        return {'complete':False,'error':'invalid_input'}
    data=snapshot(client,owner,repo,run_id,run_attempt,max_pages,100,500)
    if not data.get('complete') or data.get('output_truncated'):
        return {k:v for k,v in data.items() if k!='jobs'} | {
            'complete':False,'error':data.get('error','diagnostic_metadata_incomplete')}
    jobs=data['jobs']
    if job_name:
        exact=[j for j in jobs if (j.get('name') or '').casefold()==job_name.casefold()]
        matches=exact or [j for j in jobs if job_name.casefold() in (j.get('name') or '').casefold()]
        selection='explicit_unique_job'
    elif len(jobs)==1:
        matches=jobs;selection='only_job'
    else:
        prefixes=('android','apk','assemble','build') if platform=='android' else ('ios','xcode','archive','build')
        matches=[j for j in jobs if any(p in (j.get('name') or '').casefold() for p in prefixes)]
        selection='unique_platform_hint'
    if len(matches)!=1:
        return {'complete':False,'error':'job_selection_ambiguous' if matches else 'job_not_found',
            'run_id':run_id,'run_attempt':data['run_attempt'],'head_sha':data['head_sha'],
            'available_jobs':[{'id':j['id'],'name':j['name']} for j in jobs[:20]],
            'available_jobs_truncated':len(jobs)>20}
    job=matches[0]
    result=query(client,'grep',owner=owner,repo=repo,run_id=run_id,run_attempt=data['run_attempt'],
        max_pages=max_pages,job_name=job['name'],step_name=step_name,
        _exact_job_name=job['name'],_expected_job_id=job['id'],
        pattern=DEFAULT_ERROR_PATTERN,context=2,max_matches=50,max_lines=max_lines,max_chars=max_chars)
    result.update(platform=platform,job_id=job['id'],job_name=job['name'],job_selection=selection,
        job_status=job['status'],job_conclusion=job['conclusion'],
        diagnostic='heuristic_log_matches_not_root_cause',
        no_matches_means_success=False,run_selection=data['selection'],job_metadata_at_selection=True)
    return result


def latest_snapshot(client,owner,repo,run_attempt=None,max_pages=5,max_jobs=20,max_steps=100):
    if (not isinstance(owner,str) or not re.fullmatch(r'[A-Za-z0-9-]+',owner)
            or not isinstance(repo,str) or repo in ('.','..') or not re.fullmatch(r'[A-Za-z0-9_.-]+',repo)
            or (run_attempt is not None and not _integer(run_attempt,1))
            or not _integer(max_pages,1,20) or not _integer(max_jobs,0,100) or not _integer(max_steps,0,500)):
        return {'complete':False,'error':'invalid_input'}
    try:
        rows=client.get_workflow_runs(owner,repo,per_page=1)
        if not isinstance(rows,list) or not rows:
            return {'complete':False,'error':'no_workflow_runs'}
        run_id=rows[0].get('id')
        if not _integer(run_id,1):
            raise ValueError('identity')
        return snapshot(client,owner,repo,run_id,run_attempt,max_pages,max_jobs,max_steps)
    except Exception:
        return {'complete':False,'error':'latest_run_unavailable_or_invalid'}
