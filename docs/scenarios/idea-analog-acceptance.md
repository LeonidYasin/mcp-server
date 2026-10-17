# Idea analog acceptance: three source repositories and an ordinary idea

Local candidate, not deployed TEST/production. The [MCP contract](../repository-analogs.md)
separates agent concept extraction/comparison from server retrieval and verified excerpts.
This is not a public catalog, global index or semantic similarity model.

## Transport and retrieval checks

Four original cases: TableBot, Agora, ConstruBot, and a plain-language idea for suggesting
existing GitHub issues before opening duplicates. Each used two problem/mechanism formulations
and the same six-probe broad/zero-star/fork plan. Three explicit calls of2GETs completed
indices0–5 exactly once for each case. All24Search responses were HTTP200 and plan fingerprints
were stable across continuations. No server-side session, auto-next, retry or checkpoint cache.
Three additional reformulated broad batches used6GETs:30Search GETs total in this iteration.

Discovery/evidence tool calls went through the **local Flask MCP dispatcher** with real anonymous GitHub reads.
One additional pinned-tree debug inspection used the same bounded Reader directly.
The existing inbound token gate used a synthetic local value; that is NOT user authorization,
OAuth acceptance or a deployed-host test. The public readers send no inbound credential.
Every response retains its scope, timestamps, incomplete/coverage and pagination hints.
Successful final continuation state is not evidence that earlier batches were read in that
call; the caller combines observations and preserves conflicts. Zero-star/fork inclusion
is retrieval coverage within explicit queries, not proof of all such repositories.

## Qualitative acceptance, including failures

| Case | Observed outcome | Acceptance boundary |
| --- | --- | --- |
| TableBot | Broad README co-occurrence surfaced catalogs, unrelated bots and workflow collections. Reformulating metadata terms found conversation-FSM packages including `go-telegram/fsm` and `Feolius/telegram-bot-fsm` | Retrieval/continuation verified. No source-supported replacement for table-authored multi-role workflows established in this iteration. Candidate code review pending |
| Agora | Zero-star probe surfaced `buidanhhuong/can-co`, a need/have-intent project | Source-supported related mechanism, not verified equivalence or originality. No reuse-license clearance established |
| ConstruBot | Initial `parametric house` also found gingerbread/household/GridFinity projects. Refinement found `zjunhao/ConstructionMaterialCalculator` and a WPF variant | Discovery only here. Their quantity implementation and structural scope remain unreviewed; do not call them proved substitutes |
| Plain-language issue deduplication | Found existing Actions plus a similarly named issue-copying tool and generic embedding libraries | At least one existing approach is source-supported; runtime, deployment, data population and cost remain untested |

These few analyst judgments are not a measured precision/recall benchmark. Report negative
and unverified hits instead of treating every returned repository as an analog. Broad README
expansion can substantially reduce precision. Sparse descriptions also limit metadata-only recall.

## Concrete server fixes verified by the scenario

### Same-SHA focus: Agora-related implementation instead of generic wiring

At `buidanhhuong/can-co` SHA `8d97d1fc675f32eee9e8ae7af17be9c07aeba915`, default auto
selection used9GETs for README/package plus Supabase bootstrap, an intelligence barrel,
OpenClaw security and tool wiring. Re-reading with explicit `focus_path_terms=["match","embed"]`
also used9GETs and six files, now including matching engine, matching API/trigger and a UI card.
Source hashes and file counts remain validated; the file-name preference is not semantic proof.

The delivered [matching.ts lines18–97](https://github.com/buidanhhuong/can-co/blob/8d97d1fc675f32eee9e8ae7af17be9c07aeba915/lib/engine/matching.ts#L18-L97)
build intent text, generate/store embeddings and begin scoring district/price attributes.
The [matching API](https://github.com/buidanhhuong/can-co/blob/8d97d1fc675f32eee9e8ae7af17be9c07aeba915/app/api/matching/route.ts#L1-L38)
authenticates the user, finds active intents and retrieves associated matches. This supports
an adjacent need/have-matching mechanism, not a claim that every README feature works.

Compared with the frozen Agora
[opposite-type/other-owner cosine query](https://github.com/LeonidYasin/agora-mcp/blob/8428e8484f785e91a8689c0c8d3d2ec57c80e1b5/mcp-server/src/db.ts#L72-L105),
the observed candidate also has attribute-based scoring. Full candidate filtering/distance
implementation falls beyond the delivered matching.ts window and needs explicit follow-up.
The metadata reports no recognized SPDX license; that does not prove no license exists, but
reuse permission has NOT been established. Zero stars and nonfork metadata do not prove a solo
original author. README links/clone instructions are not parent/lineage verification.

### Module source extensions: an existing Action is no longer README-only

At `pelikhan/action-genai-issue-dedup` SHA `bdb3b5d9451c1090ffcdf123d7447a5e7c7a2528`,
the pinned tree contains `genaisrc/genai-issue-dedup.genai.mts`. Earlier auto selection
missed that suffix and returned context files only. The fixed policy reads the verified
[.mts source](https://github.com/pelikhan/action-genai-issue-dedup/blob/bdb3b5d9451c1090ffcdf123d7447a5e7c7a2528/genaisrc/genai-issue-dedup.genai.mts#L1-L80)
within the unchanged six-file/12-GET cap (9actualGETs). The excerpt configures duplicate
checking options and obtains the current issue; the full detection algorithm lies beyond
this window and is NOT considered verified. `.mjs/.cjs/.mts/.cts`, declaration exclusions,
Action manifest eligibility and `.sql` eligibility have offline regression coverage.
Eligibility does not guarantee every manifest/source fits the current plan.

### A real existing implementation for the ordinary idea

`weaviate/weaviate-github-issue-triage` at SHA `6a20f3ea7980102999f6a6ca009bafbf19014b6d`
first yielded setup/environment context. An explicit same-SHA follow-up delivered
[main.py lines90–189](https://github.com/weaviate/weaviate-github-issue-triage/blob/6a20f3ea7980102999f6a6ca009bafbf19014b6d/main.py#L90-L189):
it constructs a QueryAgent over a configured issue collection/vector, runs it against the
issue body and handles a no-match result. This is concrete existing approach evidence,
not only a repository title or README promise. DB contents, vectorization, agent correctness,
comment posting after line189, production costs and integration permissions remain untested.

`code413/issue-duplicator` advertises copying issues between repositories in its
[README](https://github.com/code413/issue-duplicator/blob/48d22d48ca0a778ce71ae8a1f8ae2e0a4ad6f9ca/README.md#L1-L9).
The selected PHP excerpts were application wiring, not copying logic. Treat it as a
purpose-level negative/adjacent candidate, not a code-verified implementation judgment.
The earlier [Markov-table negative control](idea-analog-workflow-sample.md) is code-supported.

## Quota, provenance and remaining gates

This iteration recorded57source/API GETs including one pinned-tree inspection in addition
to30Search GETs. The final source response reported1/60remaining. Further core reads were
stopped, not retried with credentials or moved to another host to bypass the observed budget.
Quota consumption is not inferred from counter differences; the counts come from recorded
attempts. No foreign project was installed, executed, contacted or deployed.

The final focused observations record matching before/after hashes of loaded source-file
versions during a code-frozen run. Earlier phases were uncommitted local iterations; their
base HEAD alone does not identify runtime changes. Observations and hashes are kept in the
local acceptance workspace rather than copying third-party source snapshots into this repo.

Remaining: source review for TableBot/ConstruBot candidates; deeper matching/dedup ranges;
verified fork-parent/delta grouping; larger human-labeled retrieval evaluation; PR/CI and
TEST host acceptance. The current local candidate must not be described as deployed or
as a complete automatic semantic analog detector. No main/VPS changes or schedule enabled.

## Follow-up review through the existing GitHub MCP connection

The two initially pending implementation reviews below were subsequently performed through
an **existing authorized GitHub MCP connection**, not by silently authenticating the
anonymous candidate reader. There is no new token handling/fallback in the server. These
reads are a separate source provenance:10read-only MCP calls (2commit observations,
3directory listings,5text files), not10measured HTTPGETs or public-mode budget acceptance.
The [review ledger](../examples/repository-analog-reviewed-cases.json) records commit pins,
provider directory/file blob identifiers, locally matched Git-blob/SHA256 hashes, delivered
line bounds and explicitly partial analyst findings. The full commit/tree/regular-mode
chain was NOT independently verified through this connection. No source snapshot is published.

### TableBot: shared FSM primitive, not a demonstrated workflow-authoring substitute

At `go-telegram/fsm` SHA `8e54b70cd0f23f40f0c943feffd3191cd29c0ab8`,
[fsm.go lines36–83](https://github.com/go-telegram/fsm/blob/8e54b70cd0f23f40f0c943feffd3191cd29c0ab8/fsm.go#L36-L83)
constructs callbacks and implements per-user state transition followed by callback invocation.
[Default storage](https://github.com/go-telegram/fsm/blob/8e54b70cd0f23f40f0c943feffd3191cd29c0ab8/user_state_storage.go#L8-L19)
is an in-memory map. This supports a shared primitive, but does not demonstrate the baseline's
[table-derived states](https://github.com/LeonidYasin/Tablebot-pipe-Advanced/blob/9e4577cdeddfb19f116d5620a5949ef0cc462d25/core/fsm_builder.py#L8-L24)
and [action subprocess orchestration](https://github.com/LeonidYasin/Tablebot-pipe-Advanced/blob/9e4577cdeddfb19f116d5620a5949ef0cc462d25/core/pipeline_executor.py#L11-L53).
No claim that the entire Go project lacks those features is made from two selected files.
For the existing Python/aiogram project this is a reference/primitive, not a drop-in replacement.
License conditions, persistence needs and callback/state-consistency policy remain adoption questions.

### ConstruBot: quantity/BOM/export patterns, not A-frame engineering

At `zjunhao/ConstructionMaterialCalculator` SHA `769231651aa3464b84b83268e96533bfd95fc66c`,
[CalculatorA.java lines20–83](https://github.com/zjunhao/ConstructionMaterialCalculator/blob/769231651aa3464b84b83268e96533bfd95fc66c/src/CalculatorA.java#L20-L83)
computes board/linear-element quantities with dimension-dependent rounding, groups records
by product/type and aggregates quantities/area. An
[accessory calculation](https://github.com/zjunhao/ConstructionMaterialCalculator/blob/769231651aa3464b84b83268e96533bfd95fc66c/src/CalculatorA.java#L91-L104)
uses aggregated board dimensions. The
[export implementation](https://github.com/zjunhao/ConstructionMaterialCalculator/blob/769231651aa3464b84b83268e96533bfd95fc66c/src/OutToExcel.java#L99-L194)
writes purchase/selling summaries with quantities and provided price fields to XLS via POI.
The earlier [ConstruBot baseline](https://github.com/LeonidYasin/ConstruBot/blob/ee3d69e0f6c721207ab66ceef2d830a316d80d52/backend/app/main.py#L21-L40)
is fixed width/height-based board/screw/roof estimation. Evaluate grouping, rounding and
report patterns before rebuilding them, but do not call this Java desktop utility a ready
A-frame geometry service, validated engineering calculator or licensed-to-copy component.
No execution, mathematical accuracy/units testing or legal reuse review was performed.

This closes the two **selected implementation-reading** gaps. It does not close full
semantic retrieval acceptance: no complete substitute, broad precision/recall, fork lineage,
novelty, runtime or deployment has been established. The live anonymous quota result and
other deeper follow-up ranges remain as originally recorded, not retroactively changed.
