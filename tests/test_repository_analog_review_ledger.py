"""Offline citation/provenance consistency; does NOT prove analyst semantic judgments."""
import json
from pathlib import Path
import re

PATH = Path(__file__).resolve().parents[1] / 'docs/examples/repository-analog-reviewed-cases.json'


def test_review_claims_reference_delivered_pinned_files_and_retained_line_ranges():
    ledger = json.loads(PATH.read_text())
    sources = {s['id']: s for s in ledger['sources']}
    for case in ledger['cases']:
        assert case['level'] == 'selected_static_observation'
        assert case['semantic_claim_automatically_verified'] is False
        assert case['evidence'] and case['unknowns'] and case['reuse_path']
        for ref in case['evidence']:
            source = sources[ref['source_id']]
            assert source['start_line'] <= ref['start_line'] <= ref['end_line'] <= source['end_line']
            assert source['content_sha256'] == ref['content_sha256']
            assert ref['url'] == source['source_url'] + f"#L{ref['start_line']}-L{ref['end_line']}"
            assert re.fullmatch('[0-9a-f]{40}', source['ref'])
            assert '/' + source['ref'] + '/' in ref['url']
            assert re.fullmatch('[0-9a-f]{64}', source['content_sha256'])
            assert 'text' not in source and source['source_text_published'] is False


def test_connected_mcp_review_is_not_misrepresented_as_anonymous_candidate_acceptance():
    ledger = json.loads(PATH.read_text())
    v = ledger['verification']
    assert not any(v[k] for k in ('semantic_claim_automatically_verified', 'foreign_code_executed',
        'runtime_verified', 'global_complete', 'candidate_public_evidence_mode_used_for_new_reads',
        'public_mode_auth_fallback_added'))
    candidates = [s for s in ledger['sources'] if s['source_role'] == 'candidate']
    assert v['new_candidate_files'] == len(candidates) == 5
    assert v['new_candidate_text_bytes'] == sum(s['bytes'] for s in candidates)
    assert all(s['git_blob_matches_directory_and_file_metadata'] is True for s in candidates)
    assert all(s['pinned_tree_mode_chain_independently_verified'] is False for s in candidates)
    assert all('not candidate public_evidence' in s['transport'] for s in candidates)


def test_review_ledger_keeps_partial_analogs_and_does_not_invent_full_replacements():
    ledger = json.loads(PATH.read_text())
    assert {c['relationship'] for c in ledger['cases']} == {
        'shared_primitive_not_demonstrated_full_substitute', 'adjacent_quantity_estimation_and_export'}
    assert {c['baseline'] for c in ledger['cases']} == {
        'LeonidYasin/Tablebot-pipe-Advanced', 'LeonidYasin/ConstruBot'}
    assert all('license' in ' '.join(c['unknowns']).lower() for c in ledger['cases'])
