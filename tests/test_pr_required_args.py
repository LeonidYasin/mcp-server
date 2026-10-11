"""Required-argument regression coverage for PR #57; no live mutations."""
from unittest.mock import MagicMock

import pytest

from mcp_server.tools.github import pull_requests as pr

TOOLS = [pr.get_pull_request, pr.update_pull_request,
         pr.merge_pull_request, pr.close_pull_request]
ARGS = {'owner': 'test-owner', 'repo': 'test-repo', 'number': 123}


@pytest.mark.parametrize('tool', TOOLS, ids=lambda t: t.__name__)
@pytest.mark.parametrize('key', ['owner', 'repo', 'number'])
@pytest.mark.parametrize('mode', ['omitted', 'null'])
def test_missing_required_arg_does_not_call_github(tool, key, mode):
    args = dict(ARGS)
    if mode == 'omitted':
        args.pop(key)
    else:
        args[key] = None
    client = MagicMock()
    result = tool(client=client, **args)
    assert result == f'❌ Не переданы обязательные параметры: {key}'
    client._request.assert_not_called()


@pytest.mark.parametrize('tool', TOOLS, ids=lambda t: t.__name__)
def test_all_missing_args_reported_in_stable_order(tool):
    client = MagicMock()
    assert tool(client=client) == '❌ Не переданы обязательные параметры: owner, repo, number'
    client._request.assert_not_called()


@pytest.mark.parametrize('tool', TOOLS, ids=lambda t: t.__name__)
def test_required_schema_unchanged(tool):
    schema = tool._mcp_tool.to_mcp_tool_definition()['inputSchema']
    assert schema['required'] == ['owner', 'repo', 'number']


def test_get_valid_args_preserves_get_request():
    client = MagicMock()
    client._request.return_value.json.return_value = {
        'number': 123, 'title': 'test', 'state': 'open', 'merged': False,
        'user': {'login': 'test-owner'}, 'head': {'ref': 'feature'},
        'base': {'ref': 'main'}, 'html_url': 'https://example.invalid/pr/123',
    }
    assert 'PR #123: test' in pr.get_pull_request(client=client, **ARGS)
    client._request.assert_called_once_with('GET', '/repos/test-owner/test-repo/pulls/123')


def test_update_valid_args_preserves_only_supplied_fields():
    client = MagicMock()
    result = pr.update_pull_request(client=client, **ARGS, title='new title')
    assert result == '✅ PR #123 обновлён (title)'
    client._request.assert_called_once_with('PATCH', '/repos/test-owner/test-repo/pulls/123',
                                            json={'title': 'new title'})


def test_update_no_fields_does_not_call_github():
    client = MagicMock()
    assert 'Нечего обновлять' in pr.update_pull_request(client=client, **ARGS)
    client._request.assert_not_called()


def test_merge_valid_args_preserves_put_payload():
    client = MagicMock()
    client._request.return_value.json.return_value = {'merged': True, 'sha': 'test-sha'}
    result = pr.merge_pull_request(client=client, **ARGS, merge_method='squash', commit_title='test')
    assert result == '✅ PR #123 смержен: test-sha'
    client._request.assert_called_once_with('PUT', '/repos/test-owner/test-repo/pulls/123/merge',
                                            json={'merge_method': 'squash', 'commit_title': 'test'})


def test_close_valid_args_preserves_patch_payload():
    client = MagicMock()
    assert pr.close_pull_request(client=client, **ARGS) == '✅ PR #123 закрыт'
    client._request.assert_called_once_with('PATCH', '/repos/test-owner/test-repo/pulls/123',
                                            json={'state': 'closed'})


@pytest.mark.parametrize('tool', TOOLS, ids=lambda t: t.__name__)
def test_mcp_missing_args_return_valid_text_without_github_request(tool, monkeypatch):
    import mcp_server.server as server
    client = MagicMock()
    monkeypatch.setattr(server, 'GitHubClient', lambda token: client)
    # Raw HTTP reproduces malformed clients despite the advertised required schema.
    response = server.app.test_client().post('/mcp',
        headers={'Authorization': 'Bearer test-not-a-real-token'},
        json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
              'params': {'name': tool.__name__, 'arguments': {}}})
    body = response.get_json()
    assert 'error' not in body
    assert body['result']['content'] == [{'type': 'text', 'text':
        '❌ Не переданы обязательные параметры: owner, repo, number'}]
    client._request.assert_not_called()
