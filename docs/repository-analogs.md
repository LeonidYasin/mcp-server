# Idea → repository analog candidates — local candidate, not deployed

The goal is to avoid rebuilding an existing solution, **not to build another public catalog**.
`find_repository_analogs` composes the existing public Search candidate with the existing
commit-pinned evidence reader. Both are included in this working tree. No model, embedding
provider, database, catalog, external index, new dependency or scheduled job is required.
The calling AI agent performs concept extraction and the final reasoned comparison; the
server performs bounded retrieval, provenance and source verification. This is not an
implemented semantic similarity model or an exhaustive GitHub index.

## Two entry points

### An idea in ordinary language

1. Agent identifies the **problem** and **mechanism**; stack names alone are insufficient.
2. Agent supplies 2–4 public search formulations, including at least one of each facet.
   Use alternate terminology/languages as additional formulations when useful. No fixed
   product dictionary or TableBot-specific branching exists in the implementation.
3. Server searches each formulation in three explicit lanes: broad including forks,
   zero-star including forks, and forks only. No minimum star filter or popularity rank.
4. Server merges stable repository IDs, records all matching probe indices and returns
   a round-robin candidate pool. This is retrieval order, NOT similarity ranking.
5. Agent inspects promising candidates using the returned `evidence_request`, or opts into
   bounded automatic evidence for the first one/two candidates. Automatic order is not
   semantic selection. Initial auto excerpts can miss the relevant implementation.
6. Agent rejects unrelated hits and compares problem, implemented mechanism, differences,
   reusable component, license/compatibility and remaining questions with pinned citations.

### An idea implemented in your repository

First call `get_repo_info(mode=public_evidence,file_selection=auto)` on the **public** source.
Read the relevant implementation explicitly at the same full SHA when auto evidence is
insufficient. Build a source profile with cited problem/mechanism, not README claims alone.
Then call `find_repository_analogs`, passing `source_repository=owner/repo` to exclude the
baseline itself. This argument is only an exclusion; it does NOT inspect the baseline or
prove its visibility. Its name is sent in the public Search query. For private work, do not
include its identity or confidential mechanisms in public queries without permission.
`idea` is returned as context but not sent as a Search query. Only caller-approved `terms`
and the explicit exclusion are sent. This is not general-purpose secret/DLP detection.

## MCP request

```json
{"name":"find_repository_analogs","arguments":{"idea":"Author multi-role Telegram workflows from a transition table","source_repository":"LeonidYasin/Tablebot-pipe-Advanced","queries":[{"facet":"problem","terms":"telegram workflow"},{"facet":"mechanism","terms":"\"transition table\" bot"}],"limit_per_probe":5,"max_candidates":30,"evidence_limit":0,"plan_only":true}}
```

`plan_only=true` makes zero network calls and needs no client when invoked locally.
Default is `false`: the MCP invocation authorizes the bounded public search batch described by the plan.
The server's existing dispatcher still requires a token for GitHub-category tools, even
for a plan; that gate is unchanged. Public outbound requests do **not** carry that token.
Legacy `search_repositories` behavior is unchanged; its explicit `mode=public` is now present
alongside evidence in this tree. Existing draft branches/remotes have not been merged/deployed.

`queries`: 2–4 distinct formulations; each object has `{facet,terms}` plus optional `search_in`. `facet` is
`problem` or `mechanism`, both required across the list. `terms` <=120characters, 1–12
words/quoted phrases; Unicode letters/digits, spaces, `_-.+` and balanced double quotes.
No qualifiers, URL, backslash, negative token or AND/OR/NOT operator: the server controls
scope. Phrase/token search is not translation, paraphrase expansion or code search.
`search_in=default` preserves GitHub repository text scope; `readme` adds `in:readme`;
`name_description_readme` adds `in:name,description,readme`. README expansion is explicit,
not all-code search or a guarantee of relevance. The same terms with a different scope are
a separate allowed formulation. For arbitrary qualifiers/code follow-up, use explicit `search_repositories(mode=public)`/`search_code`;
legacy Code Search requires credentials and is NOT made anonymous by this tool.

Defaults: `limit_per_probe=5` (1–10), `max_candidates=30` (1–40), `evidence_limit=0` (0–2),
`plan_only=false`, `max_search_requests=12` (1–12), `start_probe=0` (within the current plan). Unknown args, bool-as-integer, duplicate formulations, invalid identity,
control characters and literal current credential reflection are rejected before network.
Queries append `is:public fork:true`, plus `stars:0` in zero-star lanes; fork-only lanes
use `is:public fork:only`. Source exclusion is appended to all probes. Full query length
must fit the existing Search candidate's256character cap. Exact effective requests are
in `plan`, with no secret modifiers or star-based relevance score.

## Output and evidence

JSON text, `mode=repository_analog_candidates`, schema_version1. `state` is invalid_input,
planned, observed or partial. Observed means the requested remaining batch completed, never
that earlier batches were observed in this call or all analogs were found or that they are equivalent. Valid zero results are observations;
refusal/invalid envelopes retain unknown counts rather than pretending to be successful empty queries.

- `probes`: facet/lane, source timestamps/status, total/incomplete flags, exclusions,
  coverage and the safe `next_request` from the existing reader. Links are never followed.
- `candidates`: normalized public metadata; `matched_probes`, `matched_facets` and `metadata_probe` show
  retrieval provenance. First-observed metadata is retained, not claimed atomic/current
  across all probes. A match is not semantic evidence. Source repo excluded locally too.
- `counts`: unique observed, returned, cap omissions, source rows, conflicting identities.
  Stable ID/name conflicts reject the later row and make state partial, not silently merge.
  Candidate cap is applied after all returned rows are merged; matching probes are retained.
- `evidence_request`: ordinary existing `get_repo_info` call, not evidence that it ran.
- `evidence`: only when explicitly requested. Uses verified public metadata, full commit SHA,
  tree/regular blob and content integrity, exact excerpt anchors and unknowns from the existing
  reader. Search ID must match later evidence ID; otherwise source excerpts are discarded.
  Fork parent/delta is not auto-read: use `compare_parent=true` in a selected follow-up.
- `coverage`: global/analogs/semantic/runtime flags always false. No numeric similarity score.

A useful agent report is **relevant alternatives with why**, not a dump of names:

| Field | Required interpretation |
| --- | --- |
| Relationship | same problem / same mechanism / adjacent / unrelated / insufficient evidence |
| Evidence | claims vs implementation, pinned file/line citation; follow up beyond README |
| Differences | what is implemented, missing or uncertain; absence of an excerpt is not absence of a feature |
| Reuse path | adopt, integrate a component, contribute/fork, or still build; conditional on license/runtime review |
| Confidence/gaps | observed source limits, index/query blind spots and negative controls |

This report is the agent's analysis, not prefilled server facts. Zero stars do not mean low
quality; personal accounts do not prove solo authorship; forks do not prove a new idea.

## Bounds / failure policy

2–4 formulations ×3lanes =6–12Search GETs, exactly one page each. No auto-next/retry,
credential fallback, redirect, caller URL, disk write or code execution. Read budgets are
inherited: Search1MiB/GET, 8second checked deadline, <=5second socket timeout; optional
0–2evidence observations, each <=12GET/2MiB/30second checked deadline. Workflow checks a
120second monotonic deadline before each observation, **not hard cancellation mid-call**.
Maximum configured GET budget is36 (12Search+24evidence), not unlimited crawling.

First unavailable Search result stops further network probes and suppresses optional
source reads. Successful earlier hits survive with partial state and provenance. Any
unavailable evidence stops further automatic evidence reads. Explicit quota signals also stop siblings/next candidates. No hidden retry/checkpoint.
Incomplete results remain explicit. Candidate cap makes state partial. Output cap256KiB:
if exceeded, candidate/evidence payloads are removed and marked output_budget, never silently
cited as retained. `plan` is intent; `probes` and successful `evidence` are observations.
Numeric rate hints and fixed error codes are retained, not raw errors/bodies.

`tests/test_repository_analogs.py` exercises both real public readers via HTTP mock transport
and the real MCP dispatcher. These are offline contract tests, not deployed acceptance,
foreign-project runtime validation, exhaustive coverage or proof of equal host-token cost.

## Live verification

[Live idea-to-code sample and false positives](scenarios/idea-analog-workflow-sample.md) records
two real bounded discovery passes, selected evidence reads and the `.gs` collector regression.
It does not upgrade lexical retrieval to semantic equivalence or deployed-host acceptance.

## Budgeted continuation (no server-side session)

Use `max_search_requests=2` to inspect a small portion of the plan. Each successful probe
is recorded in `batch.completed_probe_indices`; unattempted probes are not observations.
`stop_reason=search_request_budget` and `next_probe_request` identify the next explicit call.
The server never invokes it, sleeps/retries, persists a cursor or combines batches itself.
An unavailable probe remains the next probe, not skipped as if it succeeded. Explicit
`x-ratelimit-remaining=0` stops further Search GETs before sending a predictable refusal.
Numeric rate hints are observations, not a guarantee of quota availability at the next call.

`plan_fingerprint` is SHA-256 of the canonical ordered plan, not an API snapshot checksum.
Terms, facets, text scope, exclusion and page size affect it; batch size/start do not.
The caller must compare it before combining batches by stable ID, preserving per-batch
provenance and identity conflicts. It is not an authenticated continuation token or a
server-enforced history of prior reads. New Search results may change between batches.
`batch.all_plan_probes_observed_in_call` is false when only a continuation segment was read,
even if state=observed. Per-probe Search `next_request` is pagination, a DIFFERENT cursor
from `next_probe_request`; neither is automatically followed.

Candidate-cap omissions or output overflow clear `next_probe_request` and set
`continuation_blocked_reason`: do not advance beyond omitted candidate payloads. Revisit
that batch with a smaller per-probe page/larger candidate cap when appropriate.

## Question-directed source selection

Optional `focus_path_terms=["match","embed"]` is forwarded into returned evidence requests
and optional evidence observations. The same option is available on
`get_repo_info(mode=public_evidence,file_selection=auto)`, not explicit/legacy mode.
1–8 distinct case-insensitive ASCII alphanumeric prefixes, 3–32characters each. Explicit
null/empty/invalid/duplicate values fail before network. Terms are not silently derived
from the idea text and are NOT added to Search queries.

Focus matches token prefixes after camel-case/punctuation splitting of eligible file paths.
Observed added/changed source priority remains first; matching paths then precede generic
role/diversity heuristics. Documents still consume their normal slots. The returned plan
records `focus_path_terms_used`, per-source `focus_path_matches` and the fixed selection
reason. These are file-name hints, not proof of content, relevance or feature coverage.
No content-wide search, model call, extra tree walk, larger file limit or higher GET budget.

The live Action case additionally revealed that `.mts` implementation and `action.yml`
were previously missed. Auto source candidates now include `.mjs/.cjs/.mts/.cts`, using
the existing bounded JS/TS lexical policies, while declaration `.d.mts/.d.cts` files are
excluded. `action.yml/action.yaml` can be runtime context. `.sql` is an eligible source
candidate for matching/RPC implementations; SQL excerpts use the bounded header fallback,
not a SQL semantic parser. Existing `.gs` support remains JavaScript-like and unverified.

[Four-case acceptance, noise and same-SHA focus comparison](scenarios/idea-analog-acceptance.md)
records the latest live checks and explicitly incomplete semantic acceptance.
