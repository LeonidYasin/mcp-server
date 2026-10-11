"""Bounded attempt-aware log queries; never pretend combined files are step logs."""
import json
import re
import subprocess
import sys
from pathlib import Path

from .commits import _SECRET, _safe_text
from .workflow_attempts import _integer, snapshot
from .workflow_log_archive import LogError, download

PARAMETERS = {
    'run_attempt': {'type':'integer','description':'Попытка >=1; default latest фиксируется до загрузки'},
    'max_pages': {'type':'integer','description':'Лимит страниц jobs 1–20, default 5'},
    'max_lines': {'type':'integer','description':'Общий лимит строк 1–1000, default 200'},
    'max_chars': {'type':'integer','description':'Общий лимит символов 1–65536, default 16000'},
}


def _scrub(value, token='', limit=None):
    if not isinstance(value, str):
        return None
    if token:
        value = value.replace(token, '[redacted]')
    value = _SECRET.sub('[redacted]', value)
    value = re.sub(r'(https?://[^\s?]+)\?[^\s]+', r'\1?[redacted]', value)
    return value if limit is None else value[:limit]


def segments(files, job_name=None, step_name=None):
    """Filter step portion only, not job folder; keep context per source file."""
    result, combined = [], []
    for filename, text in sorted(files.items()):
        name = filename.rsplit('/', 1)[-1]
        if '/' in filename:
            job = filename.rsplit('/', 1)[0]
            match = re.fullmatch(r'\d+_(.+)\.txt', name, re.I)
            step = match.group(1) if match else None
            mode = 'per_step' if match else 'auxiliary'
        else:
            match = re.fullmatch(r'\d+_(.+)\.txt', name, re.I)
            job, step, mode = (match.group(1) if match else name[:-4]), None, 'combined_job'
        if job_name and job_name.casefold() not in job.casefold():
            continue
        if step_name:
            if mode == 'combined_job':
                combined.append(filename)
                continue
            if step is None or step_name.casefold() not in step.casefold():
                continue
        result.append({'file':filename,'job':job,'step':step,'filter_mode':mode,'lines':text.splitlines()})
    # Cannot prove the combined file's group commands equal display step names.
    # Even with another per-step match, don't silently drop a combined job.
    if step_name and combined:
        raise LogError('step_filter_unsupported')
    return result


def _run_search(**args):
    try:
        # Fixed code, never execute log text or user-supplied code. communicate
        # timeout kills/waits the single worker even for catastrophic regex.
        proc = subprocess.run([sys.executable, '-m', 'mcp_server.tools.github.workflow_log_search'],
            input=json.dumps(args), text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=3, cwd=Path(__file__).resolve().parents[3])
        if proc.returncode:
            raise LogError('search_failed')
        value = json.loads(proc.stdout)
        if 'error' in value:
            raise LogError(value['error'])
        return value
    except subprocess.TimeoutExpired:
        raise LogError('search_timeout') from None
    except LogError:
        raise
    except Exception:
        raise LogError('search_failed') from None


def query(client, mode, **args):
    owner, repo, run_id = (args.get(k) for k in ('owner','repo','run_id'))
    step_name, job_name = args.get('step_name'), args.get('job_name')
    file_filter = args.get('file_filter')
    max_lines, max_chars = args.get('max_lines',200), args.get('max_chars',16000)
    offset, context, matches = args.get('offset',0), args.get('context',3), args.get('max_matches',50)
    direction, pattern, case = args.get('direction','head'), args.get('pattern'), args.get('case_sensitive',False)
    start_time = args.get('start_time')
    base = {'run_id':run_id,'complete':False,'logs':[],'segments':[],'output_truncated':False}
    if (not _integer(max_lines,1,1000) or not _integer(max_chars,1,65536)
            or not _integer(offset,0,100000) or not _integer(context,0,20)
            or not _integer(matches,1,500) or type(case) is not bool
            or direction not in ('head','tail')
            or any(v is not None and (not isinstance(v,str) or not v.strip() or len(v)>256)
                   for v in (job_name,step_name,file_filter))
            or (start_time is not None and (not isinstance(start_time,str) or len(start_time)>64))
            or (mode=='grep' and (not isinstance(pattern,str) or not pattern.strip() or len(pattern)>256))):
        return {**base,'error':'invalid_input'}
    if mode=='grep':
        try:
            re.compile(pattern)
        except re.error:
            return {**base,'error':'invalid_pattern'}
    identity = snapshot(client,owner,repo,run_id,args.get('run_attempt'),args.get('max_pages',5),100,0)
    base.update({k:identity.get(k) for k in ('run_attempt','selection','head_sha','created_at',
        'updated_at','run_started_at','completed_at','status','conclusion')})
    if not identity.get('complete'):
        return {**base,'error':identity.get('error','jobs_snapshot_incomplete')}
    try:
        files = download(client,owner,repo,run_id,identity['run_attempt'])
        if not files:
            return {**base,'error':'empty_archive','complete':True}
        filtered = {n:t for n,t in files.items() if file_filter.casefold() in n.casefold()} if file_filter else files
        selected = segments(filtered,job_name,step_name)
        if not selected:
            return {**base,'error':'no_matching_log_files','complete':True,
                    'available_files':[_safe_text(n) for n in sorted(files)[:20]],
                    'available_files_truncated':len(files)>20}
        auth = client._headers.get('Authorization','')
        token = auth[7:] if isinstance(auth,str) and auth.startswith('Bearer ') else ''
        count = sum(len(s['lines']) for s in selected)
        if count > 100000:
            raise LogError('log_line_limit_exceeded')
        for segment in selected:
            for k in ('file','job','step'):
                segment[k] = _scrub(segment[k],token,512)
            segment['run_attempt'] = identity['run_attempt']
            segment['lines'] = [_scrub(line,token) for line in segment['lines']]
        base.update(complete=True,filter_mode='per_step' if step_name else 'job_or_archive',
                    matched_files=[s['file'] for s in selected[:20]], matched_file_count=len(selected),
                    matched_files_truncated=len(selected)>20,total_lines=count)
        if mode=='grep':
            searched = _run_search(segments=selected,pattern=pattern,case_sensitive=case,
                context=context,max_matches=matches,max_lines=max_lines,max_chars=max_chars)
            base.update(searched)
            if not searched['matches']:
                base['error'] = 'no_matching_text'
            return base
        # Line windows are scoped per file in output, with a global offset/budget.
        flat = [(i,n,line) for i,s in enumerate(selected) for n,line in enumerate(s['lines'],1)]
        if start_time:
            first = next((i for i,(_,_,line) in enumerate(flat) if start_time in line),None)
            if first is None:
                return {**base,'error':'start_time_not_found','returned_lines':0}
            flat = flat[first:]
        eligible = flat[offset:] if mode=='offset' else flat
        chosen = eligible[-max_lines:] if direction=='tail' else eligible[:max_lines]
        rendered, chars, truncated = [], 0, len(chosen)<len(eligible)
        for i,n,line in chosen:
            if chars >= max_chars:
                truncated = True
                break
            text = line[:max_chars-chars]
            truncated |= len(text)!=len(line)
            chars += len(text)
            if not rendered or rendered[-1]['file'] != selected[i]['file']:
                rendered.append({k:v for k,v in selected[i].items() if k!='lines'} | {'lines':[]})
            rendered[-1]['lines'].append({'line':n,'text':text})
        base.update(segments=rendered,returned_lines=sum(len(s['lines']) for s in rendered),
                    output_truncated=bool(truncated),direction=direction,offset=offset)
        base['logs'] = [line['text'] for s in rendered for line in s['lines']]
        if not chosen:
            base['error']='empty_window'
        return base
    except LogError as exc:
        return {**base,'complete':False,'error':exc.code,'http_status':exc.status,
                'fallback':({'tool':'grep_run_logs','omit':'step_name','job_name':_safe_text(job_name),
                             'run_attempt':identity['run_attempt'],'note':'bounded job search; NOT step-scoped'}
                            if exc.code=='step_filter_unsupported' else None)}
    except Exception:
        return {**base,'complete':False,'error':'logs_unavailable_or_invalid'}
