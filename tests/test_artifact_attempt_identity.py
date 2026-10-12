"""#69 artifact identity: API field or explicit unknown, never times/names."""
import json
from unittest.mock import MagicMock
import httpx
import pytest
from mcp_server.tools.github.artifacts import list_artifacts,download_artifact
from test_artifact_download import art,parse,URL
from test_workflow_attempts import run,SHA


def artifact(id=7,name='report',attempt=None,**kw):
    workflow={'id':99,'head_sha':SHA}
    if attempt is not None:workflow['run_attempt']=attempt
    return art(id=id,name=name,workflow_run=workflow,**kw)


def client(pages=None,row=None,latest=None):
    c=MagicMock();calls=[]
    def request(method,url,**kw):
        calls.append((method,url,kw))
        if url.endswith('/runs/99'):value=run() if latest is None else latest
        elif '/attempts/' in url:value=run(int(url.rsplit('/',1)[1]))
        elif url.endswith('/artifacts'):value=pages[kw['params']['page']-1] if pages is not None else {'total_count':1,'artifacts':[artifact()]}
        else:value=artifact() if row is None else row
        return httpx.Response(200,json=value)
    c._request.side_effect=request
    c.resolve_artifact_download.return_value={'outcome':'resolved','download_url':URL,'http_status':302}
    return c,calls


def listing(c,**kw):return list_artifacts(c,'o','r',99,**kw)
def downloading(c,**kw):return parse(download_artifact(c,owner='o',repo='r',run_id=99,artifact_id=7,**kw))


def test_default_context_latest_does_not_label_all_artifacts_latest():
    c,calls=client();data=listing(c)
    assert data['complete'] and data['source_complete'] and data['selected_run_attempt']==2
    assert data['scope']=='run_all_attempts' and data['artifacts'][0]['artifact_run_attempt'] is None
    assert data['unknown_attempts_in_fetched']==1 and data['artifacts'][0]['attempt_source']=='not_provided'
    assert not any('/attempts/2/artifacts' in u for m,u,k in calls)


def test_explicit_attempt_unknown_candidates_not_presented_as_matches():
    c,calls=client();data=listing(c,run_attempt=1)
    assert not data['complete'] and data['source_complete'] and data['attempt_filter_complete'] is False
    assert data['artifacts']==[] and len(data['unattributed_artifacts'])==1
    assert data['error']=='attempt_attribution_incomplete' and data['selected_run_attempt']==1
    assert not any(u.endswith('/runs/99') for m,u,k in calls)


def test_duplicate_names_across_attempts_expose_exact_ids_without_time_guess():
    rows=[artifact(id=7,created_at='2026-10-01'),artifact(id=8,created_at='2026-10-02')]
    c,_=client(pages=[{'total_count':2,'artifacts':rows}]);data=listing(c)
    assert data['duplicate_names'][0]['candidate_ids']==[7,8]
    assert all(r['artifact_run_attempt'] is None for r in data['artifacts'])
    assert [r['created_at'] for r in data['artifacts']]==['2026-10-01','2026-10-02']


def test_name_that_says_attempt2_is_not_attempt_proof():
    c,_=client(row=artifact(name='run99-attempt2-report'));data=downloading(c,run_attempt=2)
    assert data['outcome']=='artifact_attempt_unknown' and data['download_url'] is None
    c.resolve_artifact_download.assert_not_called()


def test_positive_api_attempt_metadata_filtered_not_inferred():
    rows=[artifact(id=7,attempt=1),artifact(id=8,attempt=2)]
    c,_=client(pages=[{'total_count':2,'artifacts':rows}]);data=listing(c,run_attempt=1)
    assert data['complete'] and data['attempt_filter_complete'] and data['matching_artifacts']==1
    assert data['artifacts'][0]['artifact_id']==7 and data['artifacts'][0]['attempt_identity_verified']


def test_known_attempt_without_head_sha_not_enough_to_filter_or_download():
    row=artifact(attempt=1);row['workflow_run'].pop('head_sha')
    c,_=client(pages=[{'total_count':1,'artifacts':[row]}],row=row)
    data=listing(c,run_attempt=1)
    assert data['artifacts']==[] and not data['attempt_filter_complete']
    assert downloading(c,run_attempt=1)['outcome']=='artifact_attempt_unknown'
    c.resolve_artifact_download.assert_not_called()


def test_explicit_attempt_known_matching_download_resolves_exact_id():
    c,calls=client(row=artifact(attempt=1));data=downloading(c,run_attempt=1)
    assert data['outcome']=='resolved' and data['artifact_run_attempt']==1 and data['selected_run_attempt']==1
    assert data['download_url']==URL
    c.resolve_artifact_download.assert_called_once_with('o','r',7)


def test_explicit_attempt_mismatch_refuses_redirect():
    c,_=client(row=artifact(attempt=2));data=downloading(c,run_attempt=1)
    assert data['outcome']=='artifact_attempt_mismatch' and data['download_url'] is None
    c.resolve_artifact_download.assert_not_called()


def test_exact_id_without_attempt_keeps_supported_download_and_unknown():
    c,_=client();data=downloading(c)
    assert data['outcome']=='resolved' and data['artifact_run_attempt'] is None
    assert data['run_id']==99 and data['head_sha']==SHA


@pytest.mark.parametrize('mutation',[
    lambda r:r['workflow_run'].update(id=100),lambda r:r['workflow_run'].update(id=True),
    lambda r:r['workflow_run'].update(head_sha='b'*40),lambda r:r['workflow_run'].update(head_sha='bad'),
    lambda r:r['workflow_run'].update(run_attempt=True),lambda r:r['workflow_run'].update(run_attempt=0),
    lambda r:r.update(run_attempt=2,workflow_run={'id':99,'head_sha':SHA,'run_attempt':1}),
    lambda r:r.update(expired=None),lambda r:r.update(size_in_bytes=True),lambda r:r.update(id=True),
])
def test_bad_artifact_identity_listing_and_download_fail_closed(mutation):
    row=artifact();mutation(row)
    c,_=client(row=row,pages=[{'total_count':1,'artifacts':[row]}])
    assert listing(c)['error']=='artifact_identity_or_lookup_unavailable'
    assert downloading(c,run_attempt=1)['outcome']=='unknown'
    c.resolve_artifact_download.assert_not_called()


@pytest.mark.parametrize('kw',[{'run_attempt':0},{'run_attempt':True},{'max_pages':0},{'max_pages':21},{'max_items':-1},{'max_items':101},{'max_items':True}])
def test_invalid_listing_before_api(kw):
    c,calls=client();assert listing(c,**kw)['error']=='invalid_input' and not calls


def test_global_row_cap_shared_with_unknown_and_metadata_only():
    rows=[artifact(id=7,attempt=1),artifact(id=8),artifact(id=9)]
    c,_=client(pages=[{'total_count':3,'artifacts':rows}]);data=listing(c,run_attempt=1,max_items=2)
    assert len(data['artifacts'])+len(data['unattributed_artifacts'])==2 and data['output_truncated']
    data=listing(c,max_items=0)
    assert data['artifacts']==[] and data['duplicate_names']==[] and data['fetched_artifacts']==3


def test_page_cap_and_successful_empty_are_distinct():
    c,_=client(pages=[{'total_count':2,'artifacts':[artifact()]}]);data=listing(c,max_pages=1)
    assert not data['source_complete'] and data['error']=='lookup_incomplete' and data['fetched_artifacts']==1
    c,_=client(pages=[{'total_count':0,'artifacts':[]}]);data=listing(c,run_attempt=1)
    assert data['complete'] and data['source_complete'] and data['total_artifacts']==0


def test_stable_pagination_and_duplicate_id_guard():
    pages=[{'total_count':2,'artifacts':[artifact(id=7)]},{'total_count':2,'artifacts':[artifact(id=8)]}]
    c,calls=client(pages=pages);assert listing(c)['complete']
    assert [kw['params']['page'] for m,u,kw in calls if u.endswith('/artifacts')]==[1,2]
    pages[1]['artifacts'][0]['id']=7;c,_=client(pages=pages)
    assert listing(c)['error']=='artifact_identity_or_lookup_unavailable'


def test_api_exception_does_not_echo_pat_signed_url_or_claim_empty():
    c,_=client();c._request.side_effect=RuntimeError('Bearer ghp_DO_NOT_ECHO '+URL)
    data=listing(c);assert not data['complete'] and data['error']=='artifact_identity_or_lookup_unavailable'
    assert 'ghp_DO_NOT_ECHO' not in str(data) and URL not in str(data)


def test_duplicate_name_download_remains_ambiguous_even_with_requested_attempt():
    c,_=client(pages=[{'total_count':2,'artifacts':[artifact(id=7,attempt=1),artifact(id=8,attempt=2)]}])
    data=parse(download_artifact(c,owner='o',repo='r',run_id=99,name='report',run_attempt=1))
    assert data['outcome']=='ambiguous' and data['candidate_ids']==[7,8]
    c.resolve_artifact_download.assert_not_called()


def test_requested_attempt_requires_run_id_before_metadata():
    c,calls=client()
    data=parse(download_artifact(c,owner='o',repo='r',artifact_id=7,run_attempt=1))
    assert data['outcome']=='invalid_input' and not calls
