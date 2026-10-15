"""Synthetic Caddy planner/CAS cleanup, never real admin API or keys."""
import copy
import importlib.util
from pathlib import Path
import pytest

SPEC = importlib.util.spec_from_file_location('upload_test_proxy', Path(__file__).resolve().parents[1] / 'scripts/upload_test_proxy.py')
PROXY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROXY)
RID = 'upload-test-91-' + 'a'*12


def fixture_config():
    test = {'match':[{'path':['/test/*']}], 'group':'same-group', 'handle':[{'handler':'subroute','routes':[
        {'handle':[{'handler':'rewrite','strip_path_prefix':'/test'}]},
        {'handle':[{'handler':'reverse_proxy','upstreams':[{'dial':'127.0.0.1:3002'}]}]},
    ]}]}
    inner = [test, {'handle':[{'handler':'reverse_proxy','upstreams':[{'dial':'127.0.0.1:3001'}]}]}]
    guarded = {'match':[{'header':{'X-Api-Key':['synthetic-secret-never-export']}}],
               'handle':[{'handler':'subroute','routes':inner}]}
    host = {'match':[{'host':[PROXY.HOST]}], 'handle':[{'handler':'subroute','routes':[guarded,
        {'handle':[{'handler':'static_response','status_code':401,'body':'Unauthorized'}]}]}]}
    return {'apps':{'http':{'servers':{'srv0':{'routes':[host]}}}}}


def inner(config):
    return config['apps']['http']['servers']['srv0']['routes'][0]['handle'][0]['routes'][0]['handle'][0]['routes']


def test_plan_is_under_same_guard_and_changes_only_new_route():
    config = fixture_config()
    original = copy.deepcopy(config)
    parts, routes, route, key = PROXY.plan(config, RID)
    assert config == original and key == 'synthetic-secret-never-export'
    assert routes[1:] == inner(config)
    assert PROXY.at(config,parts) == inner(config)
    assert route['match'] == [{'path':[PROXY.NEW_PATH]}]
    assert route['group'] == 'same-group' and route['@id'] == RID
    assert 'synthetic-secret' not in PROXY.canonical(route)
    assert {n['strip_path_prefix'] for n,_ in PROXY.nodes(route) if isinstance(n,dict) and 'strip_path_prefix' in n} == {'/upload-test'}
    assert {n['dial'] for n,_ in PROXY.nodes(route) if isinstance(n,dict) and 'dial' in n} == {'127.0.0.1:3004'}


@pytest.mark.parametrize('kind', ['no_guard','or_unguarded','negative_guard','wildcard','wrong_host','custom_proxy','wrong_upstream','custom_rewrite','collision'])
def test_unsafe_or_ambiguous_plans_are_refused(kind):
    config=fixture_config()
    guarded=config['apps']['http']['servers']['srv0']['routes'][0]['handle'][0]['routes'][0]
    test=inner(config)[0]
    if kind=='no_guard': guarded.pop('match')
    elif kind=='or_unguarded': guarded['match'].append({'path':['/*']})
    elif kind=='negative_guard': guarded['match']=[{'not':guarded['match']}]
    elif kind=='wildcard': guarded['match'][0]['header']['X-Api-Key']=['*']
    elif kind=='wrong_host': config['apps']['http']['servers']['srv0']['routes'][0]['match']=[{'host':['other.invalid']}]
    elif kind=='custom_proxy': test['handle'][0]['routes'][1]['handle'][0]['headers']={'request':{'set':{'Authorization':['do-not-copy']}}}
    elif kind=='wrong_upstream': test['handle'][0]['routes'][1]['handle'][0]['upstreams'][0]['dial']='127.0.0.1:9999'
    elif kind=='custom_rewrite': test['handle'][0]['routes'][0]['handle'][0]['uri']='/other'
    elif kind=='collision': inner(config).insert(0,{'match':[{'path':[PROXY.NEW_PATH]}]})
    with pytest.raises(PROXY.ProxyError): PROXY.plan(config,RID)


def test_duplicate_candidate_refused():
    config=fixture_config()
    inner(config).append(copy.deepcopy(inner(config)[0]))
    with pytest.raises(PROXY.ProxyError,match='unique_protected'): PROXY.plan(config,RID)


def test_cleanup_preserves_unrelated_route_and_uses_root_etag(monkeypatch):
    config=fixture_config()
    parts,routes,route,_=PROXY.plan(config,RID)
    PROXY.at(config,parts)[:]=routes
    unrelated={'match':[{'path':['/another']}],'handle':[{'handler':'static_response','status_code':204}]}
    inner(config).insert(0,unrelated)
    requests=[]
    def admin(method,parts=(),payload=None,etag=None):
        if method=='GET': return copy.deepcopy(config),'root-etag'
        assert etag=='root-etag'
        requests.append(method)
        PROXY.at(config,parts)[:]=copy.deepcopy(payload)
    monkeypatch.setattr(PROXY,'admin',admin)
    assert PROXY.remove_route({'route':route})=='removed'
    assert inner(config)[0]==unrelated and len(inner(config))==3
    assert requests==['PATCH']
    assert PROXY.remove_route({'route':route})=='not_present'


def test_cleanup_refuses_changed_own_route(monkeypatch):
    config=fixture_config()
    parts,routes,route,_=PROXY.plan(config,RID)
    PROXY.at(config,parts)[:]=routes
    inner(config)[0]['terminal']=True
    monkeypatch.setattr(PROXY,'admin',lambda method,*args,**kw:(config,'etag') if method=='GET' else pytest.fail('must not patch'))
    with pytest.raises(PROXY.ProxyError,match='cleanup_route_changed'): PROXY.remove_route({'route':route})


def test_cleanup_retries_cas_without_overwriting_concurrent_edits(monkeypatch):
    config=fixture_config()
    parts,routes,route,_=PROXY.plan(config,RID)
    PROXY.at(config,parts)[:]=routes
    attempts=[]
    def admin(method,parts=(),payload=None,etag=None):
        if method=='GET': return copy.deepcopy(config),'etag-'+str(len(attempts))
        attempts.append(etag)
        if len(attempts)==1:
            inner(config).append({'handle':[{'handler':'static_response','status_code':202}]})
            raise PROXY.ProxyError('config_changed')
        PROXY.at(config,parts)[:]=payload
    monkeypatch.setattr(PROXY,'admin',admin)
    assert PROXY.remove_route({'route':route})=='removed'
    assert len(attempts)==2 and inner(config)[-1]['handle'][0]['status_code']==202
