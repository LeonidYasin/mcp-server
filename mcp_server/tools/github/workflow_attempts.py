"""Bounded read-only snapshots pinned to a workflow run attempt.

Attempt pinning prevents mixing reruns, not a transactional snapshot of mutable jobs.
"""
import re

from .commits import _SHA, _safe_text, _safe_url


PARAMETERS = {
    'run_attempt': {'type': 'integer', 'description': 'Попытка >=1; без параметра фиксируется latest при первом чтении'},
    'max_pages': {'type': 'integer', 'description': 'Лимит страниц jobs: 1–20, по умолчанию 5'},
    'max_jobs': {'type': 'integer', 'description': 'Лимит jobs в ответе: 0–100, по умолчанию 20'},
    'max_steps': {'type': 'integer', 'description': 'Общий лимит шагов в ответе: 0–500, по умолчанию 100'},
}


def _integer(value, low, high=None):
    return type(value) is int and value >= low and (high is None or value <= high)


def _identity(row, run_id, attempt=None, sha=None):
    return (isinstance(row, dict) and _integer(row.get('id'), 1)
            and row['id'] == run_id and _integer(row.get('run_attempt'), 1)
            and (attempt is None or row['run_attempt'] == attempt)
            and isinstance(row.get('head_sha'), str) and _SHA.fullmatch(row['head_sha'])
            and (sha is None or row['head_sha'].lower() == sha.lower()))


def _priority(row):
    if row.get('conclusion') in ('failure', 'timed_out', 'action_required', 'cancelled', 'startup_failure'):
        return 0
    if row.get('status') != 'completed' or row.get('conclusion') not in ('success', 'neutral', 'skipped'):
        return 1
    return 2


def _job_valid(row, run_id, attempt, sha):
    if not isinstance(row, dict) or not _integer(row.get('id'), 1):
        return False
    for key, expected in (('run_id', run_id), ('run_attempt', attempt)):
        if key in row and (not _integer(row[key], 1) or row[key] != expected):
            return False
    if 'head_sha' in row and (not isinstance(row['head_sha'], str) or row['head_sha'].lower() != sha.lower()):
        return False
    steps = row.get('steps', [])
    if not isinstance(steps, list) or len(steps) > 500:
        return False
    numbers = set()
    for step in steps:
        if not isinstance(step, dict) or not _integer(step.get('number'), 1) or step['number'] in numbers:
            return False
        numbers.add(step['number'])
    return True


def snapshot(client, owner, repo, run_id, run_attempt=None, max_pages=5,
             max_jobs=20, max_steps=100, flat=False):
    """Select identity, paginate the exact attempt, then bound presentation."""
    base = {'owner': owner, 'repo': repo, 'run_id': run_id, 'complete': False,
            'jobs': [], 'steps': []} if flat else {
                'owner': owner, 'repo': repo, 'run_id': run_id, 'complete': False, 'jobs': []}
    if not (isinstance(owner, str) and re.fullmatch(r'[A-Za-z0-9-]+', owner)
            and isinstance(repo, str) and re.fullmatch(r'[A-Za-z0-9_.-]+', repo)
            and repo not in ('.', '..') and _integer(run_id, 1)
            and (run_attempt is None or _integer(run_attempt, 1))
            and _integer(max_pages, 1, 20) and _integer(max_jobs, 0, 100)
            and _integer(max_steps, 0, 500)):
        return {**base, 'error': 'invalid_input'}
    path = f'/repos/{owner}/{repo}/actions/runs/{run_id}'
    selection = 'explicit' if run_attempt is not None else 'latest_at_resolution'
    try:
        sha = None
        if run_attempt is None:
            latest = client._request('GET', path).json()
            if not _identity(latest, run_id):
                raise ValueError('identity')
            run_attempt, sha = latest['run_attempt'], latest['head_sha']
        run = client._request('GET', f'{path}/attempts/{run_attempt}').json()
        if not _identity(run, run_id, run_attempt, sha):
            raise ValueError('identity')
    except Exception:
        return {**base, 'error': 'run_identity_unavailable_or_invalid'}
    sha = run['head_sha'].lower()
    base.update(run_attempt=run_attempt, selection=selection, head_sha=sha,
                html_url=_safe_url(run.get('html_url')), head_branch=_safe_text(run.get('head_branch')),
                **{key: _safe_text(run.get(key)) for key in (
                    'status', 'conclusion', 'created_at', 'updated_at', 'run_started_at', 'completed_at')})
    jobs, seen, total, error, complete = [], set(), None, None, False
    for page in range(1, max_pages + 1):
        try:
            payload = client._request('GET', f'{path}/attempts/{run_attempt}/jobs',
                                      params={'per_page': 100, 'page': page}).json()
            if not isinstance(payload, dict) or not _integer(payload.get('total_count'), 0):
                raise ValueError('total')
            expected = payload['total_count']
            rows = payload.get('jobs')
            if total is not None and total != expected:
                raise ValueError('changed total')
            if not isinstance(rows, list) or len(rows) > 100 or len(jobs) + len(rows) > expected:
                raise ValueError('rows')
            page_seen = set()
            for row in rows:
                if not _job_valid(row, run_id, run_attempt, sha) or row['id'] in seen | page_seen:
                    raise ValueError('job identity')
                page_seen.add(row['id'])
            total = expected
            jobs.extend(rows)
            seen.update(page_seen)
            if len(jobs) == total:
                complete = True
                break
            if not rows:
                raise ValueError('empty partial page')
        except Exception:
            error = 'jobs_unavailable_or_invalid'
            break
    all_steps = sum(len(job.get('steps', [])) for job in jobs)
    failed = [f"{_safe_text(job.get('name'))} / {_safe_text(step.get('name'))}"
              for job in jobs for step in job.get('steps', []) if step.get('conclusion') == 'failure']
    selected = sorted(jobs, key=_priority)[:max_jobs]
    budget, rendered, flattened = max_steps, [], []
    for job in selected:
        steps = []
        for step in sorted(job.get('steps', []), key=_priority)[:budget]:
            item = {key: _safe_text(step.get(key)) for key in ('name', 'status', 'conclusion', 'started_at', 'completed_at')}
            item.update(number=step['number'], run_attempt=run_attempt)
            steps.append(item)
            flattened.append({**item, 'job': _safe_text(job.get('name')), 'job_id': job['id'], 'step': item['name']})
        budget -= len(steps)
        rendered.append({**{key: _safe_text(job.get(key)) for key in (
            'name', 'status', 'conclusion', 'started_at', 'completed_at')},
            'id': job['id'], 'run_attempt': run_attempt, 'steps': steps})
    output_truncated = len(selected) < len(jobs) or len(flattened) < all_steps or len(failed) > 100
    base.update(complete=complete, total_jobs=total, fetched_jobs=len(jobs), returned_jobs=len(rendered),
                total_steps=all_steps if complete else None, fetched_steps=all_steps,
                returned_steps=len(flattened), failed_steps=failed[:100], failed_step_count=len(failed),
                output_truncated=output_truncated, truncated=not complete or output_truncated,
                jobs=rendered, identity_source='attempt_endpoint', atomic_snapshot=False)
    if flat:
        base['steps'] = flattened
        del base['jobs']
    if error:
        base['error'] = error
    return base
