"""Regression tests for #65: bounded compare output and honest metadata."""
import json
from unittest.mock import MagicMock

import pytest

from mcp_server.core.registry import ToolRegistry
from mcp_server.tools.github.branches import compare_branches


BASE = 'a' * 40
HEAD = 'b' * 40
MERGE_BASE = 'c' * 40


def make_client(count=15, patch='@@ -1 +1 @@\n-old\n+new', total_commits=1, link=''):
    files = [dict(filename=f'f{i}.txt', status='modified', additions=1,
                  deletions=1, patch=patch) for i in range(count)]
    data = dict(status='ahead', ahead_by=total_commits, behind_by=0,
                total_commits=total_commits, base_commit={'sha': BASE},
                merge_base_commit={'sha': MERGE_BASE}, commits=[{'sha': HEAD}],
                files=files)
    client = MagicMock()

    def request(method, url, **kwargs):
        assert method == 'GET'
        response = MagicMock()
        response.headers = {'Link': link}
        if url.endswith('/commits/main'):
            response.json.return_value = {'sha': BASE}
        elif url.endswith('/commits/feature%2Fbounded'):
            response.json.return_value = {'sha': HEAD}
        elif url.endswith(f'/compare/{BASE}...{HEAD}'):
            response.json.return_value = data
        else:
            raise AssertionError(f'unexpected request: {url}')
        return response

    client._request.side_effect = request
    return client, data


def compare(client, **kwargs):
    return compare_branches(client, owner='me', repo='repo', base='main',
                            head='feature/bounded', **kwargs)


def metadata(output):
    return json.loads(next(line[len('metadata: '):] for line in output.splitlines()
                           if line.startswith('metadata: ')))


@pytest.mark.parametrize('include_patch', [False, True])
@pytest.mark.parametrize('limit', [0, 1, 5, 300])
def test_limit_applies_to_summary_and_patch(limit, include_patch):
    client, _ = make_client()
    output = compare(client, max_files=limit, include_patch=include_patch)
    assert len([l for l in output.splitlines() if l.startswith('  [modified]')]) == min(limit, 15)
    assert output.count('diff --git ') == (min(limit, 15) if include_patch else 0)
    info = metadata(output)
    assert info['total_files'] == 15
    assert info['returned_files'] == min(limit, 15)
    assert info['truncated'] is (limit < 15)
    assert info['base_sha'] == BASE
    assert info['head_sha'] == HEAD
    assert info['merge_base_sha'] == MERGE_BASE


def test_default_limit_is_ten():
    client, _ = make_client()
    assert metadata(compare(client))['returned_files'] == 10


@pytest.mark.parametrize('name, value', [
    ('max_files', -1), ('max_files', 301), ('max_files', True),
    ('max_files', 1.5), ('max_files', '5'), ('max_files', None),
    ('max_patch_bytes', -1), ('max_patch_bytes', 262145),
    ('max_patch_lines', -1), ('max_patch_lines', 5001),
])
def test_invalid_limits_do_not_call_api(name, value):
    client = MagicMock()
    with pytest.raises(ValueError, match=name):
        compare(client, **{name: value})
    client._request.assert_not_called()


@pytest.mark.parametrize('byte_limit', [0, 1, 31, 64, 99])
def test_patch_utf8_byte_budget_is_global(byte_limit):
    client, _ = make_client(count=3, patch='+ёж' * 200)
    output = compare(client, include_patch=True, max_patch_bytes=byte_limit)
    section = output.split('--- patch ---\n', 1)[1]
    assert len(section.encode('utf-8')) <= byte_limit
    assert '\ufffd' not in section
    info = metadata(output)
    assert info['patch_truncated'] is True
    assert info['patch_bytes'] == len(section.encode('utf-8'))


@pytest.mark.parametrize('line_limit', [0, 1, 2, 5])
def test_patch_line_budget_is_global(line_limit):
    client, _ = make_client(count=3, patch='one\ntwo\nthree')
    output = compare(client, include_patch=True, max_patch_lines=line_limit)
    section = output.split('--- patch ---\n', 1)[1]
    assert len(section.splitlines()) <= line_limit
    assert metadata(output)['patch_truncated'] is True


def test_missing_patch_is_explicit():
    client, data = make_client(count=1)
    data['files'][0].pop('patch')
    info = metadata(compare(client, include_patch=True))
    assert info['patch_unavailable_files'] == 1
    assert info['patch_complete'] is False


@pytest.mark.parametrize('files_value', [[], None])
def test_no_files_is_not_an_error(files_value):
    client, data = make_client(count=0)
    data['files'] = files_value
    info = metadata(compare(client, include_patch=True))
    assert info['total_files'] == 0
    assert info['truncated'] is False
    assert info['patch_complete'] is True


def test_files_key_absent_is_unknown_not_empty_complete():
    client, data = make_client()
    data.pop('files')
    info = metadata(compare(client))
    assert info['total_files'] is None
    assert info['upstream_files_complete'] is False


def test_upstream_file_cap_is_unknown_total():
    client, _ = make_client(count=300)
    info = metadata(compare(client, max_files=300))
    assert info['total_files'] is None
    assert info['fetched_files'] == 300
    assert info['upstream_files_complete'] is False
    assert info['truncated'] is True


@pytest.mark.parametrize('total, link', [(251, ''), (1, '<https://api.github.com/next>; rel="next"')])
def test_incomplete_commits_are_reported(total, link):
    client, _ = make_client(total_commits=total, link=link)
    assert metadata(compare(client))['upstream_commits_complete'] is False


def test_api_error_is_not_reported_as_success():
    client = MagicMock()
    client._request.side_effect = RuntimeError('API unavailable')
    with pytest.raises(RuntimeError, match='API unavailable'):
        compare(client)


def test_refs_are_resolved_then_compare_uses_snapshot_shas():
    client, _ = make_client()
    compare(client)
    calls = client._request.call_args_list
    assert len(calls) == 3
    assert calls[0].args[1].endswith('/commits/main')
    assert calls[1].args[1].endswith('/commits/feature%2Fbounded')
    assert calls[2].args[1].endswith(f'/compare/{BASE}...{HEAD}')


def test_missing_sha_fails_before_comparison():
    client = MagicMock()
    client._request.return_value.json.return_value = {}
    with pytest.raises(ValueError, match='SHA'):
        compare(client)
    assert client._request.call_count == 1


def test_schema_is_discovered_with_limits():
    registry = ToolRegistry()
    registry.discover()
    tool = registry.get('compare_branches')
    schema = tool.to_mcp_tool_definition()['inputSchema']['properties']
    assert schema['max_files']['minimum'] == 0
    assert schema['max_files']['maximum'] == 300
    assert schema['max_patch_bytes']['maximum'] == 262144
    assert schema['max_patch_lines']['maximum'] == 5000


def test_missing_merge_base_is_null():
    client, data = make_client(count=0)
    data.pop('merge_base_commit')
    assert metadata(compare(client))['merge_base_sha'] is None


def test_mcp_text_response_remains_valid(monkeypatch):
    import mcp_server.server as server
    fake, _ = make_client()
    monkeypatch.setattr(server, 'GitHubClient', lambda token: fake)
    response = server.app.test_client().post('/mcp',
        headers={'Authorization': 'Bearer test-not-a-real-token'},
        json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {
            'name': 'compare_branches', 'arguments': {
                'owner': 'me', 'repo': 'repo', 'base': 'main',
                'head': 'feature/bounded', 'max_files': 5}}})
    payload = response.get_json()
    assert 'error' not in payload
    content = payload['result']['content']
    assert len(content) == 1 and content[0]['type'] == 'text'
    assert metadata(content[0]['text'])['returned_files'] == 5


def test_mcp_invalid_limit_is_error_without_github_requests(monkeypatch):
    import mcp_server.server as server
    fake = MagicMock()
    monkeypatch.setattr(server, 'GitHubClient', lambda token: fake)
    response = server.app.test_client().post('/mcp',
        headers={'Authorization': 'Bearer test-not-a-real-token'},
        json={'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {
            'name': 'compare_branches', 'arguments': {
                'owner': 'me', 'repo': 'repo', 'base': 'main',
                'head': 'feature/bounded', 'max_files': -1}}})
    payload = response.get_json()
    assert 'max_files' in payload['error']['message']
    assert 'result' not in payload
    fake._request.assert_not_called()
