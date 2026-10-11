# Combined step logs — #83

The four primary readers now support a conservative completed-runner-log format,
not permanent `unsupported` for every combined ZIP. Step display names come from
the **exact attempt's jobs/steps timeline**, never a guess from `Run ...` text.

## Supported boundary proof

1. Combined `N_job.txt` maps to one exact API job name/ID. Duplicate or sanitized
   names without an exact unique match are not inferred.
2. The snapshot is complete and its jobs/steps output is not truncated. Log queries
   with step_name request up to 100 jobs / 500 total metadata steps. The selected
   job and relevant execution timeline are completed, non-overlapping and valid.
3. Logs have UTC timestamp prefixes (optional BOM and 1–9 fractional digits).
   Group nesting is balanced with maximum depth 64. A nested `Run ...` group is
   NOT a step boundary.
4. Exactly one top-level `##[group]Run ...` appears in the selected step's API
   started_at second. Exactly one appears in the immediately following executed
   step's started_at second, equal to the selected step's completed_at second.
   Skipped steps do not invent execution. Missing intermediate step numbers,
   equal-start competing steps, gaps/overlaps and zero-duration target steps fail
   closed. Last-step completion/footer is not accepted as an end boundary.
5. Between those two markers there is no extra top-level Run boundary, no open
   group at the end, no timestamp outside the marker interval and no reversed
   timestamps. The next marker and all adjacent step text are excluded.

This validates the supported runner format against GitHub API provenance; it is
not cryptographic authenticity of user-controlled log text. Malicious or unusual
markers can cause an ambiguous refusal, not be trusted as display step names.
The parser currently checks balanced/timestamped format for the entire combined
file; unusual content outside the target can conservatively cause refusal too.

## Output and query behavior

`filter_mode=combined_step`; `boundary_source=attempt_timeline_unique_top_level_run_markers`;
`boundary_complete=true`; job_id, step_number/name, step started_at/completed_at,
run_attempt/SHA and original source_start_line/source_end_line are returned.
`line_offset` is used internally/preserved to keep grep/head/tail/offset line
numbers relative to the original combined file, not restarted at 1.
Regex context stays inside each selected step. Multiple matching steps in one
file retain separate identities; the same display name in different jobs retains
separate job IDs. Output budgets remain global after segmentation.

Original per-step ZIPs keep their existing supported behavior. If both per-step
and proven combined copies exist for the same job, prefer original files only
when they fully cover the matching step numbers/names; otherwise refuse ambiguous
mixed sources rather than silently dropping a step or double-counting it.

Residual errors are **case-specific**, not the default forever:
`step_boundaries_ambiguous`, `step_timeline_incomplete`, `step_filter_unsupported`
for unsupported formats/identity, `step_has_no_execution` for skipped targets.
A proven complete combined job with no matching timeline step is `step_not_found`,
not empty text. Supported step with zero regex hits is `no_matching_text`.
Fallback suggestions remain explicitly job-scoped and preserve the attempt.

## Evidence and remaining gates

Minimal synthetic fixtures reproduce the real TunXBox markers/timeline shape:
run 38102759021, 16KB step #22, attempts1/2. Initial read-only investigation showed
API step22 starts/completes at 01:56:27/02:00:42 (attempt1),
02:36:04/02:40:21 (attempt2); action Run markers at .9783269/.6706697 and
.3101678/.7514523 respectively. Identical emulator action titles occur for 4KB and
16KB, so names alone cannot select the step. Fixtures do not contain PATs or
signed URLs and are not presented as full real-log captures.

Live deployed segmentation checks remain required before declaring #83 complete:
verify exact step windows, exclude neighboring stages, compare against an
independent timeline/marker read, then CI and approved merge. Legacy diagnostic
wrappers/artifact attribution remain work under #69; production rollout, final
mindmap/Pages/docs are separate. ZIP transport/redaction/regex guarantees from
[attempt logs](workflow-attempt-logs.md) remain unchanged.
