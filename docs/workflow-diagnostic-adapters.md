# Attempt-pinned diagnostic adapters — #69 / #83

Legacy tool names now delegate to bounded attempt readers/snapshots. Responses
are structured, not old free-form reports. This is a deliberate safety/contract
migration; examine `complete`, `error`, `output_truncated` and run identity.
No empty job set or absent regex match is interpreted as a successful build.
Run status/conclusion come from GitHub; heuristic matches are not root-cause proof.

## Tools

- `watch_build`: one pinned snapshot; interval/timeout remain ignored compatibility
  arguments, never polling. Job/step presentation caps are the snapshot caps.
- `get_latest_workflow_error`: discover latest run ID once, then pin an explicit
  attempt or latest-at-resolution snapshot. Empty/unavailable data is not success.
- `get_workflow_run_logs`: bounded global tail (tail_lines + context_before), OR
  grep when grep_pattern is supplied. Grep takes precedence instead of also
  downloading/rendering a second tail. tail_lines=0 without grep is metadata-only.
  No auto-claim that returned archive text belongs to failed jobs only: label
  `archive_or_explicit_job`, or explicit step scope when requested.
- `get_full_workflow_logs`: historical name, bounded archive window, NOT an
  unbounded/full guarantee. offset/head window and global max_lines/max_chars.
- `get_workflow_logs_preview`: limit is global across the archive, not per job,
  additionally limited by max_lines. Optional job_name/step_name scope preserved.
- `get_step_logs_via_checks`: deprecated name, now returns **attempt step logs**,
  with `source=attempt_step_logs_not_checks`. No SHA-wide latest Check Run is
  presented as an old attempt's step output. Use get_run_logs_by_step directly.
- Android/iOS diagnostic tools: one canonical function is exported from GitHub
  and build modules, eliminating discovery-order-dependent duplicate code.
  Optional job selection: unique exact name, then unique substring; without a
  name, sole job or a unique platform hint. Never first matching job. Missing or
  ambiguous jobs return candidate metadata, no log download. Platform hints are
  not proof that the job is actually an Android/iOS build.

Platform selection snapshots must be complete with all needed job/step metadata
(up to100 jobs /500 total steps); otherwise diagnostics refuse incompleteness.
Actual log query is re-pinned to the selected attempt and verifies exact job name
and ID again. Internal exact-name matching prevents `build` also leaking
`build-other`; identity changes cause refusal. The extra read is intentional;
there is no transactional GitHub snapshot or cache. `job_metadata_at_selection`
labels selection-time job state; log result state may be from the later read.

The fixed generic pattern catches `e: file`, `error:`, FAILURE, Exception,
Unresolved reference and fatal error. It is deliberately a bounded heuristic,
not the completed compiler-aware prioritization/root-cause audit from #58.
Zero matches in a failed job preserve failure and `no_matches_means_success=false`.
Step-scoped queries inherit the supported combined-step boundaries and residual
ambiguous formats from #84. All log readers share safe ZIP/CDN/redaction/regex
worker and global budgets. No existing log cache is introduced.

## Unsafe autofix removed

Review found old auto_fix_build guessed project paths and could write generic
Synapse templates directly to main. It is now a fail-closed, no-network/no-write
compatibility tool: `auto_fix_requires_reviewed_pr`, `writes_performed=false`.
This is NOT a working automatic fix. A replacement must inspect real repository
sources, create an isolated branch, show an actual diff, run tests and require
review/explicit merge — no hardcoded templates or direct main writes.
No old autofix was executed as part of testing.

Four unused GitHubClient legacy log methods (`get_job_logs`,
`get_workflow_run_logs`, `get_workflow_run_logs_files`,
`get_workflow_run_logs_text`) now fail closed with
`legacy_log_transport_disabled_use_attempt_readers`; external Python consumers
must migrate too. Do not reinstate their unbounded/no-follow-unsafe transport.
Workflow-file listing and artifact attempt attribution are separate audits.
Final compiler diagnostics, token audit #77, docs/mindmap/Pages and production
rollout remain separate gates; do not describe the project as fully finished.
