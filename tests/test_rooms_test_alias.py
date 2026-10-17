"""Synthetic Caddy only: never make network calls, run timers or edit services."""
import copy
import importlib.util
import json
from pathlib import Path
import pytest

PATH = Path(__file__).resolve().parents[1] / 'scripts/rooms_test_alias.py'
SPEC = importlib.util.spec_from_file_location('rooms_alias_test_module', PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
ID = 'rooms_test_alias_' + 'a' * 32
KEY = 'synthetic-test-proxy-key-only'


def fixture():
    test = {'match': [{'path': ['/test/*']}], 'handle': [{'handler': 'subroute', 'routes': [
        {'handle': [{'handler': 'rewrite', 'strip_path_prefix': '/test'}]},
        {'handle': [{'handler': 'reverse_proxy', 'upstreams': [{'dial': '127.0.0.1:3002'}]}]},
    ]}]}
    production = {'handle': [{'handler': 'reverse_proxy', 'upstreams': [{'dial': '127.0.0.1:3001'}]}]}
    guard = {'match': [{'header': {'X-Api-Key': [KEY]}}],
             'handle': [{'handler': 'subroute', 'routes': [test, production]}]}
    host = {'match': [{'host': [MODULE.HOST]}], 'terminal': True,
            'handle': [{'handler': 'subroute', 'routes': [guard,
                {'handle': [{'handler': 'static_response', 'status_code': 401}]}]}]}
    return {'apps': {'http': {'servers': {'srv0': {'routes': [host]}}}}}


def descend(value, parts):
    for part in parts:
        value = value[part]
    return value


def test_add_remove_preserve_entire_original_and_identity_headers():
    config = fixture()
    unchanged = copy.deepcopy(config)
    parts, route, key = MODULE.plan(config, ID)
    assert config == unchanged and key == KEY
    assert route['match'] == [{'path': [MODULE.ALIAS]}] and route['terminal']
    assert route['handle'][0] == {'handler': 'rewrite', 'uri': '/mcp'}
    assert route['handle'][1]['upstreams'] == [{'dial': '127.0.0.1:3002'}]
    assert KEY not in json.dumps(route) and 'Authorization' not in json.dumps(route)
    assert parts[-1] == 0
    descend(config, parts[:-1]).insert(parts[-1], route)
    restored, found = MODULE.without_alias(config, {'id': ID, 'route': route})
    assert found == parts and restored == unchanged
    assert descend(config, parts) == route  # pure function, no in-place cleanup


@pytest.mark.parametrize('change', ['host', 'header_or', 'wildcard_key', 'wrong_port', 'auth_override'])
def test_plan_fails_closed_for_unexpected_routing(change):
    config = fixture()
    host = config['apps']['http']['servers']['srv0']['routes'][0]
    guard = host['handle'][0]['routes'][0]
    test = guard['handle'][0]['routes'][0]
    proxy = test['handle'][0]['routes'][1]['handle'][0]
    if change == 'host':
        host['match'][0]['host'] = ['other.example']
    elif change == 'header_or':
        guard['match'].append({'path': ['/*']})
    elif change == 'wildcard_key':
        guard['match'][0]['header']['X-Api-Key'] = ['*']
    elif change == 'wrong_port':
        proxy['upstreams'][0]['dial'] = '127.0.0.1:3001'
    else:
        proxy['headers'] = {'request': {'set': {'Authorization': ['Bearer synthetic-only']}}}
    with pytest.raises(RuntimeError):
        MODULE.plan(config, ID)


def test_cleanup_retains_unrelated_concurrent_change_and_refuses_foreign_route():
    config = fixture()
    parts, route, _ = MODULE.plan(config, ID)
    descend(config, parts[:-1]).insert(0, route)
    config['logging'] = {'logs': {}}
    stripped, _ = MODULE.without_alias(config, {'id': ID, 'route': route})
    assert stripped['logging'] == {'logs': {}}
    descend(config, parts)['terminal'] = False
    with pytest.raises(RuntimeError, match='Alias changed'):
        MODULE.without_alias(config, {'id': ID, 'route': route})


def test_existing_alias_and_duplicate_ids_refused():
    config = fixture()
    parts, route, _ = MODULE.plan(config, ID)
    descend(config, parts[:-1]).insert(0, route)
    with pytest.raises(RuntimeError):
        MODULE.plan(config, ID)
    descend(config, parts[:-1]).insert(0, copy.deepcopy(route))
    with pytest.raises(RuntimeError, match='Duplicate'):
        MODULE.without_alias(config, {'id': ID, 'route': route})


def test_cleanup_retries_cas_without_whole_config_restore(monkeypatch):
    config = fixture()
    parts, route, _ = MODULE.plan(config, ID)
    descend(config, parts[:-1]).insert(0, route)
    cleaned, _ = MODULE.without_alias(config, {'id': ID, 'route': route})
    snapshots = iter([(config, 'etag1'), (config, 'etag2'), (cleaned, 'etag3')])
    monkeypatch.setattr(MODULE, 'get_config', lambda: next(snapshots))
    calls = []
    def fake(url, method='GET', payload=None, headers=None):
        calls.append((url, method, payload, headers))
        return (412 if len(calls) == 1 else 200), b'', None
    monkeypatch.setattr(MODULE, 'request', fake)
    assert MODULE.remove({'id': ID, 'route': route}) == 'removed'
    assert len(calls) == 2 and all(call[1] == 'DELETE' and call[2] is None for call in calls)
    assert [call[3]['If-Match'] for call in calls] == ['etag1', 'etag2']


def test_private_state_permissions_and_no_redirect(tmp_path):
    _, route, _ = MODULE.plan(fixture(), ID)
    path = tmp_path / 'state.json'
    MODULE.private_write(path, MODULE.canonical({'id': ID, 'route': route}))
    assert path.stat().st_mode & 0o777 == 0o600
    assert MODULE.private_state(path)['id'] == ID
    with pytest.raises(FileExistsError):
        MODULE.private_write(path, 'overwrite')
    path.chmod(0o644)
    with pytest.raises(RuntimeError, match='private'):
        MODULE.private_state(path)
    assert MODULE.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.example') is None
