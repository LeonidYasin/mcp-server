"""User-facing MCP CI recipe: explicit attempt, honest scope, no external network."""
import ast
import json
from unittest.mock import patch

import pytest

from test_workflow_diagnostic_adapters import setup
from test_workflow_attempts import job

# Intentionally pytest-specific, not a universal compiler/root-cause detector.
# Whitespace/test-id boundaries avoid matching registry names rerun_failed_jobs.
PYTEST_PATTERN = r'\bFAILED\s+\S+::|\bE\s+(?:Failed:|AssertionError|TypeError|ValueError)|##\[error\]'


def call(client, name, **arguments):
    from mcp_server.server import app
    with patch('mcp_server.server.GitHubClient', return_value=client):
        response = app.test_client().post('/mcp', headers={'Authorization': 'Bearer LOCAL_FIXTURE'}, json={
            'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': name, 'arguments': {'owner': 'o', 'repo': 'r', 'run_id': 99,
                'run_attempt': 1, **arguments}}})
    envelope = response.get_json()
    assert 'error' not in envelope
    # Existing diagnostic dict outputs are Python-literal text, not JSON text.
    # literal_eval is deliberately not eval; do not claim structuredContent.
    return ast.literal_eval(envelope['result']['content'][0]['text'])


def test_old_failed_attempt_via_mcp_not_replaced_by_successful_latest(monkeypatch):
    c, calls, download = setup(monkeypatch)
    out = call(c, 'get_workflow_run_status', max_jobs=5, max_steps=5)
    assert out['conclusion'] == 'failure' and out['run_attempt'] == 1
    assert out['head_sha'] == 'a' * 40 and out['failed_steps'] == ['build / Compile']
    assert all('/attempts/1' in url for _, url, _ in calls)
    download.assert_not_called()


def test_ambiguous_step_then_explicit_job_search_keeps_scope_and_attempt(monkeypatch):
    j = job(id=101, attempt=1)
    j['steps'].append({**j['steps'][0], 'number': 2, 'name': 'Upload'})  # Overlapping timeline: unprovable.
    c, calls, download = setup(monkeypatch, pages=[{'total_count': 1, 'jobs': [j]}], files={
        '0_build.txt': '2026-10-02T00:00:10.0000000Z FAILED tests/test_guard.py::test_no_patch - Failed: must not patch'})
    step = call(c, 'get_run_logs_by_step', job_name='build', step_name='Compile', max_lines=10, max_chars=2000)
    assert step['error'] == 'step_boundaries_ambiguous' and not step['complete']
    assert not step['logs'] and not step['segments']
    assert step['fallback']['run_attempt'] == 1 and step['fallback']['omit'] == 'step_name'
    out = call(c, 'get_workflow_run_logs', job_name='build', grep_pattern=PYTEST_PATTERN,
               grep_context=0, max_lines=10, max_chars=2000)
    assert out['conclusion'] == 'failure' and out['matches'] == 1
    assert out['scope'] == 'archive_or_explicit_job'
    assert out['segments'][0]['filter_mode'] == 'combined_job'
    assert out['segments'][0]['step'] is None and out['run_attempt'] == 1
    assert out['no_matches_means_success'] is False
    assert all('/attempts/1' in url for _, url, _ in calls)
    assert download.call_count == 2  # Two explicit user-level reads, not an invisible retry.


@pytest.mark.parametrize('line', [
    'FAILED tests/test_guard.py::test_no_patch - Failed: must not patch',
    'E   AssertionError: expected guard refusal',
    'E   TypeError: unexpected argument',
    '##[error]Process completed with exit code 1.',
])
def test_pytest_recipe_finds_failure_without_registry_noise(monkeypatch, line):
    text = '2026-10-02T00:00:01Z [Registry] + rerun_failed_jobs\n2026-10-02T00:00:02Z ' + line
    c, _, _ = setup(monkeypatch, files={'build/1_Compile.txt': text})
    out = call(c, 'get_workflow_run_logs', job_name='build', grep_pattern=PYTEST_PATTERN,
               grep_context=0, max_lines=5, max_chars=1000)
    assert out['matches'] == 1 and out['returned_lines'] == 1
    assert 'rerun_failed_jobs' not in str(out['segments'])
    assert out['conclusion'] == 'failure' and out['no_matches_means_success'] is False


def test_broad_failed_pattern_is_not_root_cause_selection(monkeypatch):
    c, _, _ = setup(monkeypatch, files={'build/1_Compile.txt':
        '[Registry] + rerun_failed_jobs\nFAILED tests/test_guard.py::test_no_patch'})
    out = call(c, 'get_workflow_run_logs', grep_pattern='FAILED', grep_context=0)
    assert out['matches'] == 2  # Demonstrates the broad recipe's false positive, not a grep implementation bug.


def test_no_matching_failure_text_does_not_clear_failed_run(monkeypatch):
    c, _, _ = setup(monkeypatch, files={'build/1_Compile.txt': 'warning: no test summary retained'})
    out = call(c, 'get_workflow_run_logs', grep_pattern=PYTEST_PATTERN, grep_context=0)
    assert out['matches'] == 0 and out['conclusion'] == 'failure'
    assert out['no_matches_means_success'] is False


def test_ci_scenario_requires_existing_dispatcher_auth_before_client_construction():
    from mcp_server.server import app
    with patch('mcp_server.server.GitHubClient') as constructor:
        out = app.test_client().post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': 'get_workflow_run_status', 'arguments': {'owner': 'o', 'repo': 'r', 'run_id': 99}}}).get_json()
    assert out['error']['code'] == -32001
    constructor.assert_not_called()


def test_recorded_zero_duration_neighbors_do_not_prove_unique_target_boundary():
    from pathlib import Path
    from mcp_server.tools.github.workflow_step_boundaries import select
    from mcp_server.tools.github.workflow_log_archive import LogError
    data = json.loads((Path(__file__).resolve().parents[1] / 'docs/examples/ci-priority-live-scenario.json').read_text())
    j = data['supplementary_public_job_timeline']['job']
    same_second = [s['name'] for s in j['steps'] if s['started_at'] == '2026-10-15T22:58:57Z']
    assert same_second == ['Smoke import', 'Show version', 'Run tests']
    identity = {'complete': True, 'output_truncated': False, 'run_attempt': 1,
                'head_sha': data['historical_run_sha'], 'jobs': [j]}
    # Synthetic minimal well-formed marker text, NOT the historical raw archive.
    text = '2026-10-15T22:58:57.9000000Z ##[group]Run pytest -q\n2026-10-15T22:58:57.9100000Z ##[endgroup]'
    with pytest.raises(LogError, match='step_boundaries_ambiguous'):
        select('0_build (3.12).txt', text, 'build (3.12)', 'Run tests', identity)
