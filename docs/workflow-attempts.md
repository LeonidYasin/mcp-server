# Workflow attempt snapshots — issue #69, part 1

`get_workflow_run_status` and `get_workflow_run_steps` accept optional
`run_attempt` (positive integer). Explicit attempts read only that attempt.
Without it, the first GET resolves latest, followed by an exact attempt GET
and jobs from `/actions/runs/{run_id}/attempts/{attempt}/jobs`.
`selection=latest_at_resolution` does not promise latest at response time.
Run ID, attempt and full HEAD SHA are validated; mismatches never fall back to
latest or merge jobs from another attempt. Job identity fields are checked when
provided; missing fields use `identity_source=attempt_endpoint`, not guessed
identity. A pinned attempt is not a transactional snapshot: jobs may change
while pagination runs (`atomic_snapshot=false`).

## Bounds and completeness

- `max_pages`: 1–20, default 5; 100 jobs per API page.
- `max_jobs`: 0–100, default 20, bounds jobs presented (also for flat steps).
- `max_steps`: 0–500, default 100, one global presentation budget.
- Failed/problematic jobs and steps precede successful rows. Preserve `number`
  for original step order; this response is not chronological ordering.
- `complete` means jobs pagination completed with valid, stable total and
  unique IDs. It does not mean workflow success or an atomic read.
- `total_jobs`, `fetched_jobs`, `returned_jobs` distinguish upstream total,
  fetched prefix and presentation. `total_steps=null` for incomplete sources;
  `fetched_steps` always describes only fetched jobs.
- `output_truncated` is independent of source completeness. `truncated` is
  true for either incomplete source or omitted output. Metadata-only caps of
  zero still fetch and validate source counts.
- `failed_step_count` counts failure steps in fetched jobs; `failed_steps` is
  limited to 100 labels. Empty jobs do not imply a successful workflow.
- Page errors retain valid prior pages, report a generated error code and
  `complete=false`; raw API exception bodies and tokens are not echoed.
- More than 500 steps in one job, duplicate steps, malformed rows, duplicate
  jobs or changed totals are rejected as incomplete, not silently skipped.

Every snapshot includes selected `run_attempt`, `head_sha`, run timestamps
and job/step IDs and timestamps. `completed_at` is null unless the run response
actually contains it: `updated_at` is NOT a workflow completion timestamp.
`list_workflow_runs` and `get_latest_run_id` expose upstream `run_attempt` and
`run_started_at` without extra requests; absent attempts are null, not inferred.

## Examples

```json
{"owner":"LeonidYasin","repo":"TunXBox","run_id":38102759021,"run_attempt":1,"max_jobs":10,"max_steps":40}
```

Use the same tuple `(owner, repo, run_id, run_attempt, head_sha)` when reasoning
about a snapshot. There is currently no server-side workflow-log cache; future
caching must include this identity, not just run ID or artifact name.

## Deliberately deferred to part 2

Four primary readers now have a separate [attempt logs contract](workflow-attempt-logs.md)
with bounded downloads and explicit combined-step unsupported fallback. Legacy
diagnostics/full/preview/checks wrappers and artifact attempt attribution remain
unmigrated. Do not treat a pinned snapshot as proof those legacy results or a
same-named artifact belong to its attempt.
Issue #69 remains open until these cases and live rerun checks pass.
