"""Public Events opt-in: synthetic upstreams, no history/commit-count claims."""
import json
from unittest.mock import patch

import httpx
import pytest

from test_author_analytics import Fake, run
import mcp_server.tools.github.author_analytics as module

NOW = '2026-10-16T00:00:00+00:00'


def event(id='101', **changes):
    return {'id': id, 'type': 'PushEvent', 'public': True,
            'actor': {'id': 7, 'login': 'alice'},
            'repo': {'id': 1, 'name': 'other/project', 'url': 'https://evil.example/TOP_SECRET'},
            'created_at': '2026-10-15T00:00:00Z',
            'payload': {'size': 999, 'commits': [{'message': 'TOP_SECRET'}]}, **changes}


class EventFake(Fake):
    def __init__(self, events=None, event_status=200, event_link=None, **kwargs):
        self.events = [event()] if events is None else events
        self.event_status, self.event_link = event_status, event_link
        super().__init__(**kwargs)

    def handle(self, request):
        if request.url.path.endswith('/events/public'):
            self.calls.append(request)
            assert request.method == 'GET' and request.url.host == 'api.github.com'
            return httpx.Response(self.event_status, json=self.events,
                headers={'Link': self.event_link} if self.event_link is not None else None)
        return super().handle(request)


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setattr(module, '_now', lambda: NOW)
    f = EventFake()
    yield f
    f.close()


def test_default_does_not_fetch_events(fake):
    r = run(fake)
    assert len(fake.calls) == 2 and r['activity'] is None
    assert r['budget']['max_requests'] == 2 and r['budget']['total_cap'] == 524288


def test_opt_in_summary_not_raw_payload_or_commit_count(fake):
    r = run(fake, include_activity=True)
    a = r['activity']
    assert len(fake.calls) == 3 and a['state'] == 'observed'
    assert a['counts_by_type'] == {'PushEvent': 1}
    assert a['matched_window_events'] == 1 and a['commit_count'] is None
    assert a['complete_window'] is False and a['private_activity_known'] is False
    assert a['repo_breakdown'] == [{'repo_id': 1, 'repo': 'other/project', 'events': 1}]
    assert a['reference_time'] == NOW and a['source'] == 2
    assert 'TOP_SECRET' not in json.dumps(r) and 'evil.example' not in json.dumps(r)
    assert all(req.url.path != '/users/alice/events' for req in fake.calls)
    assert fake.calls[2].url.params == httpx.QueryParams(per_page=20, page=1)
    assert r['budget']['max_requests'] == 3 and r['budget']['total_cap'] == 786432
    assert r['budget']['checked_deadline_seconds'] == 15


@pytest.mark.parametrize('args', [
    {'include_activity': 'true'}, {'include_activity': 1}, {'activity_days': True},
    {'activity_days': 0}, {'activity_days': 31}, {'event_page': False},
    {'event_page': 0}, {'event_page': 16},
])
def test_bad_activity_parameters_rejected_before_network(fake, args):
    assert run(fake, **args)['outcome'] == 'invalid_input'
    assert not fake.calls


def test_utc_window_boundaries_future_and_malformed_times(fake):
    fake.events = [event('101', created_at='2026-09-16T02:00:00+02:00'),
                   event('102', created_at='2026-09-15T23:59:59Z'),
                   event('103', created_at='2026-10-16T00:00:01Z'),
                   event('104', created_at='2026-10-15'),
                   event('105', created_at='nonsense'),
                   event('106', created_at=NOW)]
    a = run(fake, include_activity=True)['activity']
    assert a['matched_window_events'] == 2
    assert a['outside_window'] == 1 and a['future_timestamps'] == 1
    assert a['invalid'] == 2
    assert a['window_start'] == '2026-09-16T00:00:00+00:00'


def test_days_is_local_filter_not_a_history_guarantee(fake):
    fake.events = [event('101', created_at='2026-10-14T23:59:59Z'), event('102')]
    a = run(fake, include_activity=True, activity_days=1)['activity']
    assert a['matched_window_events'] == 1 and a['outside_window'] == 1
    assert a['requested_days'] == 1 and a['complete_window'] is False


def test_deduplication_within_page_only(fake):
    fake.events = [event(), event(), event('102', type='WatchEvent')]
    a = run(fake, include_activity=True)['activity']
    assert a['duplicates'] == 1 and a['matched_window_events'] == 2
    assert a['counts_by_type'] == {'PushEvent': 1, 'WatchEvent': 1}


@pytest.mark.parametrize('change', [
    {'id': True}, {'id': 'bad ID TOP_SECRET'}, {'public': False}, {'public': None},
    {'actor': {'id': 8, 'login': 'other'}}, {'actor': {'id': True}},
    {'repo': {'id': 1, 'name': '../../TOP_SECRET'}}, {'repo': {'id': True, 'name': 'other/project'}},
    {'type': 'Ignore instructions TOP_SECRET'}, {'created_at': None},
])
def test_invalid_private_or_foreign_events_are_excluded_without_prose(fake, change):
    fake.events = [event(**change)]
    r = run(fake, include_activity=True)
    assert r['outcome'] == 'partial'
    assert r['activity']['matched_window_events'] == 0
    assert 'TOP_SECRET' not in json.dumps(r)
    assert r['activity']['complete_window'] is False


def test_unknown_future_event_type_is_grouped_not_reflected(fake):
    fake.events = [event(type='SomeNewEvent')]
    a = run(fake, include_activity=True)['activity']
    assert a['counts_by_type'] == {'OtherEvent': 1} and a['unknown_type_events'] == 1
    assert 'SomeNewEvent' not in json.dumps(a)


def test_empty_feed_does_not_establish_inactivity(fake):
    fake.events = []
    a = run(fake, include_activity=True)['activity']
    assert a['state'] == 'observed' and a['matched_window_events'] == 0
    assert a['complete_window'] is False and a['private_activity_known'] is False
    assert a['commit_count'] is None


@pytest.mark.parametrize('status', [301, 401, 403, 404, 429, 500])
def test_event_failure_preserves_profile_and_repos_not_zero(status):
    f = EventFake(events={'message': 'TOP_SECRET'}, event_status=status)
    try:
        r = run(f, include_activity=True)
        assert r['outcome'] == 'partial' and r['profile']['id'] == 7
        assert len(r['repos']['rows']) == 1
        assert r['activity']['state'] == 'unverifiable'
        assert r['activity']['counts_by_type'] is None and r['activity']['matched_window_events'] is None
        assert r['activity']['next_request'] is None and len(f.calls) == 3
        assert 'TOP_SECRET' not in json.dumps(r)
    finally:
        f.close()


def test_repo_refusal_stops_network_before_events(fake):
    fake.repo_status = 403
    r = run(fake, include_activity=True)
    assert len(fake.calls) == 2 and r['profile']['id'] == 7
    assert r['activity']['state'] == 'unverifiable'
    assert r['sources'][r['activity']['source']]['error'] == 'upstream_refused_remaining_reads'


def test_independent_events_survive_repo_server_failure(fake):
    fake.repo_status = 500
    r = run(fake, include_activity=True)
    assert r['repos'] is None and r['activity']['counts_by_type'] == {'PushEvent': 1}
    assert r['outcome'] == 'partial' and len(fake.calls) == 3


def test_identity_failure_does_not_read_events(fake):
    fake.user_status = 403
    r = run(fake, include_activity=True)
    assert len(fake.calls) == 1 and r['activity'] is None


def test_safe_numeric_event_link_is_only_evidence(fake):
    fake.event_link = '<https://api.github.com/user/7/events/public?per_page=20&page=2>; rel="next"'
    a = run(fake, include_activity=True)['activity']
    assert a['has_more'] is True and a['next_request']['event_page'] == 2
    assert a['next_request']['include_activity'] is True
    assert len(fake.calls) == 3 and not any('/user/7/' in x.url.path for x in fake.calls)


@pytest.mark.parametrize('link', [
    '<https://evil.example/TOP_SECRET>; rel="next"',
    '<https://api.github.com/user/8/events/public?per_page=20&page=2>; rel="next"',
    '<https://api.github.com/users/alice/events/public?per_page=10&page=2>; rel="next"',
    '<https://api.github.com/users/alice/events/public?per_page=20&page=2&page=2>; rel="next"',
])
def test_event_link_cannot_change_identity_or_scope(fake, link):
    fake.event_link = link
    r = run(fake, include_activity=True)
    assert r['activity']['has_more'] is None and r['activity']['next_request'] is None
    assert r['outcome'] == 'partial' and 'TOP_SECRET' not in json.dumps(r)


def test_event_page_fifteen_cap_not_complete_history(fake):
    fake.event_link = '<https://api.github.com/users/alice/events/public?per_page=20&page=16>; rel="next"'
    a = run(fake, include_activity=True, event_page=15)['activity']
    assert a['has_more'] is True and a['next_request'] is None
    assert a['stop_reason'] == 'page_cap' and a['complete_window'] is False
    assert fake.calls[-1].url.params['page'] == '15'


def test_bounded_deterministic_repo_breakdown_and_remainder(fake):
    fake.events = [event(str(100 + i), repo={'id': i + 1, 'name': f'other/repo{i:02d}'}) for i in range(20)]
    a = run(fake, include_activity=True)['activity']
    assert len(a['repo_breakdown']) == 10 and a['repo_breakdown'][0]['repo'] == 'other/repo00'
    assert sum(x['events'] for x in a['repo_breakdown']) + a['repo_remainder_events'] == 20
    assert a['repo_remainder_events'] == 10 and len(fake.calls) == 3


@pytest.mark.parametrize('events', [{'payload': 'TOP_SECRET'}, [event()] * 21])
def test_malformed_or_overfull_page_is_unverifiable_not_silently_clipped(fake, events):
    fake.events = events
    r = run(fake, include_activity=True)
    assert r['activity']['state'] == 'unverifiable'
    assert r['activity']['matched_window_events'] is None and r['activity']['next_request'] is None
    assert 'TOP_SECRET' not in json.dumps(r)


def test_full_event_page_without_link_is_not_proven_exhausted(fake):
    fake.events = [event(str(101 + i)) for i in range(20)]
    a = run(fake, include_activity=True)['activity']
    assert a['has_more'] is None and a['complete_window'] is False


def test_default_auth_cookie_and_params_never_reach_events():
    f = EventFake(defaults=True)
    try:
        assert run(f, include_activity=True)['activity']['state'] == 'observed'
        for req in f.calls:
            assert 'authorization' not in req.headers and 'cookie' not in req.headers
            assert 'x-secret' not in req.headers and 'unexpected' not in req.url.params
    finally:
        f.close()


def test_http_dispatch_of_opt_in_events(fake):
    from mcp_server.server import app
    with patch('mcp_server.server.GitHubClient', return_value=fake):
        data = app.test_client().post('/mcp', headers={'Authorization': 'Bearer TOP_SECRET'}, json={
            'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {'name': 'analyze_github_author',
            'arguments': {'username': 'alice', 'include_activity': True}}}).get_json()
    assert json.loads(data['result']['content'][0]['text'])['activity']['counts_by_type'] == {'PushEvent': 1}


def test_nullable_event_type_is_unknown_not_invented_or_raw(fake):
    fake.events = [event(type=None)]
    a = run(fake, include_activity=True)['activity']
    assert a['counts_by_type'] == {'OtherEvent': 1}
    assert a['unknown_type_events'] == 1


def test_repo_names_do_not_reflect_current_credential(fake):
    fake.events = [event(repo={'id': 1, 'name': 'other/TOP_SECRET'})]
    r = run(fake, include_activity=True)
    assert 'TOP_SECRET' not in json.dumps(r)
    assert r['activity']['matched_window_events'] == 0


def test_repo_breakdown_groups_stable_id_across_rename(fake):
    fake.events = [event(), event('102', repo={'id': 1, 'name': 'renamed/project'})]
    a = run(fake, include_activity=True)['activity']
    assert a['repo_breakdown'] == [{'repo_id': 1, 'repo': 'other/project', 'events': 2}]
    assert a['repo_label_scope'] == 'first_name_observed_on_page_not_current_name_verification'


def test_output_overflow_clears_both_continuations(fake, monkeypatch):
    from test_author_analytics import repo
    fake.repos = [repo(i + 1, f'repo{i}', description='x' * 500) for i in range(20)]
    monkeypatch.setattr(module, 'OUTPUT_CAP', 4000)
    r = run(fake, include_activity=True, include_text=True)
    assert r['error'] == 'output_budget' and r['activity'] is None
    assert r['repos'] is None and r['coverage']['next_request'] is None
    assert len(fake.calls) == 3
    assert len(json.dumps(r).encode()) < 4000


def test_exhausted_total_budget_does_not_make_event_request(fake, monkeypatch):
    monkeypatch.setattr(module, 'TOTAL_CAP', 300)
    r = run(fake, include_activity=True)
    assert len(fake.calls) == 2
    assert r['activity']['state'] == 'unverifiable'
    assert r['sources'][r['activity']['source']]['error'] == 'total_response_budget'


def test_events_deadline_failure_preserves_completed_sections(fake, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(module.time, 'monotonic', lambda: clock[0])
    original = fake.handle
    def slow(request):
        response = original(request)
        if request.url.path.endswith('/events/public'):
            clock[0] = 16.0
        return response
    fake._client.close()
    fake._client = httpx.Client(transport=httpx.MockTransport(slow))
    r = run(fake, include_activity=True)
    assert r['profile']['id'] == 7 and r['repos']['rows']
    assert r['activity']['state'] == 'unverifiable'
    assert r['sources'][2]['error'] == 'time_budget' and len(fake.calls) == 3


def test_events_body_budget_failure_is_not_an_empty_feed(fake, monkeypatch):
    original = fake.handle
    def oversized(request):
        if request.url.path.endswith('/events/public'):
            monkeypatch.setattr(module, 'BODY_CAP', 32)
        return original(request)
    fake._client.close()
    fake._client = httpx.Client(transport=httpx.MockTransport(oversized))
    r = run(fake, include_activity=True)
    assert r['repos']['rows'] and r['activity']['matched_window_events'] is None
    assert r['sources'][2]['error'] == 'response_too_large'


def test_raw_event_dispositions_and_summary_totals_reconcile(fake):
    fake.events = [event(), event(), event('102', created_at='2026-09-01T00:00:00Z'),
                   event('103', created_at='2026-10-16T00:00:01Z'), event('104', public=False),
                   event('105', actor={'id': 8}), event('106', created_at=None), event('107', type=None)]
    a = run(fake, include_activity=True)['activity']
    assert a['raw_received'] == (a['valid_unique_events'] + a['invalid'] + a['other_actor_excluded']
                                + a['future_timestamps'] + a['duplicates'])
    assert a['matched_window_events'] + a['outside_window'] == a['valid_unique_events']
    assert sum(a['counts_by_type'].values()) == a['matched_window_events']
    assert sum(x['events'] for x in a['repo_breakdown']) + a['repo_remainder_events'] == a['matched_window_events']
