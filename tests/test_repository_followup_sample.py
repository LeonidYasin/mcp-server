"""Offline consistency checks, NOT automatic validation of analyst claim semantics."""
import json
from pathlib import Path


SAMPLE = Path(__file__).resolve().parents[1] / 'docs/examples/repository-evidence-followup-sample.json'


def test_followup_claim_citations_fit_delivered_evidence_not_only_the_plan():
    sample = json.loads(SAMPLE.read_text())
    cases = {case['id']: case for case in sample['cases']}
    for claim in sample['claim_ledger']:
        assert claim['level'] in ('static_observation', 'review_question', 'commercial_hypothesis')
        assert claim['semantic_claim_automatically_verified'] is False
        assert claim['evidence']
        for ref in claim['evidence']:
            case = cases[ref['case_id']]
            actual = next(f for f in case['evidence']['files'] if f['path'] == ref['path'])
            assert actual['start_line'] <= ref['start_line'] <= ref['end_line'] <= actual['end_line']
            assert actual['content_sha256'] == ref['content_sha256']
            assert ref['url'] == actual['url'].split('#')[0] + f"#L{ref['start_line']}-L{ref['end_line']}"
            assert '/' + case['evidence']['revision']['sha'] + '/' in ref['url']


def test_followup_sample_distinguishes_planning_from_verified_reads():
    sample = json.loads(SAMPLE.read_text())
    assert sample['planning_reads']['identity_and_blob_verified'] is False
    assert sample['verification']['runtime_changed'] is False
    assert sample['verification']['foreign_code_executed'] is False
    for case in sample['cases']:
        evidence = case['evidence']
        assert case['arguments']['ref'] == evidence['revision']['sha']
        assert case['arguments']['file_selection'] == 'explicit'
        assert evidence['state'] == 'observed' and not evidence['gaps'] and evidence['error'] is None
        assert 0 < evidence['budget']['requests'] <= 12
        assert 0 < case['tool_text_utf8_bytes'] <= 65536
        assert all(source['http_status'] == 200 for source in evidence['sources'])
        for f in evidence['files']:
            assert f['requested_range_complete'] and f['returned_lines'] <= 100
            assert f['range_selection']['strategy'] == 'explicit'
            assert f['planning_bytes_match_verified_content_sha256']
            assert 'text' not in f
