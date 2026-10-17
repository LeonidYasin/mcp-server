"""Offline path-selection regressions; not a semantic quality benchmark."""
import pytest

from mcp_server.tools.github.repository_file_selection import select_files

DOCS = ['README.md', 'package.json', 'docs/architecture.md', 'LICENSE']
HANDLER = 'Skill_Exchange.Application/Services/User/Queries/Handlers/GetMatchingUsersHandler.cs'


def plan(paths, focus=None, comparison=None):
    return select_files(dict.fromkeys(paths), comparison=comparison, focus_path_terms=focus)


def sources(result):
    return [s for s in result['selected'] if s['role_hint'] == 'implementation']


@pytest.mark.parametrize('mechanism', [
    HANDLER, 'Skill_Exchange.Application/match_users.py',
    'Skill_Exchange.Application/calculateMatchScore.ts',
    'Skill_Exchange.Application/matching-core.go',
])
def test_basename_focus_beats_shared_project_namespace(mechanism):
    result = plan(DOCS + [
        'Skill_Exchange.Application/Auth/auth.cs',
        'Skill_Exchange.Application/Program/main.cs',
        'Skill_Exchange.Application/DTO/User.cs', mechanism,
    ], ['skill', 'match'])
    assert sources(result)[0]['path'] == mechanism
    assert 'match' in sources(result)[0]['focus_path_matches']
    assert sources(result)[0]['reason'] == 'caller_focus_path_prefix_hint'
    assert len(result['selected']) == result['max_files'] == 6
    assert result['semantic_relevance_verified'] is False
    assert result['selection_exhaustive'] is False


def test_directory_focus_still_precedes_unfocused_dispatch():
    result = plan(DOCS + ['src/matching/core.ts', 'src/server.py', 'src/main.py'], ['match'])
    assert sources(result)[0]['path'] == 'src/matching/core.ts'
    assert sources(result)[0]['focus_path_matches'] == ['match']


@pytest.mark.parametrize('status', ['added', 'modified'])
def test_observed_change_still_precedes_basename_focus(status):
    path = 'src/ordinary.py'
    result = plan(DOCS + [path, HANDLER], ['match'],
                  {'files': [{'path': path, 'status': status}]})
    assert sources(result)[0]['path'] == path
    assert sources(result)[1]['path'] == HANDLER
    assert sources(result)[0]['changed_in_observed_comparison'] is True


def test_focus_does_not_admit_ignored_or_declaration_paths():
    result = plan(DOCS + ['tests/Matching.cs', 'vendor/Matching.ts',
                         'src/Matching.d.ts', HANDLER], ['match'])
    assert [s['path'] for s in sources(result)] == [HANDLER]


def test_namespace_collision_selection_is_input_order_independent():
    entries = DOCS + [HANDLER, 'Skill_Exchange.Application/Auth/auth.cs',
                     'Skill_Exchange.Application/main.cs', 'src/matching/core.ts']
    assert plan(entries, ['skill', 'match']) == plan(list(reversed(entries)), ['skill', 'match'])


def test_absent_focus_preserves_generic_role_order():
    result = plan(DOCS + ['src/server.py', 'src/main.py', HANDLER])
    assert [s['path'] for s in sources(result)] == ['src/server.py', 'src/main.py']
    assert result['focus_path_terms_used'] == []
