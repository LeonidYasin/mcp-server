"""#60: preserve Git entry modes and reject stale-head mutations."""
import base64
import json
from unittest.mock import MagicMock

import pytest

from mcp_server.tools.github.batch import push_multiple_files

HEAD = 'a' * 40
OTHER = 'b' * 40
NEW = 'c' * 40
TREE = 'd' * 40


class Response:
    def __init__(self, data): self.data = data
    def json(self): return self.data


def client_for(entries=(), *, latest=HEAD, truncated=False, ref_error=None,
               commit_error=None, patch_error=None, returned_sha=NEW):
    calls = []
    reads = 0
    client = MagicMock()
    def request(method, url, **kwargs):
        nonlocal reads
        calls.append((method, url, kwargs))
        if method == 'GET' and '/git/ref/heads/' in url:
            reads += 1
            if ref_error: raise ref_error
            return Response({'object': {'sha': HEAD if reads == 1 else latest}})
        if method == 'GET' and '/git/commits/' in url:
            if commit_error: raise commit_error
            return Response({'tree': {'sha': TREE}})
        if method == 'GET' and '/git/trees/' in url:
            return Response({'tree': list(entries), 'truncated': truncated})
        if method == 'POST' and url.endswith('/git/blobs'):
            return Response({'sha': 'blob-' + str(len(calls))})
        if method == 'POST' and url.endswith('/git/trees'):
            return Response({'sha': 'new-tree'})
        if method == 'POST' and url.endswith('/git/commits'):
            return Response({'sha': NEW})
        if method == 'PATCH' and '/git/refs/heads/' in url:
            if patch_error: raise patch_error
            return Response({'object': {'sha': returned_sha}})
        if method == 'POST' and url.endswith('/git/refs'):
            return Response({'object': {'sha': returned_sha}})
        raise AssertionError((method, url, kwargs))
    client._request.side_effect = request
    return client, calls


def push(client, files=None, **kwargs):
    return push_multiple_files(client, owner='me', repo='repo', branch='main',
                               message='test', files=files or [{'path': 'a', 'content': 'new'}], **kwargs)


def item(path, mode, type='blob'):
    return dict(path=path, mode=mode, type=type, sha='old-blob')


def tree_payload(calls):
    return next(k['json'] for m,u,k in calls if m == 'POST' and u.endswith('/git/trees'))


def metadata(result):
    return json.loads(next(l[10:] for l in result.splitlines() if l.startswith('metadata: ')))


@pytest.mark.parametrize('mode', ['100644', '100755', '120000'])
def test_preserves_existing_blob_mode(mode):
    client, calls = client_for([item('a', mode)])
    result = push(client)
    assert '✅' in result
    assert tree_payload(calls)['tree'][0]['mode'] == mode
    assert tree_payload(calls)['tree'][0]['type'] == 'blob'
    assert metadata(result)['outcome'] == 'applied'


def test_new_file_defaults_to_ordinary_mode():
    client, calls = client_for()
    push(client)
    assert tree_payload(calls)['tree'][0]['mode'] == '100644'


@pytest.mark.parametrize('mode', ['100644', '100755', '120000'])
def test_explicit_mode_override(mode):
    client, calls = client_for([item('a', '100755')])
    push(client, files=[{'path': 'a', 'content': 'target', 'mode': mode}])
    assert tree_payload(calls)['tree'][0]['mode'] == mode


def test_mixed_files_use_one_tree_read_and_leave_other_entries_untouched():
    entries = [item('run.sh', '100755'), item('link', '120000'), item('plain', '100644'),
               item('unchanged', '100755')]
    files = [{'path': p, 'content': 'new'} for p in ['run.sh', 'link', 'plain', 'new.txt']]
    client, calls = client_for(entries)
    push(client, files=files)
    payload = tree_payload(calls)
    assert payload['base_tree'] == TREE
    assert [e['mode'] for e in payload['tree']] == ['100755', '120000', '100644', '100644']
    assert 'unchanged' not in [e['path'] for e in payload['tree']]
    reads = [(u,k) for m,u,k in calls if m == 'GET' and '/git/trees/' in u]
    assert len(reads) == 1 and reads[0][1]['params'] == {'recursive': '1'}


@pytest.mark.parametrize('mode', ['040000', '160000', '777', None, 100755])
def test_invalid_explicit_modes_fail_before_api(mode):
    client = MagicMock()
    with pytest.raises(ValueError, match='mode'):
        push(client, files=[{'path': 'a', 'content': 'new', 'mode': mode}])
    client._request.assert_not_called()


@pytest.mark.parametrize('entry', [item('a', '040000', 'tree'), item('a', '160000', 'commit'),
                                   item('a', 'unknown')])
def test_unsupported_existing_entry_refused_before_writes(entry):
    client, calls = client_for([entry])
    with pytest.raises(ValueError): push(client)
    assert all(m == 'GET' for m,_,_ in calls)


@pytest.mark.parametrize('entry', [item('a', '100644'), item('a', '120000'), item('a', '160000', 'commit')])
def test_existing_nondirectory_ancestor_cannot_be_replaced_implicitly(entry):
    client, calls = client_for([entry])
    with pytest.raises(ValueError): push(client, files=[{'path': 'a/b', 'content': 'new'}])
    assert all(m == 'GET' for m,_,_ in calls)


def test_truncated_tree_refused_before_blob_creation():
    client, calls = client_for(truncated=True)
    with pytest.raises(ValueError, match='tree'): push(client)
    assert all(m == 'GET' for m,_,_ in calls)


def test_initial_expected_head_mismatch_has_no_writes():
    client, calls = client_for()
    result = push(client, expected_head_sha=OTHER)
    assert metadata(result)['outcome'] == 'conflict'
    assert len(calls) == 1 and calls[0][0] == 'GET'


def test_matching_expected_head_and_nonforced_patch():
    client, calls = client_for()
    result = push(client, expected_head_sha=HEAD.upper())
    assert metadata(result)['base_head_sha'] == HEAD
    assert metadata(result)['expected_head_sha'] == HEAD
    patch = next(k['json'] for m,u,k in calls if m == 'PATCH')
    assert patch == {'sha': NEW, 'force': False}


def test_concurrent_head_change_before_patch_returns_conflict():
    client, calls = client_for(latest=OTHER)
    result = push(client, expected_head_sha=HEAD)
    assert metadata(result)['outcome'] == 'conflict'
    assert metadata(result)['observed_head_sha'] == OTHER
    assert not any(m == 'PATCH' for m,_,_ in calls)


@pytest.mark.parametrize('error', [RuntimeError('HTTP error 409: Conflict'),
                                  RuntimeError('HTTP error 422: Update is not a fast forward')])
def test_final_fastforward_rejection_is_conflict(error):
    client, _ = client_for(patch_error=error)
    assert metadata(push(client))['outcome'] == 'conflict'


def test_final_transport_error_is_unconfirmed_not_success_or_retry():
    client, calls = client_for(patch_error=RuntimeError('Request timeout after 30 seconds'))
    result = push(client)
    assert '✅' not in result
    assert metadata(result)['outcome'] == 'unconfirmed'
    assert sum(m == 'PATCH' for m,_,_ in calls) == 1


def test_ref_response_must_confirm_candidate_sha():
    client, _ = client_for(returned_sha=OTHER)
    result = push(client)
    assert '✅' not in result
    assert metadata(result)['outcome'] == 'unconfirmed'


@pytest.mark.parametrize('sha', ['', 'short', None, True])
def test_invalid_expected_sha_before_api(sha):
    client = MagicMock()
    with pytest.raises(ValueError, match='expected_head_sha'):
        push(client, expected_head_sha=sha)
    client._request.assert_not_called()


@pytest.mark.parametrize('path', ['', '/a', '../a', 'a/../b', 'a//b', './a', 'a/', 'a\\b', 'a\x00b'])
def test_invalid_paths_before_api(path):
    client = MagicMock()
    with pytest.raises(ValueError, match='path'):
        push(client, files=[{'path': path, 'content': 'new'}])
    client._request.assert_not_called()


@pytest.mark.parametrize('paths', [['a','a'], ['a','a/b']])
def test_duplicate_or_conflicting_paths_before_api(paths):
    client = MagicMock()
    with pytest.raises(ValueError, match='path'):
        push(client, files=[{'path':p,'content':'new'} for p in paths])
    client._request.assert_not_called()


def test_commit_lookup_404_is_not_empty_repo_fallback():
    client, calls = client_for(commit_error=RuntimeError('HTTP error 404: Not Found'))
    with pytest.raises(RuntimeError): push(client)
    assert all(m == 'GET' for m,_,_ in calls)


def test_ambiguous_ref_404_is_not_empty_repo_fallback():
    client, calls = client_for(ref_error=RuntimeError('HTTP error 404: Not Found'))
    with pytest.raises(RuntimeError): push(client)
    assert len(calls) == 1


def test_expected_head_on_empty_repo_is_conflict_without_writes():
    client, calls = client_for(ref_error=RuntimeError('HTTP error 409: Git Repository is empty.'))
    result = push(client, expected_head_sha=HEAD)
    assert metadata(result)['outcome'] == 'conflict'
    assert len(calls) == 1


def test_symlink_content_remains_link_target_blob():
    client, calls = client_for([item('a', '120000')])
    push(client, files=[{'path':'a','content':'../target'}])
    content = next(k['json']['content'] for m,u,k in calls if m=='POST' and u.endswith('/git/blobs'))
    assert base64.b64decode(content) == b'../target'
    assert tree_payload(calls)['tree'][0]['mode'] == '120000'


def test_schema_exposes_mode_and_expected_head():
    properties = push_multiple_files._mcp_tool.to_mcp_tool_definition()['inputSchema']['properties']
    assert set(properties['files']['items']['properties']['mode']['enum']) == {'100644','100755','120000'}
    assert properties['expected_head_sha']['type'] == 'string'


def test_bootstrap_explicit_executable_mode():
    client, calls = client_for(ref_error=RuntimeError('HTTP error 409: Git Repository is empty.'))
    result = push(client, files=[{'path':'a','content':'new','mode':'100755'}])
    assert metadata(result)['outcome'] == 'applied'
    assert 'bootstrap' in result
    assert tree_payload(calls)['tree'][0]['mode'] == '100755'
    assert 'base_tree' not in tree_payload(calls)
    assert not any(m=='GET' and '/git/trees/' in u for m,u,k in calls)


@pytest.mark.parametrize('error', [RuntimeError('HTTP error 403: Forbidden'),
                                  RuntimeError('HTTP error 409: Conflict')])
def test_ref_error_not_proven_empty_aborts_before_writes(error):
    client, calls = client_for(ref_error=error)
    with pytest.raises(RuntimeError): push(client)
    assert len(calls) == 1


@pytest.mark.parametrize('content', [None, 123, ['text']])
def test_nonstring_content_before_api(content):
    client=MagicMock()
    with pytest.raises(ValueError, match='content'):
        push(client, files=[{'path':'a','content':content}])
    client._request.assert_not_called()


def test_generic_ref_validation_error_is_not_asserted_to_be_head_conflict():
    client, _ = client_for(patch_error=RuntimeError('HTTP error 422: Branch protection validation failed'))
    assert metadata(push(client))['outcome'] == 'unconfirmed'


def test_legacy_json_string_files_supported():
    client, calls = client_for([item('a','100755')])
    push(client, files=json.dumps([{'path':'a','content':'new'}]))
    assert tree_payload(calls)['tree'][0]['mode'] == '100755'
