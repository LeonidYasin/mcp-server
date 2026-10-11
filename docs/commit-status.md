# get_commit_status — SHA-pinned checks and legacy statuses

The tool reads GitHub's combined legacy-status endpoint **and** the Checks API,
resolving the supplied SHA/ref to a full commit SHA first. Empty legacy statuses
can have a raw combined state of `pending`; that state alone is not evidence of
pending work and does not override successful Check Runs.

```json
{"owner":"LeonidYasin","repo":"mcp-server","sha":"main","max_pages":5,"max_rows":25}
```

## Bounds and output contract

- `max_pages`: integer 1–20, default 5, separately for each source; 100 entries
  requested per page. Invalid bounds, including booleans, fail before API calls.
- `max_rows`: integer 0–100, default 25, **per source**. This limits presentation,
  not aggregation. Zero returns counts/metadata with no individual rows.
- Read-only GET requests; no reruns, merging, or settings changes.
- Output remains MCP text: commit/status headings followed by one JSON line
  beginning `metadata: `. Consumers should parse this line rather than headings.
- Metadata contains `head_sha`, `commit_url`, `aggregate_state`, `complete`,
  `truncated`, `output_truncated`, `counts`, `legacy_statuses`, `check_runs`,
  and per-source `sources` with pages/fetched_count/total_count/error/completeness.
- Legacy rows retain id/context/state/description/target_url; check rows retain
  id/name/status/conclusion/head_sha/html_url/app and classified aggregate_state.
  Identical check names from different apps remain distinct.
- Failure/unknown/pending rows precede successful rows within a capped output.
  Counts cover **all fetched rows**, not just displayed rows.
- `complete` means both sources finished pagination for the resolved SHA.
  `truncated` covers either a pagination cap or output cap. Thus complete=true,
  truncated=true is valid if only presentation was shortened.
- Check Runs use `filter=latest` (GitHub's latest-run selection), not all history.
  Pagination links are never followed as arbitrary URLs; subsequent requests
  use the fixed GitHub endpoint with incremented page numbers.

## Aggregation policy

When either source is unavailable or incomplete, the aggregate is `unknown`,
**not** success; partial rows/counts remain diagnostic evidence. API/JSON errors,
malformed totals/rows, foreign SHA, duplicate row IDs, changed totals, or an empty
page before the advertised end prevent completeness. A page cap marks its source
truncated. No credentials or raw exception bodies are reflected in error fields.

For complete reads, precedence is:

1. `failure`: legacy failure/error or terminal failure/cancelled/timed_out/
   action_required/stale/startup_failure.
2. `unknown`: unfamiliar states/conclusions or inconsistent status/conclusion.
3. `pending`: legacy pending or checks queued/requested/pending/waiting/in_progress.
4. `no_checks`: both sources are genuinely empty.
5. `success`: all rows are success or the explicitly non-blocking neutral/skipped.

`neutral_skipped_policy=non_blocking`: neutral and skipped have separate counters.
An aggregate success does **not** mean skipped tests ran, that all required checks
exist, or that merging is permitted. `merge_eligibility=not_evaluated` is always
returned. Branch protection, required contexts, approvals, drafts, mergeability,
and policy enforcement belong to a separate PR preflight/merge workflow (#62).

## Safety and limitations

Texts and links are bounded. Common GitHub PAT/Bearer formats are redacted from
text; link credentials, query strings and fragments are removed. This is not a
universal detector for arbitrary secrets embedded in names or URL paths. Links
are references only; the tool never fetches them.

Commit identity is pinned, but mutable check/status data cannot be read as one
atomic snapshot across two APIs or multiple pages. Obvious pagination changes
are refused; stable totals cannot prove that state did not change mid-read.
An `unknown` result requires investigation, not an automatic merge or write retry.

Tests cover classification, SHA resolution, both paginated sources, limits,
malformed/error responses, duplicate IDs, redaction, output caps and Flask MCP
transport. Live GitHub and deployed-service checks are tracked in the PR; mocked
fixtures are not proof of deployment.
