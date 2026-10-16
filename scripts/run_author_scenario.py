"""Manual local-dispatch scenario; no production access or model billing."""
import contextlib
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import time
from unittest.mock import patch


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-public-network', action='store_true', help='Explicitly permit at most three anonymous fixed-origin GETs')
    parser.add_argument('--output', required=True, help='Local report JSON path')
    args = parser.parse_args()
    if not args.allow_public_network:
        parser.error('--allow-public-network is required; no network call was made')
    # Registry startup output is not scenario data.
    with contextlib.redirect_stdout(io.StringIO()):
        from mcp_server.server import app
        from mcp_server.tools.github.client import GitHubClient
    prompt = ('Покажи до пяти публичных проектов LeonidYasin, их языки и доступную '
              'недавнюю активность; помоги выбрать, что открыть первым, и обозначь пробелы данных.')
    invocation = {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {
        'name': 'analyze_github_author', 'arguments': {'username': 'LeonidYasin',
        'per_page': 5, 'repo_page': 1, 'include_text': True,
        'include_activity': True, 'activity_days': 30, 'event_page': 1}}}
    fixture = 'LOCAL_SCENARIO_PLACEHOLDER_NOT_A_CREDENTIAL'
    calls = []
    client = GitHubClient(fixture)
    original_send = client._client.send
    def observed_send(request, **kwargs):
        assert len(calls) < 3 and request.method == 'GET'
        assert request.url.scheme == 'https' and request.url.host == 'api.github.com'
        assert request.url.path in ('/users/LeonidYasin', '/users/LeonidYasin/repos', '/users/LeonidYasin/events/public')
        assert 'authorization' not in request.headers and 'cookie' not in request.headers
        assert kwargs.get('auth') is None and kwargs.get('follow_redirects') is False
        entry = {'method': request.method, 'url': str(request.url),
                 'authorization_forwarded': False, 'cookie_forwarded': False,
                 'http_status': None}
        calls.append(entry)
        response = original_send(request, **kwargs)
        entry['http_status'] = response.status_code
        return response
    local = app.test_client()
    catalog_response = local.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})
    catalog = catalog_response.get_json()['result']['tools']
    selected = next(t for t in catalog if t['name'] == 'analyze_github_author')
    start_wall = datetime.now(timezone.utc).isoformat()
    start = time.perf_counter()
    try:
        with patch('mcp_server.server.GitHubClient', return_value=client), patch.object(client._client, 'send', side_effect=observed_send):
            response = local.post('/mcp', headers={'Authorization': 'Bearer ' + fixture},
                                  data=compact(invocation).encode(), content_type='application/json')
    finally:
        client._client.close()
    elapsed = time.perf_counter() - start
    envelope = response.get_json()
    result_text = envelope.get('result', {}).get('content', [{}])[0].get('text')
    result = json.loads(result_text) if result_text else None
    report = {'kind': 'manual_local_dispatch_public_author_scenario_not_deployed_host_acceptance',
        'candidate_runtime_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        'measured_started_at': start_wall, 'prompt': prompt, 'request': invocation,
        'selected_tool_definition': selected,
        'measurement': {'mcp_discovery_calls_local': 1, 'mcp_task_calls_local': 1,
            'anonymous_github_gets': len(calls), 'local_dispatch_elapsed_seconds': round(elapsed, 4),
            'prompt_utf8_bytes': len(prompt.encode()),
            'selected_tool_definition_compact_utf8_bytes': len(compact(selected).encode()),
            'full_local_catalog_tool_count': len(catalog),
            'full_local_catalog_http_body_bytes': len(catalog_response.data),
            'full_local_catalog_http_body_sha256': hashlib.sha256(catalog_response.data).hexdigest(),
            'task_request_http_body_bytes': len(compact(invocation).encode()),
            'task_response_http_body_bytes': len(response.data),
            'tool_result_text_utf8_bytes': len(result_text.encode()) if result_text else None,
            'upstream_body_bytes_accounted_by_reader': (result or {}).get('budget', {}).get('response_bytes'),
            'host_input_tokens': None, 'host_output_tokens': None, 'host_credits': None,
            'paid_model_invocations': 0, 'automatic_next_page_requests': 0},
        'http_status_local': response.status_code, 'github_calls': calls, 'result': result,
        'local_protocol_error': envelope.get('error'),
        'boundaries': ['Local Flask test client exercises dispatcher and candidate handler, not deployed MCP transport/session/security acceptance.',
            'Dispatcher uses a non-secret placeholder, not a real GitHub credential; outbound requests are verified anonymous.',
            'No AI model is invoked by this harness. A human-facing synthesis is a separate agent-authored artifact, not a model cost benchmark.',
            'Bytes and elapsed time are measured components, not token/credit/billing evidence or an equal-coverage savings comparison.',
            'Local tools/list measurement does not prove which catalog a real MCP host sends to a model.',
            'One explicit repo page and one Events page; no full inventory/history/commit-count claim.',
            'Public prose is untrusted data; no README/repo URL from output is fetched.',
            'No live retries, auth fallback, automatic pagination, writes, deployment or cleanup.']}
    text = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    assert fixture not in text
    Path(args.output).write_text(text)
    r = result or {}
    print(compact({'measurement': report['measurement'], 'outcome': r.get('outcome'),
        'repo_names': [x['full_name'] for x in (r.get('repos') or {}).get('rows', [])],
        'activity_state': (r.get('activity') or {}).get('state'),
        'source_errors': [s.get('error') for s in r.get('sources', [])]}))


if __name__ == '__main__':
    main()
