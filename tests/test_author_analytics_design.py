"""Validate design artifacts only; historical full proposal is distinct from the implemented phase1 handler."""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / 'docs/examples/github-author-analytics-contract.json').read_text())
EXAMPLES = json.loads((ROOT / 'docs/examples/github-author-analytics-design-fixtures.json').read_text())


def test_full_proposal_is_distinct_from_the_implemented_phase1():
    from mcp_server.server import registry
    assert CONTRACT['design_status'] == 'partially_implemented_profile_repos_only'
    assert CONTRACT['registration_change'] is True
    tool = registry.get(CONTRACT['candidate_name'])
    assert tool is not None
    assert set(tool.parameters) == set(CONTRACT['runtime_phase1']['accepted_fields'])
    assert 'include_activity' not in tool.parameters
    assert CONTRACT['runtime_phase1']['events_supported'] is False
    assert EXAMPLES['kind'] == 'design_examples_not_handler_outputs'


def test_proposed_budget_and_anonymous_scope_are_explicit():
    transport = CONTRACT['transport']
    assert transport['method'] == 'GET'
    assert transport['origin'] == 'https://api.github.com'
    assert transport['requests_max'] == len(transport['routes']) == 3
    assert transport['total_response_bytes_max'] == 3 * transport['response_bytes_max']
    assert transport['outbound_auth'] == 'none'
    assert transport['redirects'] is False and transport['retries'] == 0
    assert transport['cache'] is False
    assert CONTRACT['scope']['private_supported'] is False
    assert all(x['path'].startswith('/users/{username}') for x in transport['routes'])
    assert CONTRACT['scope']['zero_stars_included'] is True
    assert CONTRACT['scope']['forks_included'] is True
    assert CONTRACT['scope']['archived_included'] is True


def test_documentation_observation_is_not_a_silent_api_upgrade():
    obs = CONTRACT['provider_documentation_observation']
    assert obs['events_timeline_cap'] == 300
    assert obs['events_retention_days'] == 30
    assert obs['event_latency_seconds_max'] == 6 * 60 * 60
    assert obs['version_upgrade_authorized'] is False
    assert obs['runtime_api_version_to_reconfirm'] == '2022-11-28'
    assert len(obs['sources']) == 3
    assert all(len(x['sha256']) == 64 for x in obs['sources'])


@pytest.mark.parametrize('case', EXAMPLES['cases'], ids=lambda x: x['id'])
def test_expected_design_reports_do_not_invent_coverage_or_language_bytes(case):
    assert case['synthetic'] is True
    r = case['expected_report']
    assert r['outcome'] in ('observed', 'partial', 'unavailable')
    if r['outcome'] != 'observed':
        assert r['repos'] is None and r['languages'] is None
        assert r['zero_repositories_claim'] is False
        if r.get('coverage'):
            assert r['coverage']['complete_account_inventory'] is False
            assert r['coverage']['next_page'] is None
        return
    if 'activity' in r:
        a = r['activity']
        assert a['complete_window'] is False and a['commit_count'] is None
        assert a['private_activity_known'] is False
        assert sum(a['counts_by_type'].values()) == a['matched_window_events']
        assert a['provider_retention_days'] == 30
        return
    rows, c, languages = r['repos'], r['coverage'], r['languages']
    assert c['returned'] == len(rows) == languages['all_returned_repos']
    assert c['complete_account_inventory'] is False
    assert c['profile_total_is_hint'] is True
    assert languages['byte_weighted'] is False
    assert sum(languages['counts'].values()) == languages['known_language_repos']
    assert languages['known_language_repos'] + languages['unknown_language_repos'] == len(rows)
    assert languages['known_language_repos'] == sum(x['language'] is not None for x in rows)
    assert len({x['id'] for x in rows}) == len(rows)
    assert all(type(x['stars']) is int and x['stars'] >= 0 for x in rows)
    assert all(0 <= x['source'] < len(r['sources']) for x in rows)
    if c['has_more']:
        assert c['next_page'] == c['requested_page'] + 1
    else:
        assert c['next_page'] is None


def test_examples_include_zero_empty_fork_archive_and_partial_cases():
    cases = {x['id']: x['expected_report'] for x in EXAMPLES['cases']}
    assert any(x['stars'] == 0 for x in cases['zero_star_first_page']['repos'])
    assert cases['empty_public_listing']['repos'] == []
    assert cases['not_found_visibility_ambiguous']['zero_repositories_claim'] is False
    assert any(x['fork'] for x in cases['archived_and_forked_retained']['repos'])
    assert any(x['archived'] for x in cases['archived_and_forked_retained']['repos'])
    assert cases['second_page']['coverage']['requested_page'] == 2
    assert len(EXAMPLES['pending_handler_test_matrix']) >= 30
