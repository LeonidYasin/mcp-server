# Artifact attempt identity — #69

GitHub run artifact listing spans attempts. Real TunXBox run38102759021 currently
returns six artifacts in three repeated-name pairs, each with its own ID/time,
run ID and same HEAD SHA, but **no run_attempt in artifact/workflow metadata**.
There is no invented `/attempts/N/artifacts` request. Creation time, name suffix,
current latest attempt or a common SHA do NOT prove artifact attempt ownership.

## list_artifacts

Parameters: owner/repo/run_id, optional run_attempt, max_pages=1..20 (default5),
max_items=0..100 (default20). Pin run context (latest-at-resolution or explicit
attempt), then paginate the run-wide artifacts endpoint with stable total and
unique IDs, 100/page. Validate artifact/run/SHA metadata; generated errors, no
raw exception or archive_download_url output.

- `selected_run_attempt`/`selected_head_sha` describe **run context**, never the
  attempt of every artifact. `run_created_at`, `run_started_at`,
  `run_completed_at` are separate from artifact timestamps; completion is null
  when the API doesn't supply it.
- Without explicit run_attempt, scope is `run_all_attempts`, artifacts may have
  `artifact_run_attempt=null`, attempt_source=not_provided.
- Explicit attempt: only API-proven matching attempt + SHA rows go in artifacts.
  Unknown/incomplete attribution candidates are in unattributed_artifacts, never
  represented as matching that attempt. `attempt_attribution_incomplete`,
  complete=false, source_complete=true distinguishes identity uncertainty from
  a failed/partial enumeration. Known different attempts are excluded.
- If upstream provides a positive integer attempt field (workflow_run or direct),
  it is labelled github_api_metadata; conflicting/invalid fields are rejected.
  This positive path is fixture-covered, not claimed available in the current
  observed GitHub response. No producer-name/manifest heuristic is trusted.
- One global max_items budget is shared by proven rows and unknown candidates;
  zero is metadata-only, not evidence that the run has no artifacts.
- total_artifacts/fetched_artifacts/matching_artifacts/unattributed_count,
  source_complete/complete/output_truncated distinguish source vs presentation.
  Duplicate names expose bounded candidate IDs; their count is only in fetched
  data when enumeration is incomplete. Group output is capped separately and
  explicitly labelled when truncated. IDs, created/updated/expiry, digest when
  valid sha256, artifact_run_attempt, actual head_sha/run_id are returned.

## download_artifact

Existing exact-ID and unique exact-name/run behavior stays available. Duplicate
names still require an exact ID, EVEN if run_attempt is supplied; don't silently
choose a first/latest record or decide ownership using its time.

Optional run_attempt requires run_id. Resolve that exact run context and verify
artifact run/SHA/attempt before requesting any download capability. Unknown
attempt or missing SHA returns artifact_attempt_unknown, download_url=null;
known mismatch returns artifact_attempt_mismatch. No redirect request is made.

If GitHub omits attempt, callers may deliberately omit the strict run_attempt
condition and choose exact artifact_id using independent audit evidence. That
resolves the selected ID but **does not claim attempt ownership**; metadata keeps
artifact_run_attempt=null. Signed capability handling/CDN safety from #78 is
unchanged; never put the resulting URL in comments, fixtures or persistent logs.

## Remaining limits / rollout

This is honest API identity, not universal automatic attribution. Reliable
producer run/attempt manifests or attempt-qualified naming would require a
separately reviewed producer workflow protocol, not a guess in the MCP server.
No changes to TunXBox producer workflows or production services are made here.
Cache is not introduced. Live TEST enumeration/duplicate/unknown/refusal and
exact-ID gates remain mandatory; positive attempt proof currently has fixture
coverage only. Final docs/mindmap/Pages, #58 compiler diagnosis, #77 token audit
and #86 safe autofix replacement remain separate work.
