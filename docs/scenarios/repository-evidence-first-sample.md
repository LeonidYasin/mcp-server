# Repository evidence: first measured public scenario

**Candidate-local observation, not a deployment or whole-GitHub report.**
Historical explicit-selection sample: its runtime hashes identify the pre-auto candidate.
See [the later automatic-selection sample](repository-evidence-auto-sample.md).
Observed2026-10-16T21:24:46.036713+00:00.
Three real `tools/call` requests to `get_repo_info(mode=public_evidence)` through Flask's
local MCP dispatcher. Existing token gate used a synthetic local-only value; every
upstream request was anonymous. No third-party packages were installed or executed.
See [measured source metadata and runtime hashes](../examples/repository-evidence-public-sample.json)
and [the contract](../repository-evidence.md).

## Measurements

| Repository | Selected files returned | Public GETs | Upstream body bytes | Tool text UTF-8 bytes | Local elapsed seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| Furox-Art/scientific-toolkit | 4 | 7 | 75029 | 17666 | 0.853746 |
| Primexz/netops-mcp | 6 | 9 | 104292 | 25578 | 0.911639 |
| Johnmelo/codebadger-mola | 6 | 12 | 316808 | 28910 | 1.638385 |
| Total | 16 | 28 | 496129 | 72154 | 3.403770 |

All28upstream responses were HTTP200. Each call was `observed` with no missing-source gaps;
this does **not** mean every selected file was returned whole. Output bytes count JSON text,
not complete HTTP envelopes, schema discovery, model context/tokens or billed host credits.
Elapsed time is one local sample, not a latency guarantee or equal-coverage cost benchmark.
The hashes in the sample identify the actual tested candidate runtime, not a main commit
that does not contain the feature.

## What this second layer supports

### scientific-toolkit: orchestration, not a new scientific engine

The manifest and catalog were returned whole. They support a concrete story: an MCP gateway
around existing science/verification CLIs, with no mandatory Python dependencies in the
gateway manifest. A user still needs the underlying CLI environments. Selected `tools.py`
lines165–264 show actual dispatch and validation routines, rather than relying only on
marketing text. No upstream numerical correctness was tested.

Sources: [manifest](https://github.com/Furox-Art/scientific-toolkit/blob/3f8fb75a917d02128e1fe3e1dfe4edcb5a6599c4/pyproject.toml#L1-L40),
[catalog](https://github.com/Furox-Art/scientific-toolkit/blob/3f8fb75a917d02128e1fe3e1dfe4edcb5a6599c4/scientific_toolkit_mcp/catalog.py#L1-L50),
[selected implementation](https://github.com/Furox-Art/scientific-toolkit/blob/3f8fb75a917d02128e1fe3e1dfe4edcb5a6599c4/scientific_toolkit_mcp/tools.py#L165-L264).

**Commercial hypothesis:** a reproducible engineering/research assistant that shows which
external tool produced a result. Demand, scientific validity and production OAuth are not
established by this collection.

### netops-mcp: vendor-specific contracts matter

The coverage document and Go manifest were returned whole; config/engines were selected
excerpts. Securepoint's selected lines contain plan preparation, state checks and execution
guards. Do not imply this excerpt includes the entire engine or every replay-protection
detail: follow-up source reads may be needed. No router credentials or equipment were used.

Sources: [coverage](https://github.com/Primexz/netops-mcp/blob/748bf3aaa14454e48a1ddb4320fcdde35b99e401/docs/mikrotik/coverage.md#L1-L40),
[Go manifest](https://github.com/Primexz/netops-mcp/blob/748bf3aaa14454e48a1ddb4320fcdde35b99e401/go.mod#L1-L23),
[Securepoint excerpt](https://github.com/Primexz/netops-mcp/blob/748bf3aaa14454e48a1ddb4320fcdde35b99e401/internal/securepoint/engine/engine.go#L317-L416).

**Commercial hypothesis:** read-only diagnostics for an integrator's known fleet before
allowing mutations. This is a proposed pilot, not demonstrated autonomous troubleshooting
or a safety certification.

### codebadger-mola: inspect a fork's changes before discarding it

The separately resolved parent is `qcri/codebadger` at
`857adcabe38677c53d068b310ab4f6ca51828c61`; the selected fork is pinned to
`9fbb0b63b54a105cb14a9a7ddcdfd47dfee4217f`.
Comparison reports ahead12/behind0 and24changed file rows. All24rows fit the local40row
display cap, but the general `file_list_complete` flag remains false; patches were not
reviewed by this mode. Ahead count is not a feature/novelty count.

The Android Intent query was returned whole (57lines). The WebView file has more content
than the returned range; it stopped at line96 due to the6000character excerpt cap, despite
requesting100lines. `requested_range_complete=false` and `whole_file_included=false`
correctly preserve this limitation. A follow-up read starting at97is necessary before
claiming complete inspection. The query-executor excerpt supports the concrete timeout
tradeoff: retain the Joern server after a long query, rather than automatically destroying
it. No runtime memory measurement or vulnerability confirmation was performed.

Sources: [pinned comparison](https://github.com/Johnmelo/codebadger-mola/compare/857adcabe38677c53d068b310ab4f6ca51828c61...9fbb0b63b54a105cb14a9a7ddcdfd47dfee4217f),
[Intent query](https://github.com/Johnmelo/codebadger-mola/blob/9fbb0b63b54a105cb14a9a7ddcdfd47dfee4217f/src/tools/queries/android_intent_injection.scala#L1-L57),
[WebView excerpt](https://github.com/Johnmelo/codebadger-mola/blob/9fbb0b63b54a105cb14a9a7ddcdfd47dfee4217f/src/tools/queries/android_webview_sinks.scala#L1-L96),
[timeout excerpt](https://github.com/Johnmelo/codebadger-mola/blob/9fbb0b63b54a105cb14a9a7ddcdfd47dfee4217f/src/services/query_executor.py#L146-L185).

**Commercial hypothesis:** a graph-backed code-security assistant, subject to infrastructure
cost, false-positive validation and license review. Static query patterns are not confirmed
exploits. No automatic deployment on a small VPS is recommended.

## Not yet delivered

At this sample's runtime there was no automatic file selection. Later path heuristics are
measured separately in the linked auto sample; they are not retroactively established here.
No generated narrative, analogue clustering, broad
enumeration, trend history, runtime validation or billing benchmark. The collector supplies
verifiable source material for the analyst and makes missing/partial observations explicit.
Evidence selection is still manual; no claim that this sample covers these repositories
fully or represents GitHub at large. The source-text snapshots were retained locally for
verification, not committed verbatim into this repository.