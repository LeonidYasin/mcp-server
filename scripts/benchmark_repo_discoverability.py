"""Offline MCP-visible token accounting; no GitHub/model requests or billing claims.

Optional local dependency: tiktoken. Input is prepared fixture JSON, not live data.
The legacy comparison covers a shared subset, not equivalent audit evidence.
Tokenizer initialization may fetch its public vocabulary if it is not cached.
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import io
import json
import os
import logging
import subprocess
from pathlib import Path
import sys
from unittest.mock import patch

import httpx
import tiktoken

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for flag in ('ENABLE_LOCAL_TOOLS', 'ENABLE_LOCAL_SHELL', 'ENABLE_SYNAPSE', 'ENABLE_FILE_UPLOADS'):
    os.environ[flag] = '0'
with contextlib.redirect_stdout(io.StringIO()):
    from mcp_server.server import registry, _normalize_content
from mcp_server.tools.github.client import GitHubClient

logging.getLogger('httpx').setLevel(logging.WARNING)
ENCODER = tiktoken.get_encoding('cl100k_base')
FIXED_TIME = '2026-10-16T00:00:00+00:00'
COMMIT = 'a' * 40


def packed(data):
    return json.dumps(data, ensure_ascii=False, separators=(',', ':'))


def measure(data):
    text = packed(data)
    return {'utf8_bytes': len(text.encode()), 'tokens_cl100k_base': len(ENCODER.encode(text))}


def blob(text, path):
    raw = text.encode()
    sha = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    return {'type': 'file', 'path': path, 'sha': sha, 'size': len(raw),
            'encoding': 'base64', 'content': base64.b64encode(raw).decode()}


def routes(case):
    readme = blob(case['readme'], 'README.md')
    manifest = blob(case['manifest'], 'pyproject.toml')
    return {
        '/repos/alice/demo': {'full_name': 'alice/demo', 'html_url': 'https://github.com/alice/demo',
            'description': None, 'language': 'Python', 'private': False, 'archived': False,
            'fork': False, 'size': 10, 'stargazers_count': 0, 'forks_count': 0, 'watchers_count': 0,
            'open_issues_count': 0, 'default_branch': 'main', 'created_at': FIXED_TIME,
            'updated_at': FIXED_TIME, 'pushed_at': FIXED_TIME, 'homepage': '', 'topics': [],
            'license': None, 'has_issues': True, 'has_pages': False},
        '/repos/alice/demo/topics': {'names': []},
        '/repos/alice/demo/commits/main': {'sha': COMMIT},
        '/repos/alice/demo/readme': readme,
        '/repos/alice/demo/contents/README.md': readme,
        '/repos/alice/demo/contents/pyproject.toml': manifest,
        '/repos/alice/demo/contents': [{'name': 'pyproject.toml', 'type': 'file', 'sha': manifest['sha']}],
        '/repos/alice/demo/releases/latest': {'tag_name': 'v0.1.0', 'name': 'Demo',
            'draft': False, 'prerelease': False, 'published_at': FIXED_TIME,
            'html_url': 'https://github.com/alice/demo/releases/tag/v0.1.0', 'body': 'Fixture release.'},
    }


def scenario(case, catalog, calls):
    data = routes(case)
    requests, rpc_calls, rpc_results = [], [], []

    def handle(request):
        assert request.method == 'GET' and request.url.host == 'api.github.com'
        assert request.url.path in data, request.url.path
        requests.append(request.url.path)
        return httpx.Response(200, json=data[request.url.path])

    client = GitHubClient('offline-fixture-not-a-credential')
    client._client.close()
    client._client = httpx.Client(base_url=client.BASE_URL, transport=httpx.MockTransport(handle))
    try:
        with patch('mcp_server.tools.github.repo_discoverability._now', return_value=FIXED_TIME):
            for index, (name, arguments) in enumerate(calls, 1):
                rpc_calls.append({'jsonrpc': '2.0', 'id': index, 'method': 'tools/call',
                                  'params': {'name': name, 'arguments': arguments}})
                out = registry.get(name).handler(client=client, **arguments)
                rpc_results.append({'jsonrpc': '2.0', 'id': index, 'result': _normalize_content(out)})
    finally:
        client._client.close()
    schema_metrics, args_metrics, results_metrics = measure(catalog), measure(rpc_calls), measure(rpc_results)
    totals = {k: schema_metrics[k] + args_metrics[k] + results_metrics[k] for k in schema_metrics}
    # Independent arithmetic check against explicit serialized components, not a second scenario run.
    independent = sum(len(ENCODER.encode(packed(v))) for v in (catalog, rpc_calls, rpc_results))
    assert totals['tokens_cl100k_base'] == independent
    return {'schema': schema_metrics, 'args': args_metrics, 'results': results_metrics,
            'mcp_visible_total': totals, 'tool_calls': len(calls),
            'response_rounds': {'parallel_lower_bound': 1, 'sequential_upper_bound': len(calls)},
            'mock_http_requests': len(requests),
            'transcript': {'schemas': catalog, 'requests': rpc_calls, 'responses': rpc_results}}


def benchmark(inputs):
    catalog = [t.to_mcp_tool_definition() for t in sorted(registry.get_all(), key=lambda t: t.name)]
    audit_def = next(t for t in catalog if t['name'] == 'audit_repo_seo')
    before_catalog = [t for t in catalog if t['name'] != 'audit_repo_seo']
    base = {'owner': 'alice', 'repo': 'demo'}
    baseline = [('get_repo_info', base), ('get_repo_topics', base),
                ('get_file_contents', {**base, 'path': 'README.md', 'ref': COMMIT}),
                ('get_file_contents', {**base, 'path': 'pyproject.toml', 'ref': COMMIT}),
                ('get_latest_release', base)]
    batched = [('get_repo_info', base), ('get_repo_topics', base),
               ('read_multiple_files', {**base, 'paths': ['README.md', 'pyproject.toml'], 'ref': COMMIT}),
               ('get_latest_release', base)]
    candidate = [('audit_repo_seo', {**base, 'project_type': 'mcp'})]
    rows, transcripts = [], []
    for case in inputs:
        for name, calls in (('legacy_shared_subset', baseline), ('legacy_batched_subset', batched), ('audit_full_scope', candidate)):
            metrics = scenario(case, catalog, calls)
            transcript = metrics.pop('transcript')
            transcripts.append({'case': case['case'], 'scenario': name, **transcript})
            rows.append({'case': case['case'], 'scenario': name, **metrics})
    evidence = {
        'method': 'offline_fixture_mcp_visible_accounting_v1', 'tokenizer': 'cl100k_base',
        'input_cases': [{'case': c['case'], 'kind': c['kind'], 'provenance': c['provenance'],
                         'readme_sha256': hashlib.sha256(c['readme'].encode()).hexdigest(),
                         'manifest_sha256': hashlib.sha256(c['manifest'].encode()).hexdigest()} for c in inputs],
        'schema_definition': measure(audit_def),
        'catalog_before_count': len(before_catalog), 'catalog_candidate_count': len(catalog),
        'catalog_before': measure(before_catalog), 'catalog_candidate': measure(catalog),
        'rows': rows,
        'comparison_plan': [{'grain': 'one fixed fixture and scenario', 'unit': 'cl100k_base tokens / UTF-8 bytes',
            'population': '2 chosen fixtures, same candidate full catalog in both scenarios',
            'disposition': 'table', 'reason': 'Software regression artifact, non-equivalent coverage; no headline savings ratio or audience-facing chart.'}],
        'limitations': [
            'Both scenarios include the same full candidate catalog exactly once. Actual host caching/discovery behavior is unknown.',
            'Legacy 5-call and batched 4-call subsets lack license/Issues/Pages/root completeness/pinned snapshot resolution and generated audit actions; NOT equivalent evidence.',
            'Pinned refs are supplied to baseline calls for free; ref-discovery cost is excluded. No claim that the baseline is optimal.',
            'Fixtures are not a representative repository sample. Mock HTTP counts are not live latency measurements.',
            'Parallel lower bound differs from sequential upper bound; five calls need not mean five model turns.',
            'Visible schemas+JSON-RPC args+normalized results only; system/chat/reasoning/follow-up prose/host wrapping excluded.',
            'Token counts are not Notion credits, actual model tokenizer, billed usage or proof of end-to-end monetary savings.',
            'Exact report synthesis equivalence, deployed/private workflow cost and host accounting remain pending #77.'
        ]}
    return evidence, transcripts


def prepare_inputs(path):
    cases = []
    for name, kind in [('synthetic-small', 'synthetic'), ('public-readme-snapshot', 'hybrid_fixture')]:
        if kind == 'synthetic':
            readme = '# Demo\n\n## Why\nAn offline comparison utility.\n\n## Quick start\nSee local instructions.\n\n## Limitations\nExperimental.\n'
            manifest = '[project]\nname="demo"\ndescription="Offline file comparison tool."\nkeywords=["python", "cli"]\n'
        else:
            readme = subprocess.check_output(['git', 'show', '0c12a375:README.md'], cwd=ROOT, text=True)
            manifest = subprocess.check_output(['git', 'show', '0c12a375:pyproject.toml'], cwd=ROOT, text=True)
        cases.append({'case': name, 'kind': kind, 'readme': readme, 'manifest': manifest,
            'provenance': 'Synthetic metadata/routes in both cases; second case only README/pyproject bytes from public LeonidYasin/mcp-server commit0c12a375. No claim of live API measurement.'})
    path.write_text(json.dumps(cases, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--transcript', type=Path)
    parser.add_argument('--prepare-inputs', action='store_true',
                        help='Explicitly write two fixtures; needs local git history containing 0c12a375.')
    args = parser.parse_args()
    if args.prepare_inputs:
        if args.input.exists():
            parser.error('refusing to overwrite existing raw input')
        prepare_inputs(args.input)
    inputs = json.loads(args.input.read_text())
    evidence, transcripts = benchmark(inputs)
    evidence['input_file_sha256'] = hashlib.sha256(args.input.read_bytes()).hexdigest()
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
    if args.transcript:
        args.transcript.write_text(json.dumps(transcripts, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'cases': len(inputs), 'scenarios': len(evidence['rows']),
                      'tokenizer': evidence['tokenizer'], 'result': 'recorded_no_billing_claim'}))


if __name__ == '__main__':
    main()
