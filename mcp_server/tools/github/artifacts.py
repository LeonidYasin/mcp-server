"""Bounded artifact lookup and sensitive, validated download capability resolution."""
import json
import re
from mcp_server.core.registry import mcp_tool
from mcp_server.tools.github.client import GitHubClient
from mcp_server.tools.github.commits import _safe_text, _SHA
from .workflow_attempts import _identity


def _positive(value):
    return type(value) is int and value > 0


def _result(outcome, **extra):
    data = {"outcome": outcome, "download_url": None, "url_expires_at": None,
            "requires_github_authorization": None, "sensitive_download_url": False, **extra}
    return "📦 Artifact: " + outcome + "\nmetadata: " + json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _lookup(client, path, name, max_pages):
    fetched = 0
    total = None
    matches = []
    seen = set()
    for page in range(1, max_pages + 1):
        response = client._request("GET", path, params={"name": name, "per_page": 100, "page": page})
        data = response.json()
        if not isinstance(data, dict) or type(data.get("total_count")) is not int or data["total_count"] < 0:
            raise ValueError("invalid lookup payload")
        if total is not None and total != data["total_count"]:
            raise ValueError("lookup changed")
        total = data["total_count"]
        rows = data.get("artifacts")
        if not isinstance(rows, list) or len(rows) > 100:
            raise ValueError("invalid lookup rows")
        for row in rows:
            if not isinstance(row, dict) or not _positive(row.get("id")) or not isinstance(row.get("name"), str):
                raise ValueError("invalid artifact row")
            if row["id"] in seen:
                raise ValueError("duplicate artifact row")
            seen.add(row["id"])
            if row["name"] == name:
                matches.append(row)
        fetched += len(rows)
        if fetched > total:
            raise ValueError("invalid total")
        more = bool(re.search(r'rel=["\']?next', response.headers.get("Link", "")))
        if fetched == total and not more:
            return matches, True
        if not rows:
            raise ValueError("empty page before end")
    return matches, False


def _attempt(row):
    workflow=row.get('workflow_run')
    nested=workflow.get('run_attempt') if isinstance(workflow,dict) else None
    direct=row.get('run_attempt')
    for value in (nested,direct):
        if value is not None and not _positive(value):
            raise ValueError('invalid attempt')
    if nested is not None and direct is not None and nested!=direct:
        raise ValueError('conflicting attempt')
    return nested if nested is not None else direct


def _artifact_info(row,run_id=None,head_sha=None):
    if (not isinstance(row,dict) or not _positive(row.get('id'))
            or not isinstance(row.get('name'),str) or not row['name']
            or type(row.get('expired')) is not bool or type(row.get('size_in_bytes')) is not int
            or row['size_in_bytes']<0):
        raise ValueError('invalid metadata')
    workflow=row.get('workflow_run')
    if workflow is not None and (not isinstance(workflow,dict) or not _positive(workflow.get('id'))):
        raise ValueError('invalid workflow')
    if run_id is not None and (workflow is None or workflow['id']!=run_id):
        raise ValueError('foreign run')
    sha=workflow.get('head_sha') if isinstance(workflow,dict) else None
    if sha is not None and (not isinstance(sha,str) or not _SHA.fullmatch(sha)):
        raise ValueError('invalid SHA')
    if sha and head_sha and sha.lower()!=head_sha.lower():
        raise ValueError('foreign SHA')
    attempt=_attempt(row)
    digest=row.get('digest')
    return {'artifact_id':row['id'],'name':_safe_text(row['name']),
            'size_in_bytes':row['size_in_bytes'],'created_at':_safe_text(row.get('created_at')),
            'updated_at':_safe_text(row.get('updated_at')),
            'artifact_expires_at':_safe_text(row.get('expires_at')),'expired':row['expired'],
            'run_id':workflow['id'] if workflow else None,'head_sha':sha.lower() if sha else None,
            'artifact_run_attempt':attempt,'attempt_identity_verified':attempt is not None and sha is not None,
            'attempt_source':'github_api_metadata' if attempt else 'not_provided',
            'digest':digest if isinstance(digest,str) and re.fullmatch(r'sha256:[0-9a-fA-F]{64}',digest) else None}


def _run_context(client,owner,repo,run_id,attempt=None):
    path=f'/repos/{owner}/{repo}/actions/runs/{run_id}'
    sha=None
    if attempt is None:
        latest=client._request('GET',path).json()
        if not _identity(latest,run_id):
            raise ValueError('run identity')
        attempt,sha=latest['run_attempt'],latest['head_sha']
    row=client._request('GET',f'{path}/attempts/{attempt}').json()
    if not _identity(row,run_id,attempt,sha):
        raise ValueError('attempt identity')
    return {'selected_run_attempt':attempt,'selected_head_sha':row['head_sha'].lower(),
            'selection':'explicit' if sha is None else 'latest_at_resolution',
            'run_created_at':_safe_text(row.get('created_at')),
            'run_started_at':_safe_text(row.get('run_started_at')),
            'run_completed_at':_safe_text(row.get('completed_at'))}


@mcp_tool(name='list_artifacts',description='Bounded run artifacts: IDs/SHA/time/attempt-or-unknown; явная попытка не фильтруется по guessed time/name.',
    parameters={'owner':{'type':'string'},'repo':{'type':'string'},'run_id':{'type':'integer'},
        'run_attempt':{'type':'integer','description':'>=1; только доказанные совпадения, unknown отдельно'},
        'max_pages':{'type':'integer','description':'1–20, default5'},
        'max_items':{'type':'integer','description':'0–100, default20; presentation cap'}},
    required=['owner','repo','run_id'])
def list_artifacts(client,owner,repo,run_id,run_attempt=None,max_pages=5,max_items=20):
    base={'complete':False,'source_complete':False,'artifacts':[],'unattributed_artifacts':[]}
    if (not isinstance(owner,str) or not re.fullmatch(r'[A-Za-z0-9-]+',owner)
            or not isinstance(repo,str) or repo in ('.','..') or not re.fullmatch(r'[A-Za-z0-9_.-]+',repo)
            or not _positive(run_id) or (run_attempt is not None and not _positive(run_attempt))
            or type(max_pages) is not int or not 1<=max_pages<=20
            or type(max_items) is not int or not 0<=max_items<=100):
        return {**base,'error':'invalid_input'}
    try:
        context=_run_context(client,owner,repo,run_id,run_attempt)
        base.update(context)
        rows,seen,total,done=[],set(),None,False
        for page in range(1,max_pages+1):
            response=client._request('GET',f'/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts',params={'per_page':100,'page':page})
            data=response.json()
            if not isinstance(data,dict) or type(data.get('total_count')) is not int or data['total_count']<0:
                raise ValueError('total')
            if total is not None and total!=data['total_count']:
                raise ValueError('changing total')
            total=data['total_count'];batch=data.get('artifacts')
            if not isinstance(batch,list) or len(batch)>100 or len(rows)+len(batch)>total:
                raise ValueError('rows')
            for row in batch:
                info=_artifact_info(row,run_id,context['selected_head_sha'])
                if info['artifact_id'] in seen:
                    raise ValueError('duplicate ID')
                seen.add(info['artifact_id']);rows.append((row['name'],info))
            more=bool(re.search(r'rel=["\']?next',response.headers.get('Link','')))
            if len(rows)==total and not more:
                done=True;break
            if not batch:
                raise ValueError('empty partial')
        eligible,unknown=[],[]
        groups={}
        for name,info in rows:
            groups.setdefault(name,[]).append(info['artifact_id'])
            if run_attempt is None or (info['artifact_run_attempt']==run_attempt and info['attempt_identity_verified']):
                eligible.append(info)
            elif info['artifact_run_attempt'] is None or not info['attempt_identity_verified']:
                unknown.append(info)
        # One global row budget shared by proven matches and unknown candidates.
        shown=eligible[:max_items];unattributed=unknown[:max(0,max_items-len(shown))]
        duplicates=[{'name':_safe_text(n),'candidate_ids':ids[:20],'ids_truncated':len(ids)>20}
                    for n,ids in groups.items() if len(ids)>1]
        complete=done and (run_attempt is None or not unknown)
        base.update(owner=owner,repo=repo,run_id=run_id,scope='run_all_attempts' if run_attempt is None else 'verified_attempt_matches',
            complete=complete,source_complete=done,total_artifacts=total,fetched_artifacts=len(rows),
            matching_artifacts=len(eligible),unattributed_count=len(unknown),
            unknown_attempts_in_fetched=sum(i['artifact_run_attempt'] is None for n,i in rows),
            artifacts=shown,unattributed_artifacts=unattributed,
            output_truncated=len(shown)<len(eligible) or len(unattributed)<len(unknown),
            duplicate_names=duplicates[:min(20,max_items)],duplicate_name_count_in_fetched=len(duplicates),
            duplicate_groups_truncated=len(duplicates)>min(20,max_items),
            attempt_filter_complete=(done and not unknown) if run_attempt is not None else None,
            attempt_attribution_policy='never_infer_from_name_or_timestamps')
        if not done:base['error']='lookup_incomplete'
        elif run_attempt is not None and unknown:base['error']='attempt_attribution_incomplete'
        return base
    except Exception:
        return {**base,'complete':False,'source_complete':False,'error':'artifact_identity_or_lookup_unavailable'}


@mcp_tool(
    name="download_artifact",
    description="Разрешает 302 GitHub в проверенную краткоживущую ZIP-ссылку; PAT не нужен на CDN. URL чувствительный; файл не скачивает.",
    parameters={
        "owner": {"type": "string"}, "repo": {"type": "string"},
        "artifact_id": {"type": "integer", "description": "Точный ID; имеет приоритет над name"},
        "name": {"type": "string", "description": "Точное имя, обязательно вместе с run_id"},
        "run_id": {"type": "integer", "description": "ID запуска для поиска по name"},
        "max_pages": {"type": "integer", "description": "Лимит lookup страниц 1–20, default 5; по 100 записей"},
        "run_attempt": {"type":"integer","description":">=1 + run_id; отказ при неизвестной принадлежности, не guessed time/name"},
    },
    required=["owner", "repo"],
)
def download_artifact(client: GitHubClient, **kwargs) -> str:
    owner, repo = kwargs.get("owner"), kwargs.get("repo")
    artifact_id, name, run_id = kwargs.get("artifact_id"), kwargs.get("name"), kwargs.get("run_id")
    max_pages = kwargs.get("max_pages", 5)
    requested_attempt = kwargs.get("run_attempt")
    if (not isinstance(owner, str) or not re.fullmatch(r"[A-Za-z0-9-]+", owner)
            or not isinstance(repo, str) or repo in (".", "..") or not re.fullmatch(r"[A-Za-z0-9_.-]+", repo)
            or type(max_pages) is not int or not 1 <= max_pages <= 20
            or (artifact_id is not None and not _positive(artifact_id))
            or (run_id is not None and not _positive(run_id))
            or (requested_attempt is not None and (not _positive(requested_attempt) or not _positive(run_id)))
            or (artifact_id is None and (not isinstance(name, str) or not name or not _positive(run_id)))):
        return _result("invalid_input", error="artifact_id_or_exact_name_and_run_required")
    root = f"/repos/{owner}/{repo}/actions"
    try:
        context = _run_context(client,owner,repo,run_id,requested_attempt) if requested_attempt is not None else {}
        if artifact_id is None:
            matches, complete = _lookup(client, f"{root}/runs/{run_id}/artifacts", name, max_pages)
            ids = [row["id"] for row in matches]
            if not complete:
                return _result("lookup_incomplete", lookup_complete=False, candidate_ids=ids[:20],
                               candidates_truncated=len(ids) > 20)
            if not matches:
                return _result("not_found", lookup_complete=True)
            if len(matches) > 1:
                return _result("ambiguous", lookup_complete=True, candidate_ids=ids[:20],
                               candidates_truncated=len(ids) > 20)
            art = matches[0]
            artifact_id = art["id"]
        else:
            art = client._request("GET", f"{root}/artifacts/{artifact_id}").json()
        info = _artifact_info(art,run_id,context.get('selected_head_sha'))
        if info['artifact_id']!=artifact_id:
            raise ValueError('artifact ID mismatch')
        info.update(context,lookup_complete=True)
        if requested_attempt is not None:
            if info['artifact_run_attempt'] is None or info['head_sha'] is None:
                return _result('artifact_attempt_unknown',**info,error='requested_attempt_not_proven')
            if info['artifact_run_attempt']!=requested_attempt:
                return _result('artifact_attempt_mismatch',**info,error='foreign_attempt')
        if art["expired"]:
            return _result("expired", **info)
        # Never trust archive_download_url from metadata as a destination.
        resolved = client.resolve_artifact_download(owner, repo, artifact_id)
        if not isinstance(resolved, dict) or resolved.get("outcome") != "resolved":
            outcome = resolved.get("outcome", "unknown") if isinstance(resolved, dict) else "unknown"
            status = resolved.get("http_status") if isinstance(resolved, dict) else None
            return _result(outcome, **info, http_status=status, error="download_not_resolved")
        return _result("resolved", **info, download_url=resolved["download_url"], http_status=302,
                       requires_github_authorization=False, sensitive_download_url=True)
    except Exception:
        return _result("unknown", artifact_id=artifact_id, lookup_complete=False,
                       error="metadata_or_lookup_unavailable_or_invalid")
