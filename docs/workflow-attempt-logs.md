# Workflow logs — #69 part 2

The four readers `read_run_logs_offset`, `grep_run_logs`, `get_run_logs_by_step`
and `grep_workflow_logs` now select a run identity before downloading
`/actions/runs/{run_id}/attempts/{run_attempt}/logs`. Optional `run_attempt`
is explicit; otherwise latest is fixed at resolution, never silently substituted
after an older attempt fails. The snapshot must have complete valid jobs metadata.
`max_pages` bounds that prerequisite (1–20, default 5).

## Filtering and honest fallback

- Original ZIP entries `job/N_Step name.txt` support step-name substring filtering
  against **only the step portion**, not the job folder. Job-name filtering is
  against the job portion. `grep_workflow_logs.file_filter` retains its historical
  path-substring semantics; it is not a job/step identity guarantee.
- Combined `N_job.txt` now supports completed step segmentation when exact
  attempt timeline + unique top-level Run markers establish boundaries. See the
  [supported format and residual cases](workflow-step-boundaries.md).
- `Run ...` command titles alone are never treated as step display names.
  Missing/ambiguous boundaries return a case-specific error and a same-attempt
  bounded job-search suggestion; job fallback is NOT step-scoped.
- In mixed archives, fully covering original step files are preferred over a
  proven combined copy. Incomplete/contradictory copies fail closed, not duplicate
  hits or silently dropped steps. Unknown archive formats remain unsupported.
- Each returned segment labels file/job/step when known, attempt, filter mode,
  and source-relative line numbers. Regex context never crosses files.

## Return contract / migration

Readers return structured data, not the previous free-form grep/offset string.
`get_run_logs_by_step` preserves a `logs` list and adds labelled `segments`;
`read_run_logs_offset` preserves `limit` as an alias for `max_lines`.
Inspect `complete`, `error`, `output_truncated`, run identity and timestamps.
A valid zero-hit search is `no_matching_text` with `complete=true`;
`no_matching_log_files` and `empty_archive` are distinct. API 404/403/live-log
unavailability are errors with `complete=false`, never successful empty matches.
Run conclusion is preserved; no assertion that absent log errors means CI passed.
`completed_at` remains null unless supplied by the run endpoint.

Default global output budget: 200 lines and 16000 characters. Bounds are
`max_lines=1..1000`, `max_chars=1..65536`, `context=0..20`,
`max_matches=1..500`, pattern length <=256, offset 0..100000. Limits are global,
not multiplied per job. Empty windows and missing start_time markers are explicit.
Regex runs in a fixed-code subprocess killed/waited after 3 seconds, not on the
Gunicorn thread or by changing process-wide signal handlers.

## Transport / archive budgets

The authenticated fixed API endpoint is read headers-only, no redirect follow.
Its 302 destination must be HTTPS with a GitHub-owned host family used for
artifact results (`objects.githubusercontent.com`, `*.actions.githubusercontent.com`,
`productionresultssaN.blob.core.windows.net`). Destination URLs are not returned
or persisted. httpx log query strings are redacted. CDN uses a **new client**:
no inherited PAT, cookies, proxy credentials, or redirect follow.

8 MiB compressed/download cap; 8 MiB expanded total; 4 MiB per file; 256 entries;
100000 selected lines. Check advertised and streamed byte sizes. CDN timeout 20s
and bounded transfer iteration deadline 30s (not a strict whole-request deadline).
Unsafe names, duplicates, symlinks, encryption, non-txt entries, corrupt ZIPs,
excess sizes or incomplete reads fail closed. Decode UTF-8 with replacement;
never extract, execute or persist files. Credential-like strings/known PAT and
URL queries are redacted before search/output; not a universal secret scanner.
This can change matching compared to raw secret-bearing logs, intentionally.

## Remaining work (issue #69 stays open)

Legacy diagnostics/full/preview/checks wrappers are NOT migrated in this PR and
must not be assumed attempt-safe. Artifact attempt attribution remains separate:
existing name lookup already rejects duplicate names, but no attempt is guessed
from name/time. There is no workflow-log cache to update. Future caches must use
owner/repo/run_id/run_attempt/head_sha. Final docs, mindmap/Pages and production
rollout remain separate gates.
