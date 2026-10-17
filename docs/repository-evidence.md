# Public repository evidence — candidate, not deployed

Second research layer after discovery: **selected source evidence, not a generated sales pitch**.
Existing `get_repo_info` gains explicit `mode=public_evidence`; default authenticated legacy
text is unchanged. No new registered tool, dependency, model, database or background worker.
File selection is explicit by default; opt-in `file_selection=auto` adds explained path
heuristics, not an LLM or a claim of semantic relevance.
The original evidence candidate is independent of Search. This local integration tree also
includes the public Search candidate and an [idea-to-analog workflow](repository-analogs.md);
that does not imply either draft was merged or deployed.

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

### Question-led explicit follow-up

An analyst can follow a first observation with additional explicit ranges at the **same full SHA**.
This adds no automatic call-graph traversal or background reads. A separate call is needed for
a second range of the same path (paths must be unique within a request). All normal verification
and budgets apply anew; a prior read is not trusted as a cached integrity verdict.
See the [question-led follow-up scenario](scenarios/repository-evidence-followup-sample.md)
for credential-client and write-control chains, an explicit claim ledger and remaining unknowns.
Only delivered file ranges support citations; plans and failed reads do not.

### Automatic selection

```json
{"name":"get_repo_info","arguments":{"owner":"Johnmelo","repo":"codebadger-mola","mode":"public_evidence","file_selection":"auto","ref":"9fbb0b63b54a105cb14a9a7ddcdfd47dfee4217f","compare_parent":true}}
```

Auto and `evidence_files` are mutually exclusive, even an empty explicit list. It uses the
same bounded pinned tree, not extra traversal requests. Known oversized files and non-regular
blobs are excluded before planning. A truncated tree produces a partial selection with an
explicit gap, even when all chosen file reads succeed. No recognizable paths is a gap,
not an empty repository or evidence that relevant implementation does not exist.

`auto_paths_v2` chooses up to six files. It first reserves available overview/README,
runtime manifest, architecture document and license slots, then fills **all remaining slots**
with implementation candidates. If source candidates run out, deployment config, additional
manifests and documents can fill the remaining budget. Root paths are preferred for documents.
Observed changed source paths retain first priority (added before modified/renamed), even when
this reduces role diversity. Added-file priority does not establish importance or originality.

For otherwise equal change status, prefer unused recognized implementation role hints:
dispatch, bootstrap, authorization, domain integration, configuration, then other source.
An unrecognized role does not displace a repeated recognized role merely for diversity.
Repeated roles prefer a previously unselected namespace/group. Conventional path/stem words,
not code semantics, determine roles: e.g. `server`/`engine`, `main`/`index`, auth-related words,
`servers/<group>/...` or `connectors/<group>/...`, and `config`/`settings`.
Within a domain role, an exact group match against non-generic owner/repository name tokens
is a weak preference. It does **not** establish the project's primary integration, authorship,
originality or business value. No repository-specific exceptions or popularity signals are used.
Known source roots, conventional stems, depth and lexical order break remaining ties.

The plan reports per-file `implementation_role_hint`, `implementation_group_hint`,
`identity_domain_match` and fixed reason, plus `identity_tokens_used`,
`implementation_slots_after_documents` and `implementation_role_coverage_hint`
(available/selected/not_selected, always `coverage_verified=false`). With four document slots,
only two implementation files fit; with three, up to three fit. Hints depend on the observed
eligible tree, not a verified inventory of all architectural roles. This version adds no
traversal request or larger file budget. See the
[monorepo regression sample](scenarios/repository-evidence-monorepo-sample.md).

Conventional dependency/vendor/generated/test/example directories, lock files, common test
names, Python `__init__`/`__main__` wrappers and minified/declaration files are excluded
heuristically. These are not perfect
semantic classifiers. Relevant examples, unconventional files, monorepo subprojects and
unrecognized functions or logic outside the selected window can be missed. Caller can
follow up with explicit file/range requests.

With explicit `compare_parent=true` on a fork, comparison happens **before** auto planning
and reading Contents so its displayed changed source paths can be prioritized. Only the
at-most40displayed comparison rows are used, not a hidden uncapped list or patches. Removed
and unchanged rows do not receive changed-path priority. Refused comparison leaves an
explicit gap and a path-only fallback, not an assertion of no changes.

`file_selection` returns strategy, selected paths, role **hints**, fixed reasons, candidate
counts and `semantic_relevance_verified=false`. This is a plan; only entries in `files`
are delivered source evidence. The plan may remain after failed reads or output-budget
removal, and must not be cited as if the source were read. Planned auto `start_line` is null
until a file is successfully decoded and its window selected. Returned evidence carries
the actual start/end and `range_selection`; the successful plan entry is updated to match.
Each auto file returns at most80LF-delimited lines, still bounded to6000characters and
whole lines per excerpt.
Unicode paragraph/line separator characters inside a source line do not shift GitHub
line anchors; CRLF line endings are normalized for display.

See [automatic-selection measurements and limitations](scenarios/repository-evidence-auto-sample.md).

### Callable-centered windows

After regular-blob identity, size, UTF-8 and credential-reflection checks, the collector may
select a source window **locally from the already downloaded file**. No additional GitHub
reads, code installation/import/execution, model calls or shell commands are introduced.
The existing per-file128KiB cap remains. Explicit caller ranges are never moved.

Current `auto_callable_v2` applies only to auto-selected implementation files longer than80lines.
Short files and documents/manifests/licenses retain their beginning. Python uses standard
library `ast.parse`, never import/exec/eval; Go/Scala/JS/TS use basic declaration patterns
and Rust uses basic `fn`/attribute patterns after conservative comment/string masking.
Lexical recognizers are not full language parsers:
exotic/generic/multiline syntax, Scala symbols and JS regexp/interpolation may be missed or
misidentified. Other languages, syntax failures, absent declarations and analysis caps fall
back to the header with a fixed explicit reason, not a fabricated function match.

Framework registration hints take priority, then eligible declaration names use a fixed
heuristic: execute, call, processing
(handle/dispatch/audit/validate/etc.), entrypoints (run/serve/main/etc.), then other callables;
specific query/tool-call names also have execution priority. Common constructor/formatting
helpers are skipped. Equal priorities choose the earliest eligible declaration.
Nested Python functions are eligible too; this is not a call graph or reachable-code proof.
Names express where to inspect, **not** proven effects, safety or business value.
No per-repository path/name exceptions or source-text instructions are used.

At most8000LF lines,20000walked Python AST nodes and256eligible declaration candidates.
AST construction itself is bounded by the input file cap, not hard real-time cancellation;
parse/recursion/resource errors fall back conservatively. Cap failures do not claim a
complete candidate scan or zero candidates. Bare CR inside a source line uses a header
fallback so parser newline normalization cannot shift LF-based citation anchors.

Choose one contiguous window starting two lines before the declaration (minimum1), up to
80lines/6000characters. This can omit decorators, earlier context, related helpers or the
rest of a long function. Character clipping never cuts a source line. If clipping omits
the chosen declaration, `anchor_line_retained=false`; the anchor is not evidence it was
returned. Python's `python_body_end_retained` only reports whether the parsed last body line
fits the delivered excerpt; for lexical matches it is null. It is not a correctness or
complete-inspection assertion. `full_callable_verified=false` and semantic relevance false
remain conservative even when the Python body endpoint is included.

Per-file `range_selection` records strategy, parser/lexical method, fixed reason, anchor
name/line, eligible candidate count (unknown on incomplete/no scan), scan limits/completeness,
and actual retention flags. `requested_range_complete` still means the selected bounded
range was delivered, not the file, function or behavior was completely studied.
Use `get_repo_info` explicit ranges / existing `read_file_chunk` for further context.

See [the measured callable-window scenario](scenarios/repository-evidence-window-sample.md).
That historical v1 scenario keeps its original runtime hashes; later v2 changes are measured
separately in [the registration/Rust regression scenario](scenarios/repository-evidence-framework-sample.md).

### Registration and Rust hints (v2)

For JS/TS, recognize statement-shaped `receiver.tool(...)` / `receiver.registerTool(...)`
only after observing a named `McpServer`/`Server` SDK import (including a simple alias) and
`const`/`let`/`var receiver = new ImportedConstructor(...)` syntax. SDK imports and bindings
inside comments/strings are masked out; statement-start matching excludes ordinary regexp
literal contents. This is not a JS parser, symbol resolver, module loader or scope analysis.
Namespace/default/CommonJS imports, factories, reassignment, dynamic property access and
split receiver/method syntax can be missed. A receiver shadowed in a different scope can
still be misidentified: `binding_scope_verified=false` is deliberate.

Only a simple quoted first-argument name followed by comma/closing parenthesis is exposed
as `static_tool_name`. Dynamic expressions, escaped/template names and literal prefixes of
concatenations stay unknown; no expression is evaluated. At most32constructor aliases or
receiver bindings; exceeding that limit returns a header `framework_binding_cap`, avoiding
unbounded receiver-by-line matching. This uses the already downloaded text, no SDK execution.

For Python, AST-shaped `.tool` / `.call_tool` decorators are promoted only with observed
named SDK constructors (`FastMCP` or low-level `Server`) and a simple assigned receiver.
Local compatibility wrappers/factories are unresolved and remain ordinary callable hints.
AST scopes are not resolved; alias shadowing remains uncertain. A registration can be a hint
even if the function name resembles a constructor normally excluded by generic-name rules.

For Rust, recognize basic visibility/async/unsafe/generic `fn` declarations and adjacent
`#[tool(...)]` / qualified `#[...::tool]` attributes, including multiline attributes.
`tool_router` is not treated as a tool declaration. Attribute carry-over is limited to24lines
and interrupted by unrelated code; exotic same-line closing-attribute/code forms may be missed.
ASCII lifetimes/labels are not mistaken for quoted strings; raw/hash strings and nested block
comments are conservatively masked. This is **not** Rust parsing, macro expansion, cfg
evaluation, reachability or proof that a `tool` macro belongs to MCP.

Registration-shaped syntax has `kind`, `registration_line`, fixed reason
`framework_registration_hint` and unverified binding/scope. Prefer including its preceding
attribute/decorator when within20lines of the declaration, otherwise center on the callable
and explicitly expose whether the registration line was retained. The80line/6000character
caps still apply. Rust/JS body endpoints remain null; Python body-end retention does not
establish correctness. File ranking now uses `auto_paths_v2` as described above.
Direct-dependency input formats such as `requirements.in` remain open work; a selected
configuration or authorization filename does not guarantee the relevant control is in its window.

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
Window tests cover Python AST/async and nested declarations, Go/Scala/JS/TS lexical matches,
fake declarations in comments/strings, explicit-range preservation, parser/candidate/node/line
caps, exact pinned deep-function anchors, incomplete long bodies and failed-read plans.
V2 tests additionally cover SDK constructor aliases, registrations and unresolved/dynamic names,
Python decorators, Rust tool attributes/raw strings/lifetimes, fake comment/template/regexp
matches, bounded bindings/candidates, registration retention and unknown lexical body endpoints.
Initial tests exposed two fixture issues (a non-existent dispatcher module and a body threshold
that was larger than the fixture); these were corrected, not counted as runtime fixes.
Review also identified a real safety gap before publication: Contents may dereference symlinks.
The final candidate now verifies regular-file mode and exact blob identity against the pinned
Git tree before reading Contents; regression tests cover this boundary.

See [the measured three-repository scenario](scenarios/repository-evidence-first-sample.md)
and [its observation metadata](examples/repository-evidence-public-sample.json).
That earlier explicit-selection sample retains the hashes of its earlier runtime; it is
not relabelled as a live run of later automatic-selection changes.
### JavaScript-like `.gs` source candidates

The local idea-analog integration additionally treats regular `.gs` paths as implementation
candidates. Long files use the bounded JS lexical window policy with an explicit
`javascript_like_gs_unverified` hint. This supports common Apps Script repositories without
asserting language/runtime from the suffix; no import, execution or extra traversal is added.
Existing exclusions, file budgets and explicit fallback/range reporting still apply.

### Caller focus and explicit rate stops in the local integration

`focus_path_terms` is an optional auto-only list of1–8 distinct ASCII alphanumeric path-token
prefixes (3–32chars), e.g. `["match","embed"]`. It is validated before network; explicit and
legacy modes reject it rather than silently ignore it. Added/changed source paths keep
priority, then matching file paths precede generic role/namespace hints. Document slots,
six-file limit and all read/integrity budgets remain unchanged. The plan records terms and
matches; no claim that path hints locate or verify the requested mechanism is inferred.

Regular `.mjs/.cjs/.mts/.cts` and `.sql` are eligible implementation candidates;
`action.yml/action.yaml` can provide runtime context. Module JS/TS suffixes use the existing
bounded lexical policies with `syntax_extension_alias` reported; TypeScript declaration
`.d.mts/.d.cts` files are excluded. SQL retains a bounded header, not parsed SQL behavior.

After HTTP429, explicit remaining=0, or HTTP403 with numeric Retry-After, the same observation
makes no further sibling/parent GETs. Already verified files are retained and unattempted
reads get `observed_rate_budget` gaps. A bare403 without a quota signal remains scoped to
that refused read (e.g. permission-denied fork comparison); no automatic auth/retry is added.
This is checked stopping, not quota prediction or hard cancellation of an in-flight request.


## Oversized REST commit metadata — compact Git pin recovery

When the REST commit response exceeds the existing body cap, the reader may resolve the **known default branch** through an exact refs/heads pointer and obtain its commit/tree via the compact Git commit API. An explicit full SHA can go directly to Git commit metadata after the size refusal. Other refs/tags are not guessed. Identity/type/tree, remaining shared budgets and rate-stop state remain mandatory; no redirects, auth fallback, retry of the failed endpoint or cap increase. `revision.resolution_strategy` and source indices preserve the failed observation and compact recovery. No fallback for HTTP403/404/429, time limits or exhausted total bytes. [Quality audit](scenarios/analog-quality-audit.md).
