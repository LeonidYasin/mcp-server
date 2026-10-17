# Idea analog workflow: live retrieval is not equivalence

Local candidate only, not deployed-host acceptance. No catalog, product pilot, writes,
external code execution or schedule. Public reads use the candidate implementation through
its actual Python handlers and HTTP transport, not a claim that TEST already exposes it.
The [workflow contract](../repository-analogs.md) describes the agent/server division.

## Baseline / question

Source idea: author Telegram workflows from a transition table, with dynamic FSM states
and subprocess-based action pipelines. These are distinct mechanisms, not merely the
words "Telegram", "table" or "workflow".

Baseline evidence already observed at the full source SHA:
- [FSM state construction from from_state/to_state](https://github.com/LeonidYasin/Tablebot-pipe-Advanced/blob/9e4577cdeddfb19f116d5620a5949ef0cc462d25/core/fsm_builder.py#L8-L24).
- [JSON temporary files, subprocess actions and timeout](https://github.com/LeonidYasin/Tablebot-pipe-Advanced/blob/9e4577cdeddfb19f116d5620a5949ef0cc462d25/core/pipeline_executor.py#L11-L53).

This baseline is a selected static observation, not a runtime validation or current-HEAD claim.

## First live pass

Two formulations: problem=`telegram workflow`, mechanism=`"transition table" bot`.
Each was queried in broad, zero-star and fork-only lanes, excluding the source repository.
Six HTTP200 Search GETs, 39269 response body bytes, seven unique candidates at two rows/probe.
No automatic candidate evidence requested on this pass. Ordinary broad problem query reported
10396matches: its two returned rows are NOT a complete result or a useful product ranking.

The mechanism query returned `scarafoni/Opinion_Bot`. A selected follow-up read obtained four
verified files at SHA `e31957cfb1b8d2b247a81186ed2f5d86d326c13a` (seven GETs).
The [transition table implementation](https://github.com/scarafoni/Opinion_Bot/blob/e31957cfb1b8d2b247a81186ed2f5d86d326c13a/src/opinion_bot/transition_table.py#L1-L64)
counts adjacent n-grams and normalizes probabilities. **Reject as a matching workflow
mechanism for the baseline**: same words, different mechanism. This is an analyst judgment
supported by that file, not a generic server feature that semantically rejects all such hits.

A second selected follow-up read `requilence/integram` at SHA
`7464d2640e02b382d19b64826a554d717ad52995` (six files, nine GETs).
Its [Run function](https://github.com/requilence/integram/blob/7464d2640e02b382d19b64826a554d717ad52995/handlers.go#L144-L223)
initializes bots, Redis jobs, rate limiting and the router. Treat as adjacent Telegram
integration infrastructure, not demonstrated table-authored FSM equivalence. Selected
windows do not prove such a feature absent elsewhere in the project.

## Refinement / real collector defect

Refined formulations: problem=`telegram spreadsheet`; mechanism=`telegram "state machine"`
with explicit `search_in=readme`. Six more Search HTTP200 responses produced twelve unique
candidates; optional evidence for the first retrieval-order candidate added four GETs.
All ten calls completed. This does not show twelve relevant analogs: the README query also
returned blockchain projects where broad word co-occurrence is not mechanism equivalence.
README expansion is explicit and useful for recall, but is not a relevance guarantee.

First candidate `tegohsx/laporan-keuangan-bot` initially yielded README only despite its
README naming `Kode.gs`. This exposed an actual collector omission: `.gs` was not an eligible
implementation suffix. The server now considers `.gs` files and uses bounded JavaScript-like
lexical window hints for long files; `.gs` is not asserted to be a verified language/runtime.

Re-reading **the same SHA** `7ecc571e0db9b365ac520ca427d09663d27ed6b0` after that fix
used five GETs and delivered README plus
[Kode.gs lines13–92](https://github.com/tegohsx/laporan-keuangan-bot/blob/7ecc571e0db9b365ac520ca427d09663d27ed6b0/Kode.gs#L13-L92).
The delivered code receives Telegram updates, checks allowed chat IDs and routes expense/
income commands into spreadsheet collections. It is a neighboring integration mechanism,
**not demonstrated table-to-workflow authoring**. Legal reuse/runtime/correctness are untested.
Do not claim one read proves the entire product implements or lacks a feature.

Regression coverage includes `.gs` selection, comment/string masking, no source execution
and a discovered candidate reaching pinned `.gs` implementation evidence through the new tool.
The fix adds no network request beyond the existing six-file/12-GET evidence cap; selecting
one additional eligible file naturally uses one additional Contents GET in this sample.

## Acceptance / remaining work

This sample verifies retrieval, provenance, selected implementation inspection, a concrete
false-positive rejection and a real collector fix. It does NOT establish high recall, a global
semantic index, runtime validity, novelty or successful production/TEST deployment.

Next research iterations must diversify formulations, choose evidence by the question rather
than first-row order, compare fork parents when reuse is plausible, and test additional source
ideas (e.g. offer/want vector matching and parametric building estimates) plus arbitrary ideas.
Use small human-labeled positive/adjacent/negative cases and report retrieval failures too.
Do not turn this into a separate public catalog or a paid vertical product project.

Measured JSON observations are retained outside the source tree, with hashes of the dirty
runtime files used for each phase. The base Git HEAD alone does not identify this uncommitted
implementation. Source excerpts are not copied into this scenario document.
