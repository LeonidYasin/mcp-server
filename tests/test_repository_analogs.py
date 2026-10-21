"""Offline contract tests for the idea -> discovery -> pinned-code MCP path."""
import base64
import hashlib
import json
from unittest.mock import MagicMock

import httpx
import pytest

from mcp_server.tools.github.repository_analogs import find_repository_analogs
from mcp_server.tools.github import repository_analogs as module

SECRET = 'SYNTHETIC_PRIVATE_CREDENTIAL'
SHA, TREE = 'a' * 40, 'b' * 40
QUERIES = [{'facet': 'problem', 'terms': 'telegram workflow'},
           {'facet': 'mechanism', 'terms': '"transition table" bot'}]


def row(ident=1, name='alice/tiny', **kw):
    return {'id': ident, 'full_name': name,
            'owner': {'id': ident + 100, 'login': name.split('/')[0], 'type': 'User'},
            'private': False, 'fork': True, 'archived': False, 'stargazers_count': 0,
            'forks_count': 0, 'description': 'A candidate, not a validated equivalent',
            'topics': [], **kw}


class Fake:
    def __init__(self):
        self.calls = []
        self.searches = 0
        self.search = lambda n, req: httpx.Response(200, json={
            'items': [row()], 'total_count': 1, 'incomplete_results': False})
        self.override = None
        self.meta_id = 1
        self.text = '# Workflow\nREADME claim, not implementation proof.\n'
        self._headers = {'Authorization': 'Bearer ' + SECRET}
        self._request = MagicMock(side_effect=AssertionError('Authenticated legacy path forbidden'))
        self._client = httpx.Client(transport=httpx.MockTransport(self.handle),
            headers={'Authorization': SECRET, 'X-Secret': SECRET},
            cookies={'secret': SECRET}, params={'leaked': SECRET}, auth=('user', SECRET),
            follow_redirects=True)

    def handle(self, request):
        self.calls.append(request)
        if self.override:
            response = self.override(request)
            if response is not None:
                return response
        if request.url.path == '/search/repositories':
            self.searches += 1
            return self.search(self.searches, request)
        raw = self.text.encode()
        blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        path = request.url.path
        if '/contents/' in path:
            data = {'type': 'file', 'path': 'README.md', 'sha': blob, 'size': len(raw),
                    'encoding': 'base64', 'content': base64.b64encode(raw).decode()}
        elif '/git/trees/' in path:
            data = {'sha': TREE, 'truncated': False, 'tree': [
                {'type': 'blob', 'path': 'README.md', 'mode': '100644', 'sha': blob, 'size': len(raw)}]}
        elif '/commits/' in path:
            data = {'sha': SHA, 'commit': {'tree': {'sha': TREE}}}
        else:
            data = {'id': self.meta_id, 'full_name': 'alice/tiny', 'private': False,
                    'fork': True, 'default_branch': 'main', 'stargazers_count': 0}
        return httpx.Response(200, json=data)


@pytest.fixture
def fake():
    f = Fake()
    yield f
    f._client.close()


def run(fake, **kw):
    return json.loads(find_repository_analogs(fake, **{'idea': 'Авторинг Telegram-сценариев из таблицы переходов',
                                                     'queries': QUERIES, **kw}))


def test_three_explicit_lanes_per_facet_without_popularity_floor(fake):
    r = run(fake)
    assert r['state'] == 'observed' and len(r['probes']) == 6
    assert [p['lane'] for p in r['plan']] == ['broad', 'broad', 'zero_star', 'zero_star', 'forks', 'forks']
    qs = [dict(q.url.params)['q'] for q in fake.calls]
    assert 'fork:true' in qs[0] and 'stars:' not in qs[0]
    assert 'stars:0' in qs[2] and 'fork:only' in qs[4]
    assert all('is:public' in q for q in qs)
    assert len(r['candidates']) == 1 and r['candidates'][0]['matched_probes'] == list(range(6))
    assert r['candidates'][0]['stars'] == 0 and r['candidates'][0]['fork'] is True
    assert r['candidates'][0]['similarity'] == 'not_assessed'
    assert not any(r['coverage'].values())
    assert r['budget']['requests'] == 6


def test_private_idea_not_automatically_sent_to_search(fake):
    r = run(fake, idea='A nonpublic business context not to be sent as Search query')
    assert r['idea'].startswith('A nonpublic')
    assert all('nonpublic' not in str(q.url) for q in fake.calls)
    assert all(not {'authorization', 'cookie', 'x-secret'} & set(q.headers) for q in fake.calls)
    assert all('leaked' not in q.url.params for q in fake.calls)
    fake._request.assert_not_called()


def test_plan_only_no_client_or_network():
    r = run(None, plan_only=True)
    assert r['state'] == 'planned' and r['budget']['requests'] == 0
    assert len(r['plan']) == 6 and not r['candidates']


def test_source_exclusion_both_query_and_returned_rows(fake):
    r = run(fake, source_repository='ALICE/tiny')
    assert not r['candidates'] and r['counts']['source_rows_excluded'] == 6
    assert all('-repo:ALICE/tiny' in str(q.url.params['q']) for q in fake.calls)
    assert len(fake.calls) == 6  # Does not read/implicitly publish the source idea.


def test_round_robin_and_match_provenance_survive_candidate_cap(fake):
    def search(n, req):
        return httpx.Response(200, json={'items': [row(n, f'alice/first{n}'), row(20, 'alice/shared')],
                                       'total_count': 2, 'incomplete_results': False})
    fake.search = search
    r = run(fake, max_candidates=7, limit_per_probe=2)
    assert [c['id'] for c in r['candidates']] == [1, 2, 3, 4, 5, 6, 20]
    assert r['candidates'][-1]['matched_probes'] == list(range(6))
    r = run(fake, max_candidates=2, limit_per_probe=2)
    assert r['counts']['omitted_by_candidate_cap'] == 5 and r['state'] == 'partial'


@pytest.mark.parametrize('kw', [
    {'idea': ''}, {'idea': 'x' * 1201}, {'idea': 3}, {'idea': SECRET},
    {'queries': []}, {'queries': QUERIES[:1]}, {'queries': QUERIES * 3},
    {'queries': [QUERIES[0], QUERIES[0]]},
    {'queries': [QUERIES[0], {'facet': 'stack', 'terms': 'python'}]},
    {'queries': [QUERIES[0], {'facet': 'mechanism', 'terms': 'repo:private/secret'}]},
    {'queries': [QUERIES[0], {'facet': 'mechanism', 'terms': 'bot OR private'}]},
    {'queries': [QUERIES[0], {'facet': 'mechanism', 'terms': '"unfinished'}]},
    {'queries': [QUERIES[0], {'facet': 'mechanism', 'terms': '-telegram'}]},
    {'queries': [QUERIES[0], {'facet': 'mechanism', 'terms': SECRET}]},
    {'queries': [QUERIES[0], {'facet': 'mechanism', 'terms': 'x', 'hidden': 'extra'}]},
    {'queries': [QUERIES[0], {'facet': ['mechanism'], 'terms': 'x'}]},
    {'source_repository': '../secret'}, {'source_repository': 'https://github.com/alice/tiny'},
    {'limit_per_probe': True}, {'limit_per_probe': 31}, {'max_candidates': 0},
    {'max_candidates': 101}, {'evidence_limit': True}, {'evidence_limit': 3},
    {'plan_only': 1}, {'unknown': True},
])
def test_invalid_inputs_zero_requests_no_echo(fake, kw):
    r = run(fake, **kw)
    assert r['state'] == 'invalid_input' and not fake.calls
    assert SECRET not in json.dumps(r)


@pytest.mark.parametrize('status', [301, 401, 403, 404, 429, 500])
def test_refusal_stops_without_retry_or_empty_success(fake, status):
    fake.search = lambda n, req: httpx.Response(status, text=SECRET, headers={'Location': 'https://evil.test'})
    r = run(fake, evidence_limit=2)
    assert len(fake.calls) == 1 and r['state'] == 'partial'
    assert r['probes'][0]['returned'] is None and not r['evidence']
    assert r['stop_reason'] == 'search_refused' and SECRET not in json.dumps(r)


def test_partial_hits_preserved_then_rate_refusal_no_evidence_reads(fake):
    fake.search = lambda n, req: httpx.Response(200, json={'items': [row()], 'total_count': 10,
        'incomplete_results': True}) if n == 1 else httpx.Response(429, text=SECRET)
    r = run(fake, evidence_limit=1)
    assert len(r['candidates']) == 1 and len(fake.calls) == 2 and not r['evidence']
    assert r['state'] == 'partial' and r['probes'][0]['incomplete_results'] is True


def test_private_and_unverified_results_not_exported(fake):
    fake.search = lambda n, req: httpx.Response(200, json={'items': [row(name='private/hidden', private=True)],
        'total_count': 1, 'incomplete_results': False})
    r = run(fake)
    assert r['state'] == 'partial' and not r['candidates']
    assert 'private/hidden' not in json.dumps(r)


def test_valid_empty_is_observation_not_absence_proof(fake):
    fake.search = lambda n, req: httpx.Response(200, json={'items': [], 'total_count': 0, 'incomplete_results': False})
    r = run(fake)
    assert r['state'] == 'observed' and r['counts']['returned'] == 0
    assert r['coverage']['analogs_complete'] is False


def test_conflicting_identities_not_silently_merged(fake):
    fake.search = lambda n, req: httpx.Response(200, json={'items': [row(1 if n < 3 else 2)],
        'total_count': 1, 'incomplete_results': False})
    r = run(fake)
    assert r['state'] == 'partial' and len(r['candidates']) == 1
    assert r['counts']['conflicting_identity_rows'] == 4


def test_optional_evidence_real_pin_hash_and_no_execution(fake):
    r = run(fake, evidence_limit=1)
    assert len(fake.calls) == 10 and r['budget']['requests'] == 10
    evidence = r['evidence'][0]['observation']
    assert evidence['state'] == 'observed'
    assert evidence['revision']['sha'] == SHA
    assert evidence['files'][0]['url'].endswith(f'/{SHA}/README.md#L1-L2')
    assert evidence['files'][0]['content_sha256'] == hashlib.sha256(fake.text.encode()).hexdigest()
    assert all(q.method == 'GET' and q.url.host == 'api.github.com' for q in fake.calls)
    assert all(not {'authorization', 'cookie', 'x-secret'} & set(q.headers) for q in fake.calls)
    assert r['candidates'][0]['similarity'] == 'not_assessed'  # Reading README is not equivalence proof.


def test_search_and_evidence_id_must_agree(fake):
    fake.meta_id = 55
    r = run(fake, evidence_limit=1)
    e = r['evidence'][0]['observation']
    assert r['state'] == 'partial' and e['error'] == 'candidate_identity_changed'
    assert e['files'] == [] and e['revision'] is None


def test_evidence_refusal_stops_next_candidate(fake):
    fake.search = lambda n, req: httpx.Response(200, json={'items': [row(), row(2, 'alice/second')],
        'total_count': 2, 'incomplete_results': False})
    fake.override = lambda req: httpx.Response(403, text=SECRET) if req.url.path.startswith('/repos/') else None
    r = run(fake, evidence_limit=2)
    assert len(fake.calls) == 7 and len(r['evidence']) == 1
    assert r['stop_reason'] == 'evidence_refused'


def test_deadline_checked_between_calls(fake, monkeypatch):
    ticks = iter([0, 121])
    monkeypatch.setattr(module.time, 'monotonic', lambda: next(ticks))
    r = run(fake)
    assert not fake.calls and r['stop_reason'] == 'time_budget'


def test_output_budget_never_silently_keeps_evidence(fake, monkeypatch):
    monkeypatch.setattr(module, 'OUTPUT_CAP', 12000)
    fake.search = lambda n, req: httpx.Response(200, json={'items': [row(n * 10 + i, f'alice/repo{n}_{i}')
        for i in range(5)], 'total_count': 5, 'incomplete_results': False})
    r = run(fake)
    assert r['error'] == 'output_budget' and r['candidates'] == [] and r['evidence'] == []
    assert r['counts']['returned'] == 0


def test_registry_and_real_mcp_json_text_contract(fake, monkeypatch):
    from mcp_server.server import app, registry
    tool = registry.get('find_repository_analogs')
    assert tool is not None and tool.required == ['idea', 'queries']
    monkeypatch.setattr('mcp_server.server.GitHubClient', lambda token: fake)
    params = {'name': 'find_repository_analogs', 'arguments': {'idea': 'Table-driven workflow',
              'queries': QUERIES, 'evidence_limit': 1}}
    response = app.test_client().post('/mcp', json={'jsonrpc': '2.0', 'id': 1,
        'method': 'tools/call', 'params': params}, headers={'Authorization': 'Bearer ' + SECRET})
    body = response.get_json()
    assert 'error' not in body
    result = json.loads(body['result']['content'][0]['text'])
    assert result['evidence'][0]['observation']['revision']['sha'] == SHA


@pytest.mark.parametrize('scope,qualifier', [('default', None), ('readme', 'in:readme'),
                                          ('name_description_readme', 'in:name,description,readme')])
def test_readme_expansion_is_explicit_and_recorded_in_effective_query(fake, scope, qualifier):
    r = run(fake, queries=[QUERIES[0], {**QUERIES[1], 'search_in': scope}])
    q = r['plan'][1]['arguments']['query']
    assert (qualifier in q) if qualifier else ('in:' not in q)
    assert r['candidates'][0]['matched_facets'] == ['problem', 'mechanism']


def test_invalid_read_scope_rejected_without_network(fake):
    r = run(fake, queries=[QUERIES[0], {**QUERIES[1], 'search_in': 'all_private_code'}])
    assert r['state'] == 'invalid_input' and not fake.calls


def test_same_terms_different_read_scopes_allowed(fake):
    r = run(fake, queries=[QUERIES[0], {'facet': 'mechanism', 'terms': QUERIES[0]['terms'],
                                      'search_in': 'readme'}])
    assert r['state'] == 'observed' and len(fake.calls) == 6


def test_unrelated_idea_is_not_hardcoded_to_telegram_and_max_budget_is_explicit(fake):
    queries = [{'facet': 'problem', 'terms': 'appointment booking'},
               {'facet': 'mechanism', 'terms': 'availability slots', 'search_in': 'readme'},
               {'facet': 'problem', 'terms': 'запись клиентов'},
               {'facet': 'mechanism', 'terms': 'calendar scheduling'}]
    r = run(fake, idea='Scheduling appointments without overbooking', queries=queries, evidence_limit=2)
    assert len(r['plan']) == 12 and r['budget']['max_search_requests'] == 12
    assert r['budget']['max_evidence_requests'] == 24
    assert all('telegram' not in p['arguments']['query'] for p in r['plan'])
    assert len(r['candidates']) == 1  # No fabricated scores or market claims from context.


@pytest.mark.parametrize('source_path', ['Kode.gs', 'genaisrc/main.genai.mts',
                                      'src/main.mjs', 'src/main.cts', 'src/main.cjs'])
def test_discovered_candidate_reads_script_source_beyond_readme(fake, source_path):
    source = ('\n' * 100 + 'function handleUpdate(e) {\nreturn e;\n}\n').encode()
    blob = hashlib.sha1(b'blob ' + str(len(source)).encode() + b'\0' + source).hexdigest()
    readme = fake.text.encode()
    doc_blob = hashlib.sha1(b'blob ' + str(len(readme)).encode() + b'\0' + readme).hexdigest()
    def override(req):
        if '/git/trees/' in req.url.path:
            return httpx.Response(200, json={'sha': TREE, 'truncated': False, 'tree': [
                {'type': 'blob', 'path': 'README.md', 'sha': doc_blob, 'mode': '100644', 'size': len(readme)},
                {'type': 'blob', 'path': source_path, 'sha': blob, 'mode': '100644', 'size': len(source)}]})
        if '/contents/' + source_path in req.url.path:
            return httpx.Response(200, json={'type': 'file', 'path': source_path, 'sha': blob,
                'encoding': 'base64', 'size': len(source), 'content': base64.b64encode(source).decode()})
        return None
    fake.override = override
    r = run(fake, evidence_limit=1)
    e = r['evidence'][0]['observation']
    assert e['state'] == 'observed' and len(e['files']) == 2
    f = next(f for f in e['files'] if f['path'] == source_path)
    assert 'handleUpdate' in f['text'] and f['start_line'] > 80
    assert f['url'].startswith('https://github.com/alice/tiny/blob/' + SHA + '/' + source_path + '#L')
    assert f['content_sha256'] == hashlib.sha256(source).hexdigest()
    assert r['budget']['requests'] == 11


@pytest.mark.parametrize('budget', [1, 2, 3, 5])
def test_bounded_search_batch_has_explicit_nonautomatic_continuation(fake, budget):
    r = run(fake, max_search_requests=budget)
    assert len(fake.calls) == budget and r['budget']['requests'] == budget
    assert r['state'] == 'partial' and r['stop_reason'] == 'search_request_budget'
    assert r['batch']['completed_probe_indices'] == list(range(budget))
    assert r['next_probe_request']['start_probe'] == budget
    assert r['budget']['planned_search_requests'] == 6
    assert r['budget']['max_search_requests'] == budget


def test_three_batches_cover_plan_without_repeating_searches(fake):
    r1 = run(fake, max_search_requests=2)
    r2 = json.loads(find_repository_analogs(fake, **r1['next_probe_request']))
    r3 = json.loads(find_repository_analogs(fake, **r2['next_probe_request']))
    assert r1['plan_fingerprint'] == r2['plan_fingerprint'] == r3['plan_fingerprint']
    assert [p['index'] for r in [r1, r2, r3] for p in r['probes']] == list(range(6))
    assert len(fake.calls) == 6 and r3['next_probe_request'] is None
    assert r3['state'] == 'observed'  # This completed only the final batch, not a persisted session.
    assert r3['batch']['all_plan_probes_observed_in_call'] is False
    assert r3['batch']['start_probe'] == 4
    assert r3['candidates'][0]['matched_probes'] == [4, 5]


def test_failed_probe_is_retained_as_next_not_skipped_or_automatically_retried(fake):
    fake.search = lambda n, req: httpx.Response(403, text=SECRET) if n == 2 else httpx.Response(200,
        json={'items': [row()], 'total_count': 1, 'incomplete_results': False})
    r = run(fake, max_search_requests=4)
    assert len(fake.calls) == 2 and r['next_probe_request']['start_probe'] == 1
    assert r['batch']['completed_probe_indices'] == [0]
    assert r['stop_reason'] == 'search_refused' and SECRET not in json.dumps(r)


def test_plan_preview_returns_executable_arguments_but_makes_zero_calls(fake):
    r = run(fake, plan_only=True, start_probe=2, max_search_requests=1)
    assert not fake.calls and r['next_probe_request']['start_probe'] == 2
    assert r['next_probe_request']['plan_only'] is False
    assert r['budget']['max_search_requests'] == 1


@pytest.mark.parametrize('kw', [{'max_search_requests': True}, {'max_search_requests': 0},
    {'max_search_requests': 13}, {'start_probe': True}, {'start_probe': -1}, {'start_probe': 6},
    {'start_probe': 1.0}, {'start_probe': '1'}])
def test_invalid_batch_controls_rejected_before_any_request(fake, kw):
    r = run(fake, **kw)
    assert r['state'] == 'invalid_input' and not fake.calls
    assert r['next_probe_request'] is None


def test_fingerprint_changes_for_terms_scope_source_or_limit_but_not_batch(fake):
    first = run(fake, plan_only=True)
    same = run(fake, plan_only=True, start_probe=3, max_search_requests=1)
    assert first['plan_fingerprint'] == same['plan_fingerprint']
    for changes in [{'limit_per_probe': 2}, {'source_repository': 'alice/source'},
                    {'queries': [QUERIES[0], {**QUERIES[1], 'search_in': 'readme'}]}]:
        assert run(fake, plan_only=True, **changes)['plan_fingerprint'] != first['plan_fingerprint']


def test_candidate_cap_blocks_continuation_past_omitted_data(fake):
    fake.search = lambda n, req: httpx.Response(200, json={'items': [row(n, f'alice/repo{n}')],
        'total_count': 1, 'incomplete_results': False})
    r = run(fake, max_search_requests=2, max_candidates=1)
    assert r['counts']['omitted_by_candidate_cap'] == 1
    assert r['next_probe_request'] is None and r['continuation_blocked_reason'] == 'candidate_cap'


def test_successful_search_with_zero_remaining_stops_before_another_get(fake):
    fake.search = lambda n, req: httpx.Response(200, headers={'x-ratelimit-remaining': '0'},
        json={'items': [row()], 'total_count': 1, 'incomplete_results': False})
    r = run(fake)
    assert len(fake.calls) == 1 and r['stop_reason'] == 'rate_budget_observed'
    assert r['batch']['completed_probe_indices'] == [0]
    assert r['next_probe_request']['start_probe'] == 1 and r['error'] is None


def test_partial_evidence_quota_signal_stops_next_candidate(fake):
    fake.search = lambda n, req: httpx.Response(200, json={'items': [row(), row(2, 'alice/second')],
        'total_count': 2, 'incomplete_results': False})
    fake.override = lambda req: httpx.Response(429, text=SECRET) if '/contents/' in req.url.path else None
    r = run(fake, evidence_limit=2)
    assert len(fake.calls) == 10 and len(r['evidence']) == 1
    assert r['evidence'][0]['observation']['state'] == 'partial'
    assert r['stop_reason'] == 'evidence_rate_budget' and SECRET not in json.dumps(r)


def test_evidence_path_focus_is_explicit_not_a_hidden_search_term(fake):
    r = run(fake, focus_path_terms=['Match', 'embed'], evidence_limit=1)
    assert all('match' not in p['arguments']['query'].lower() for p in r['plan'])
    assert r['candidates'][0]['evidence_request']['arguments']['focus_path_terms'] == ['match', 'embed']
    assert r['evidence'][0]['observation']['file_selection']['focus_path_terms_used'] == ['match', 'embed']
    assert r['budget']['requests'] == 10


@pytest.mark.parametrize('focus', [[], ['ma'], ['match/name'], ['match', 'MATCH'], None])
def test_invalid_analog_path_focus_rejected_without_network(fake, focus):
    r = run(fake, focus_path_terms=focus)
    assert r['state'] == 'invalid_input' and not fake.calls

# Quality follow-up: query diversity, explicit pages, safe resume, honest ordering.
def test_eight_formulations_cover_alternate_terms_without_more_per_call_gets(fake):
    queries = [
        {'facet':'problem','terms':'"supply demand" matching'},
        {'facet':'mechanism','terms':'"offer" "want" matching'},
        {'facet':'workflow','terms':'needs offers exchange'},
        {'facet':'domain','terms':'barter marketplace'},
        {'facet':'problem','terms':'взаимопомощь обмен'},
        {'facet':'mechanism','terms':'semantic matchmaking'},
        {'facet':'problem','terms':'resource discovery'},
        {'facet':'mechanism','terms':'complementary intent matching'},
    ]
    r=run(fake,queries=queries,max_search_requests=12)
    assert len(r['plan'])==24 and len(fake.calls)==12
    assert r['next_probe_request']['start_probe']==12
    assert {p['facet'] for p in r['plan']}=={'problem','mechanism','workflow','domain'}
    assert all(p['arguments']['page']==1 for p in r['plan'])
    assert r['coverage']['analogs_complete'] is False


def test_more_than_eight_formulations_refused(fake):
    queries=[{'facet':'problem' if i else 'mechanism','terms':f'concept {i}'} for i in range(9)]
    assert run(fake,queries=queries)['state']=='invalid_input' and not fake.calls


def test_resume_expected_fingerprint_enforced_before_network(fake):
    r=run(fake,plan_only=True)
    follow=r['next_probe_request']
    assert follow['expected_plan_fingerprint']==r['plan_fingerprint']
    follow['source_repository']='alice/changed'
    r2=json.loads(find_repository_analogs(fake,**follow))
    assert r2['error']=='plan_fingerprint_mismatch' and not fake.calls


def test_expected_fingerprint_remains_stable_across_search_batches(fake):
    a=run(fake,max_search_requests=2)
    b=json.loads(find_repository_analogs(fake,**a['next_probe_request']))
    assert a['plan_fingerprint']==b['plan_fingerprint']
    assert b['next_probe_request']['expected_plan_fingerprint']==b['plan_fingerprint']


@pytest.mark.parametrize('kw',[
    {'expected_plan_fingerprint':False},{'expected_plan_fingerprint':'x'*64},
    {'probe_pages':None},{'probe_pages':[]},{'probe_pages':{'00':2}},
    {'probe_pages':{'-1':2}},{'probe_pages':{'6':2}},{'probe_pages':{'0':True}},
    {'probe_pages':{'0':0}},{'probe_pages':{'0':1.2}},{'probe_pages':{'0':201}},
    {'probe_pages':{'0'*5000:1}},{'probe_pages':{'١':2}},
    {'probe_only':1},{'candidate_order':None},{'candidate_order':'stars'},
])
def test_invalid_new_controls_fail_before_network(fake,kw):
    assert run(fake,**kw)['state']=='invalid_input' and not fake.calls


def search_page_with_next(n,req):
    page=int(req.url.params['page']); size=int(req.url.params['per_page'])
    ids=[(page-1)*size+i+1 for i in range(size)]
    next_url=req.url.copy_merge_params({'page':page+1})
    return httpx.Response(200,headers={'Link':f'<{next_url}>; rel="next"'},
        json={'items':[row(i,f'alice/project{i}') for i in ids],
              'total_count':1000,'incomplete_results':False})


def test_page_followup_is_executable_scope_guarded_and_does_not_visit_siblings(fake):
    fake.search=search_page_with_next
    a=run(fake,limit_per_probe=2,max_search_requests=1)
    assert len(a['next_page_requests'])==1 and a['coverage_gaps'][0]['reasons']==['more_pages_available']
    args=a['next_page_requests'][0]['arguments']
    assert args['probe_pages']=={'0':2} and args['probe_only'] is True
    assert args['expected_plan_fingerprint']!=a['plan_fingerprint']
    b=json.loads(find_repository_analogs(fake,**args))
    assert len(fake.calls)==2 and b['probes'][0]['index']==0
    assert b['plan'][0]['arguments']['page']==2
    assert [c['id'] for c in a['candidates']]==[1,2]
    assert [c['id'] for c in b['candidates']]==[3,4]
    assert b['next_probe_request'] is None
    assert b['stop_reason']=='selected_probe_observed'
    assert b['next_page_requests'][0]['arguments']['probe_pages']=={'0':3}
    assert b['coverage']['analogs_complete'] is False


def test_explicit_page_stays_within_provider_window(fake):
    fake.search=search_page_with_next
    r=run(fake,limit_per_probe=10,probe_pages={'0':100},probe_only=True)
    assert len(fake.calls)==1 and fake.calls[0].url.params['page']=='100'
    assert r['next_page_requests']==[]
    assert r['probes'][0]['coverage']['stop_reason']=='search_window_cap'
    assert r['coverage']['global_complete'] is False


def test_missing_or_invalid_pagination_not_guessed_from_large_total(fake):
    fake.search=lambda n,req:httpx.Response(200,json={'items':[row()], 'total_count':500,'incomplete_results':False})
    r=run(fake,probe_only=True)
    assert not r['next_page_requests']
    assert r['coverage_gaps'][0]['reasons']==['pagination_unknown']


def test_forged_link_never_followed_or_exported_as_safe_page(fake):
    fake.search=lambda n,req:httpx.Response(200,headers={'Link':'<https://evil.test/>; rel="next"'},
        json={'items':[row()],'total_count':500,'incomplete_results':False})
    r=run(fake,probe_only=True)
    assert not r['next_page_requests'] and len(fake.calls)==1
    assert 'evil.test' not in json.dumps(r)


def test_page_followup_retains_failed_page_after_refusal(fake):
    fake.search=search_page_with_next
    a=run(fake,probe_only=True)
    fake.search=lambda n,req:httpx.Response(429,text=SECRET)
    b=json.loads(find_repository_analogs(fake,**a['next_page_requests'][0]['arguments']))
    assert b['next_probe_request']['probe_pages']=={'0':2}
    assert b['next_probe_request']['start_probe']==0 and len(fake.calls)==2
    assert b['batch']['completed_probe_indices']==[] and SECRET not in json.dumps(b)


def test_more_candidates_and_larger_pages_are_bounded(fake):
    fake.search=lambda n,req:httpx.Response(200,json={
        'items':[row(n*100+i,f'alice/proj{n}-{i}') for i in range(30)],
        'total_count':30,'incomplete_results':False})
    r=run(fake,limit_per_probe=30,max_candidates=100)
    assert r['counts']['unique_observed']==180 and len(r['candidates'])==100
    assert r['counts']['omitted_by_candidate_cap']==80
    assert r['continuation_blocked_reason']=='candidate_cap' and r['next_page_requests']==[]


def test_facet_order_is_explained_ignores_stars_and_counts_formulations_not_lanes(fake):
    def search(n,req):
        # First query: popular adjacent and tiny source-related. Second: only tiny.
        rows=[row(1,'alice/popular',stargazers_count=99999),row(2,'alice/tiny',stargazers_count=0)] if req.url.params['q'].startswith('telegram workflow') else [row(2,'alice/tiny',stargazers_count=0)]
        return httpx.Response(200,json={'items':rows,'total_count':len(rows),'incomplete_results':False})
    fake.search=search
    original=run(fake)
    assert original['candidates'][0]['id']==1
    ranked=run(fake,candidate_order='facet_coverage')
    c=ranked['candidates'][0]
    assert c['id']==2 and c['stars']==0 and set(c['matched_query_indices'])=={0,1}
    assert c['selection_basis']=={'order':'facet_coverage','core_facets_both_matched':True,
        'distinct_formulations':2,'semantic_similarity_verified':False}
    assert ranked['candidates'][1]['selection_basis']['distinct_formulations']==1
    assert all(c['similarity']=='not_assessed' for c in ranked['candidates'])


def test_zero_hits_incomplete_and_window_gaps_are_explicit(fake):
    fake.search=lambda n,req:httpx.Response(200,json={'items':[],'total_count':2001 if n==1 else 0,
        'incomplete_results':True if n==1 else False})
    r=run(fake,max_search_requests=2)
    assert 'provider_1000_result_window' in r['coverage_gaps'][0]['reasons']
    assert 'provider_incomplete_or_unknown' in r['coverage_gaps'][0]['reasons']
    assert 'zero_hits_not_absence_proof' in r['coverage_gaps'][1]['reasons']
    assert not r['coverage']['analogs_complete']


def test_candidate_omission_can_be_recovered_without_skipping_search_pages(fake):
    fake.search=lambda n,req:httpx.Response(200,json={
        'items':[row(i,f'alice/item{i}') for i in range(1,6)], 'total_count':5,'incomplete_results':False})
    a=run(fake,max_candidates=1)
    assert a['continuation_blocked_reason']=='candidate_cap'
    assert a['next_probe_request'] is None and a['next_page_requests']==[]
    assert a['recovery_request']['start_probe']==0
    b=json.loads(find_repository_analogs(fake,**a['recovery_request']))
    assert len(b['candidates'])==5 and b['counts']['omitted_by_candidate_cap']==0
    assert b['plan_fingerprint']==a['plan_fingerprint']
    assert b['next_probe_request']['start_probe']==1


def test_changed_page_or_limit_rejects_continuation_fingerprint(fake):
    a=run(fake,plan_only=True)
    for changes in [{'probe_pages':{'0':2}},{'limit_per_probe':20}]:
        r=json.loads(find_repository_analogs(fake,**{**a['next_probe_request'],**changes}))
        assert r['error']=='plan_fingerprint_mismatch'
    assert not fake.calls


def test_plan_warns_about_default_core_scope_without_network(fake):
    r = run(fake, plan_only=True)
    coverage = r['query_coverage']
    assert coverage['readme_formulation_indices'] == []
    assert coverage['core_facets_without_readme_scope'] == ['problem', 'mechanism']
    assert coverage['advisories'][0]['code'] == 'core_facet_without_readme_scope'
    assert coverage['synonyms_languages_assessed'] is False
    assert coverage['semantic_coverage_verified'] is False
    assert not fake.calls


@pytest.mark.parametrize('scope', ['readme', 'name_description_readme'])
def test_readme_advisory_tracks_each_core_facet_not_optional_facet(fake, scope):
    queries = [
        {'facet': 'problem', 'terms': 'complementary needs', 'search_in': scope},
        {'facet': 'mechanism', 'terms': 'intent matching'},
        {'facet': 'domain', 'terms': 'community exchange', 'search_in': scope},
    ]
    a = run(fake, queries=queries, plan_only=True)
    assert a['query_coverage']['readme_formulation_indices'] == [0, 2]
    assert a['query_coverage']['core_facets_without_readme_scope'] == ['mechanism']
    queries[1]['search_in'] = scope
    b = run(fake, queries=queries, plan_only=True)
    assert b['query_coverage']['advisories'] == []
    assert b['query_coverage']['semantic_coverage_verified'] is False
    assert not fake.calls


def test_advisory_does_not_silently_expand_search_scope(fake):
    r = run(fake, max_search_requests=1)
    assert r['query_coverage']['advisories']
    assert 'in:readme' not in fake.calls[0].url.params['q']
    assert r['state'] == 'partial' and len(fake.calls) == 1


def test_invalid_query_has_no_scope_advisory_or_network(fake):
    r = run(fake, queries=[{'facet': 'problem', 'terms': SECRET}])
    assert r['query_coverage'] is None and not fake.calls
    assert SECRET not in json.dumps(r)
