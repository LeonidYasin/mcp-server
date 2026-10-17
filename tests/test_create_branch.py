"""Exact branch copying: real client + offline HTTP transport, no credentials/network."""
import json

import httpx
import pytest

from mcp_server.tools.github.branches import create_branch
from mcp_server.tools.github.client import GitHubClient

SHA = '243e8583bcc373d51b62edb129f65c0f5a7bb173'
OTHER = 'b' * 40
BRANCH = 'deploy/single-user-vps'
PREFIX = '/repos/LeonidYasin/glacier-mcp'


def ref(sha=SHA):
    return {'ref': 'refs/heads/' + BRANCH, 'object': {'type': 'commit', 'sha': sha}}


@pytest.fixture
def client_factory():
    clients = []

    def make(*, existing=None, source_status=200, target_status=None,
             post_status=201, readback=SHA, readback_status=200, source_sha=SHA,
             race=None, malformed=False, timeout=False):
        calls = []
        ref_reads = 0

        def respond(request):
            nonlocal ref_reads
            calls.append(request)
            path = request.url.path
            if '/commits/' in path:
                if timeout:
                    raise httpx.ReadTimeout('offline timeout', request=request)
                return httpx.Response(source_status, json={'sha': source_sha})
            if request.method == 'POST':
                assert path == PREFIX + '/git/refs'
                assert json.loads(request.content) == {'ref': 'refs/heads/' + BRANCH, 'sha': SHA}
                return httpx.Response(post_status, json=ref())
            assert path == PREFIX + '/git/ref/heads/' + BRANCH
            ref_reads += 1
            if ref_reads == 1:
                if malformed:
                    return httpx.Response(200, json={})
                if target_status is not None:
                    return httpx.Response(target_status, json={'message': 'refused'})
                return httpx.Response(200 if existing else 404, json=ref(existing) if existing else {})
            if race is not None:
                return httpx.Response(200, json=ref(race))
            return httpx.Response(readback_status, json=ref(readback))

        client = GitHubClient('offline-test-not-a-credential')
        client._client.close()
        client._client = httpx.Client(base_url=client.BASE_URL, transport=httpx.MockTransport(respond))
        clients.append(client)
        return client, calls

    yield make
    for client in clients:
        client._client.close()


def call(client, **kwargs):
    return create_branch(client, owner='LeonidYasin', repo='glacier-mcp', branch=BRANCH, **kwargs)


def writes(calls):
    return [r for r in calls if r.method != 'GET']


@pytest.mark.parametrize('source', [{}, {'from_branch': BRANCH}, {'from_branch': 'v1.0'},
                                    {'from_branch': SHA}, {'from_sha': SHA}, {'from_sha': SHA.upper()}])
def test_sources_use_commits_and_exact_sha(client_factory, source):
    client, calls = client_factory()
    output = call(client, **source)
    assert output.startswith('✅') and SHA in output
    assert 'Read-back подтверждён' in output
    assert len(writes(calls)) == 1
    expected = source.get('from_sha', source.get('from_branch', 'main'))
    assert calls[0].url.path == PREFIX + '/commits/' + expected
    if '/' in expected:
        assert '%2F' in calls[0].url.raw_path.decode()
    assert all(r.method in ('GET', 'POST') for r in calls)


@pytest.mark.parametrize('existing, marker', [(SHA, 'ℹ️'), (OTHER, '❌ Конфликт')])
def test_existing_branch_never_overwritten(client_factory, existing, marker):
    client, calls = client_factory(existing=existing)
    assert call(client, from_sha=SHA).startswith(marker)
    assert not writes(calls)


@pytest.mark.parametrize('status', [401, 403, 429, 500])
def test_probe_failure_is_not_absence(client_factory, status):
    client, calls = client_factory(target_status=status)
    assert call(client, from_sha=SHA).startswith('❌')
    assert not writes(calls)


def test_malformed_existing_response_is_not_absence(client_factory):
    client, calls = client_factory(malformed=True)
    assert call(client, from_sha=SHA).startswith('❌')
    assert not writes(calls)


@pytest.mark.parametrize('status', [404, 422, 403, 500])
def test_source_failure_never_writes(client_factory, status):
    client, calls = client_factory(source_status=status)
    assert call(client, from_sha=SHA).startswith('❌')
    assert len(calls) == 1 and not writes(calls)


@pytest.mark.parametrize('bad', ['no-sha', OTHER])
def test_explicit_source_is_pinned(client_factory, bad):
    client, calls = client_factory(source_sha=bad)
    assert call(client, from_sha=SHA).startswith('❌')
    assert not writes(calls)


def test_source_timeout_never_writes(client_factory):
    client, calls = client_factory(timeout=True)
    assert call(client, from_sha=SHA).startswith('❌')
    assert not writes(calls)


@pytest.mark.parametrize('race, marker', [(SHA, 'ℹ️'), (OTHER, '❌ Конфликт')])
def test_concurrent_creation_readback_no_retry(client_factory, race, marker):
    client, calls = client_factory(post_status=422, race=race)
    assert call(client, from_sha=SHA).startswith(marker)
    assert len(writes(calls)) == 1


@pytest.mark.parametrize('status', [403, 404, 422, 500])
def test_post_refusal_never_reports_success_or_retries(client_factory, status):
    client, calls = client_factory(post_status=status, readback_status=404)
    assert call(client, from_sha=SHA).startswith('❌')
    assert len(writes(calls)) == 1


@pytest.mark.parametrize('options', [{'readback': OTHER}, {'readback_status': 403}])
def test_unconfirmed_readback_never_reports_success(client_factory, options):
    client, calls = client_factory(**options)
    assert call(client, from_sha=SHA).startswith('⚠️')
    assert len(writes(calls)) == 1


@pytest.mark.parametrize('kwargs', [{'from_sha': ''}, {'from_sha': None}, {'from_sha': 'abc123'},
    {'from_sha': 'g' * 40}, {'from_branch': ''}, {'from_branch': None},
    {'from_branch': 'main', 'from_sha': SHA}])
def test_invalid_source_before_io(client_factory, kwargs):
    client, calls = client_factory()
    with pytest.raises(ValueError):
        call(client, **kwargs)
    assert not calls


@pytest.mark.parametrize('branch', ['', '../bad', 'a..b', 'a.lock', 'a/.hidden', 'a//b',
    'bad name', 'bad[name', 'bad\\name', 'bad@{name', '-bad', 'bad/', 'bad.', '@'])
def test_invalid_branch_before_io(client_factory, branch):
    client, calls = client_factory()
    with pytest.raises(ValueError):
        create_branch(client, owner='me', repo='r', branch=branch, from_sha=SHA)
    assert not calls


def test_schema_exposes_exact_sha():
    tool = create_branch._mcp_tool
    assert tool.required == ['owner', 'repo', 'branch']
    assert tool.parameters['from_sha']['pattern'] == '^[0-9a-fA-F]{40}$'
