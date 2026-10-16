# Public repository evidence — candidate, not deployed

Second research layer after discovery: **selected source evidence, not a generated sales pitch**.
Existing `get_repo_info` gains explicit `mode=public_evidence`; default authenticated legacy
text is unchanged. No new registered tool, dependency, model, database or background worker.
File selection is explicit by default; opt-in `file_selection=auto` adds explained path
heuristics, not an LLM or a claim of semantic relevance.
This branch is independent of the Search candidate: callers can supply a repository discovered
with existing tools. No assumption that another draft has been merged or deployed.

## Request

```json
{"name":"get_repo_info","arguments":{"owner":"Johnmelo","repo":"codebadger-mola","mode":"public_evidence","ref":"9fbb0b63b54a105cb14a9a7ddcdfd47dfee4217f","evidence_files":[{"path":"pyproject.toml"},{"path":"src/services/query_executor.py","start_line":146,"max_lines":40}],"compare_parent":true}}
```

One repository per call. Default `file_selection=explicit` requires `evidence_files`:
1–6 unique paths, each object has `path`,
optional 1-based `start_line` (default1, max1000000), `max_lines` (default80, max100).
Paths use a conservative ASCII segment allowlist: no URLs, traversal, encoded separators,
backslashes or symlink/submodule following. Unsupported paths are invalid input, not evidence
that a file does not exist. Call existing `get_repo_tree`/`grep_file` first to choose paths;
selection and relevance are the analyst's responsibility. One bounded pinned Git tree read
verifies selected blob identities and regular-file modes; it does not select files for the
analyst in explicit mode. No README guesses in explicit mode.
`ref` is a branch/tag/SHA; default is the separately observed default branch.
Extra arguments and bool-as-integer are rejected. Evidence arguments in legacy mode are
rejected instead of silently ignored.

### Automatic selection

```json
{"name":"get_repo_info","arguments":{"owner":"Johnmelo","repo":"codebadger-mola","mode":"public_evidence","file_selection":"auto","ref":"9fbb0b63b54a105cb14a9a7ddcdfd47dfee4217f","compare_parent":true}}
```

Auto and `evidence_files` are mutually exclusive, even an empty explicit list. It uses the
same bounded pinned tree, not extra traversal requests. Known oversized files and non-regular
blobs are excluded before planning. A truncated tree produces a partial selection with an
explicit gap, even when all chosen file reads succeed. No recognizable paths is a gap,
not an empty repository or evidence that relevant implementation does not exist.

`auto_paths_v1` chooses up to six files with fixed diversity slots:
overview/README, runtime manifest, architecture document, license, two implementation files.
Unfilled slots can use deployment config, additional manifests, implementation or overview
documents. Root paths are preferred for documents/manifests; implementation paths prefer
observed changed source paths (added before modified/renamed), then conventional
engine/server/main/app/tools names. Added-file priority is an exploration heuristic,
not a claim of importance, originality or correctness.
Within equal priorities, depth and lexical order make selection deterministic.
No minimum stars or popularity signal enters selection.

Conventional dependency/vendor/generated/test/example directories, lock files, common test
names, Python `__init__`/`__main__` wrappers and minified/declaration files are excluded
heuristically. These are not perfect
semantic classifiers. Relevant examples, unconventional files, monorepo subprojects and
logic far below line80can be missed. Caller can follow up with explicit file/range requests.

With explicit `compare_parent=true` on a fork, comparison happens **before** auto planning
and reading Contents so its displayed changed source paths can be prioritized. Only the
at-most40displayed comparison rows are used, not a hidden uncapped list or patches. Removed
and unchanged rows do not receive changed-path priority. Refused comparison leaves an
explicit gap and a path-only fallback, not an assertion of no changes.

`file_selection` returns strategy, selected paths, role **hints**, fixed reasons, candidate
counts and `semantic_relevance_verified=false`. This is a plan; only entries in `files`
are delivered source evidence. The plan may remain after failed reads or output-budget
removal, and must not be cited as if the source were read. Each auto file asks for its
first80LF-delimited lines, still bounded to6000characters and whole lines per excerpt.
Unicode paragraph/line separator characters inside a source line do not shift GitHub
line anchors; CRLF line endings are normalized for display.

See [automatic-selection measurements and limitations](scenarios/repository-evidence-auto-sample.md).

## Evidence contract

- JSON **text** within the existing MCP text transport; existing dispatcher token gate remains.
  Outbound reads for this mode are anonymous. Default client auth, cookies, headers and params
  are not inherited. No authentication fallback; this mode does not investigate private repos.
- Read public metadata and resolve ref to a full commit SHA **before** selected file reads.
  Repositories must explicitly report `private=false`, matching identity, stable numeric ID
  and boolean fork flag. Unknown stars stay null; zero stars stay zero.
- GitHub Contents reads use `ref=SHA`, base64 only. Verify declared size and Git blob SHA-1,
  decode strict UTF-8, reject binary control bytes and submodules/symlinks. File cap128KiB.
  Before Contents, require the selected path's blob SHA and mode100644/100755 from the pinned
  commit's Git tree; otherwise Contents can transparently resolve a symlink. A truncated tree
  can verify an included entry, but missing entries remain unknown. An oversized/refused
  tree makes the selection unavailable; this conservative cap can exclude large repositories.
  No raw/CDN/download URLs from responses are followed.
- Per file: source index, exact blob SHA, full-content SHA256, full line count, actual returned
  range, excerpt, whole-file/range completeness flags, reconstructed commit-pinned citation.
  At most6000characters per excerpt; retain whole source lines only. Empty/out-of-range excerpts
  carry no fabricated line anchor. A range may be complete without including the whole file.
- `sources` record endpoint/params, attempt/completed-envelope timestamps, HTTP status and fixed
  error codes, numeric allowlisted rate hints only. Completion of JSON reading does not imply
  semantic validation. Metadata and branch movement are not an atomic snapshot.
- `compare_parent=true` expands **forks only**: independently verify public parent metadata,
  resolve its current default branch to SHA, then read one three-dot comparison in the fork's
  network. Show ahead/behind, merge-base, at most40file names/statuses and both pinned SHAs.
  No patches or commit messages are returned. GitHub's response may include patches within the
  bounded body; they are not interpreted, retained or described as reviewed.
- Three-dot means changes since merge-base, not an exact tree-to-tree diff, feature count,
  originality or proof the upstream has no equivalent implementation. Parent default branch
  may not be the historically relevant fork base. `file_list_complete=false` always:
  provider file caps, local display cap and single-page observation prevent a general guarantee.
- `state=observed` means selected observations completed, **not** repository completeness.
  Missing/refused/invalid files or comparisons create explicit gaps and `state=partial`.
  Failed identity/ref resolution is unavailable, not an empty repository.
  `coverage` always denies global/repository completeness, runtime/security verification and CI
  checking. Use existing `get_commit_status` separately for CI; green checks are not runtime proof.

## Safety and cost limits

At most12GETs (metadata + commit + tree +6files + parent metadata + parent commit + comparison),
no retries, redirects, pagination, execution, installation, arbitrary URLs or writes.
Per response256KiB, total bodies2MiB, output64KiB; triggering8KiB chunks may cross a body
bound and are rejected. Checked elapsed deadline30s, per-operation socket timeout5s:
these are checked limits, not hard real-time cancellation. Later operations stop after budget
exhaustion. Rate refusal remains a gap; no retry or credential upgrade. Anonymous limits can
become the practical bottleneck well before filesystem space.

If output would overflow, discard file excerpts and comparison, mark partial/output_budget;
never present silently omitted evidence as fully delivered. Exceptions, response error bodies
and headers are not dumped. Literal current-client credential copies are excluded from JSON
and decoded content; this is not semantic sanitization or a general secret scanner. Response
close errors are separately classified and cannot overwrite the original outcome.

All repository text is **untrusted data**, including README instructions addressed to an
assistant. It must never become commands or policy. No model is called by this collector.
No proof of demand, solo authorship, scientific correctness or exploitable vulnerabilities is
inferred. License metadata is only a hint: inspect LICENSE before reuse. The committed live
sample excludes verbatim third-party excerpts; their hashes and citation ranges remain.

## Report composition

After explicit or automatic selection, the analyst should write:

1. **Hook:** one understandable, source-supported distinction, not a restated description.
2. **Practical use:** user's task and expected input/output; mark untested use cases as hypotheses.
3. **Implemented mechanics:** cite exact pinned files and actual excerpt ranges.
4. **Fork contribution:** compare first, then read relevant changed files before interpreting.
5. **Readiness/cost/risk:** dependencies, license, resource needs, verified CI separately from runtime.
6. **Unknowns and next check:** no stars/popularity threshold, no claim of complete GitHub coverage.

Keep author's claims, code observations, runtime measurements and commercial hypotheses distinct.
Do not automatically turn a keyword, dependency or `ahead_by` into a feature or commercial score.
Similarity across unrelated repositories and actual trends require subsequent indexing/history;
this feature does not implement either.

## Verification

Offline tests exercise pinning, content integrity, ranges, fork comparison, anonymous transport,
budgets, malformed/refused sources, credential reflection, partial results, legacy compatibility
and actual MCP dispatcher JSON-text transport/token gate.
Auto tests also cover role diversity, deterministic ranking, fork-priority ordering, refusal
fallback, oversized files/symlinks, incomplete trees, input conflicts and Unicode line anchors.
Initial tests exposed two fixture issues (a non-existent dispatcher module and a body threshold
that was larger than the fixture); these were corrected, not counted as runtime fixes.
Review also identified a real safety gap before publication: Contents may dereference symlinks.
The final candidate now verifies regular-file mode and exact blob identity against the pinned
Git tree before reading Contents; regression tests cover this boundary.

See [the measured three-repository scenario](scenarios/repository-evidence-first-sample.md)
and [its observation metadata](examples/repository-evidence-public-sample.json).
That earlier explicit-selection sample retains the hashes of its earlier runtime; it is
not relabelled as a live run of later automatic-selection changes.