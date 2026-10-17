"""Path-only policy regressions: no source execution or network access."""
import pytest

from mcp_server.tools.github.repository_file_selection import select_files


def plan(*paths, identity=None, comparison=None, focus=None):
    return select_files(dict.fromkeys(paths), comparison, identity, focus)


def paths(result):
    return [item['path'] for item in result['selected']]


DOCS = ('README.md', 'pyproject.toml', 'LICENSE')


def test_monorepo_diverse_roles_and_identity_are_only_hints():
    result = plan(*DOCS, 'Dockerfile', 'src/servers/main.py', 'src/auth/factory.py',
                  'src/servers/alpha/main.py', 'src/servers/acme/main.py', identity='acme/service')
    assert paths(result) == [*DOCS, 'src/servers/main.py', 'src/auth/factory.py', 'src/servers/acme/main.py']
    assert [x.get('implementation_role_hint') for x in result['selected'][3:]] == ['bootstrap', 'authorization', 'domain']
    assert result['selected'][-1]['reason'] == 'identity_domain_path_hint'
    assert result['selected'][-1]['identity_domain_match'] is True
    assert result['implementation_role_coverage_hint']['coverage_verified'] is False
    assert result['semantic_relevance_verified'] is False
    assert result['strategy'] == 'auto_paths_v2'
    assert result['implementation_slots_after_documents'] == 3


def test_four_documents_keep_two_source_slots_and_report_missing_roles():
    result = plan(*DOCS, 'docs/architecture.md', 'src/server.py', 'src/main.py', 'src/auth.py', 'src/config.py')
    assert paths(result)[-2:] == ['src/server.py', 'src/main.py']
    assert len(result['selected']) == 6
    assert result['implementation_slots_after_documents'] == 2
    assert result['implementation_role_coverage_hint']['not_selected'] == ['authorization', 'configuration']


def test_multiple_dispatch_namespaces_not_displaced_by_unknown_role():
    result = plan(*DOCS, 'docs/architecture.md', 'internal/zebra/server.go', 'internal/alpha/engine.go',
                  'internal/alpha/server.go', 'src/extra.py')
    assert paths(result)[-2:] == ['internal/alpha/engine.go', 'internal/zebra/server.go']


def test_changed_paths_override_role_diversity_and_identity():
    comparison = {'files': [{'path': 'src/extra.scala', 'status': 'added'},
                            {'path': 'src/catalog.scala', 'status': 'modified'},
                            {'path': 'src/auth.py', 'status': 'removed'}]}
    result = plan(*DOCS, 'docs/architecture.md', 'src/server.py', 'src/auth.py',
                  'src/extra.scala', 'src/catalog.scala', comparison=comparison)
    assert paths(result)[-2:] == ['src/extra.scala', 'src/catalog.scala']
    assert [x['reason'] for x in result['selected'][-2:]] == [
        'added_source_path_in_observed_comparison', 'changed_source_path_in_observed_comparison']


@pytest.mark.parametrize('name', ['auth.py', 'oauth.py', 'BaseAuthClient.py', 'AuthorizationProvider.ts',
                                  'UserCredentials.go', 'security/service.py'])
def test_authorization_word_hints(name):
    result = plan('src/' + name)
    assert result['selected'][0]['implementation_role_hint'] == 'authorization'


@pytest.mark.parametrize('identity', [None, '', 'bad', '../acme', 'https://acme/service', 'mcp/server', {'x': 1}])
def test_invalid_or_generic_identity_does_not_boost_domain(identity):
    result = plan(*DOCS, 'src/main.py', 'src/auth.py', 'src/servers/zeta/main.py',
                  'src/servers/alpha/main.py', identity=identity)
    assert paths(result)[-1] == 'src/servers/alpha/main.py'
    assert result['identity_tokens_used'] == []


def test_domain_group_requires_subdirectory_not_filename():
    result = plan('src/servers/main.py', 'src/servers/acme/main.py')
    assert [x['implementation_role_hint'] for x in result['selected']] == ['bootstrap', 'domain']


def test_unknown_sources_fill_remaining_slots_before_deployment():
    result = plan(*DOCS, 'src/server.rs', 'src/main.rs', 'src/catalog.rs', 'Dockerfile')
    assert paths(result)[-1] == 'src/catalog.rs'
    assert result['implementation_role_coverage_hint']['selected'] == ['bootstrap', 'dispatch', 'other']


def test_deployment_fallback_does_not_change_document_slot_accounting():
    result = plan(*DOCS, 'src/main.py', 'Dockerfile')
    assert paths(result)[-1] == 'Dockerfile'
    assert result['implementation_slots_after_documents'] == 3


def test_selection_stable_under_input_reversal():
    entries = (*DOCS, 'src/main.py', 'src/auth.py', 'src/servers/beta/main.py',
               'src/servers/alpha/main.py', 'src/server.py', 'src/config.py', 'src/extra.py')
    assert plan(*entries) == plan(*reversed(entries))


def test_excluded_paths_do_not_supply_roles():
    result = plan('README.md', 'tests/auth.py', 'vendor/server.go', 'generated/main.rs', 'src/index.d.ts')
    assert paths(result) == ['README.md']
    assert result['implementation_role_coverage_hint']['available'] == []


def test_apps_script_files_are_implementation_candidates_not_just_readme():
    result = plan('README.md', 'Kode.gs', 'vendor/hidden.gs', 'tests/test_bot.gs')
    assert paths(result) == ['README.md', 'Kode.gs']
    assert result['selected'][1]['role_hint'] == 'implementation'
    assert result['semantic_relevance_verified'] is False


@pytest.mark.parametrize('extension', ['mjs', 'cjs', 'mts', 'cts'])
def test_javascript_module_extensions_are_eligible_implementation(extension):
    result = plan('README.md', 'genaisrc/main.genai.' + extension)
    assert paths(result) == ['README.md', 'genaisrc/main.genai.' + extension]
    assert result['selected'][1]['role_hint'] == 'implementation'


@pytest.mark.parametrize('name', ['action.yml', 'action.yaml'])
def test_github_action_manifest_can_be_read_as_runtime_context(name):
    result = plan('README.md', name, 'genaisrc/run.genai.mts')
    assert paths(result) == ['README.md', name, 'genaisrc/run.genai.mts']
    assert result['selected'][1]['role_hint'] == 'runtime'


@pytest.mark.parametrize('name', ['types.d.mts', 'types.d.cts'])
def test_typescript_module_declarations_are_not_implementation(name):
    assert paths(plan('README.md', name)) == ['README.md']


def test_explicit_focus_prefers_mechanism_paths_over_generic_bootstrap_and_auth():
    result = plan(*DOCS, 'src/server.py', 'src/index.ts', 'src/auth.py',
                  'lib/matching/core.ts', 'sql/semantic_embedding.sql', focus=['match', 'embed'])
    chosen = paths(result)
    assert len(chosen) == 6 and chosen[:3] == list(DOCS)
    assert chosen[3:5] == ['lib/matching/core.ts', 'sql/semantic_embedding.sql']
    assert result['focus_path_terms_used'] == ['match', 'embed']
    assert [s['focus_path_matches'] for s in result['selected'][3:5]] == [['match'], ['embed']]
    assert all(s['reason'] == 'caller_focus_path_prefix_hint' for s in result['selected'][3:5])
    assert result['semantic_relevance_verified'] is False


def test_focus_path_prefixes_split_camel_case_and_never_expand_six_file_budget():
    result = plan(*DOCS, 'src/server.py', 'src/EstimateMaterials.ts',
                  'src/StateMachine.ts', 'src/transition_table.py', focus=['material', 'state', 'transit'])
    assert set(paths(result)[3:]) == {'src/EstimateMaterials.ts', 'src/StateMachine.ts', 'src/transition_table.py'}
    assert len(paths(result)) == 6


def test_observed_added_paths_still_precede_caller_focus_hints():
    result = plan(*DOCS, 'docs/architecture.md', 'src/extra.py', 'src/matching.py', 'src/server.py',
                  comparison={'files': [{'path': 'src/extra.py', 'status': 'added'}]}, focus=['match'])
    assert paths(result)[-2:] == ['src/extra.py', 'src/matching.py']
