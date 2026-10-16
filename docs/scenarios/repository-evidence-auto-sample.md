# Automatic repository file selection: measured sample

**Candidate-local, not deployed; three fixed repositories, not a GitHub-wide sample.**
Historical path-selection sample: this runtime used first80line excerpts. Its original
runtime hashes remain unchanged. See [the later callable-window sample](repository-evidence-window-sample.md)
for the subsequent within-file selection feature.
Observed 2026-10-16T21:47:45.256734+00:00.
The existing Flask MCP dispatcher received three real `tools/call` requests with
`get_repo_info(mode=public_evidence, file_selection=auto)` and pinned refs.
No file paths were supplied by the caller. Only the fork used `compare_parent=true`.
All upstream requests were anonymous; a synthetic local-only value satisfied the unchanged
MCP dispatcher token gate. No third-party projects were installed or executed.

[Source metadata, exact arguments and tested runtime hashes](../examples/repository-evidence-auto-sample.json)
· [Selection contract and limitations](../repository-evidence.md)

## Measurements

| Repository | Files returned | GETs | Upstream body bytes | Tool text UTF-8 bytes | Local elapsed seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| Furox-Art/scientific-toolkit | 6 | 9 | 102570 | 29398 | 0.927572 |
| Primexz/netops-mcp | 6 | 9 | 99348 | 21760 | 0.903307 |
| Johnmelo/codebadger-mola | 6 | 12 | 343032 | 31700 | 1.679918 |
| Total | 18 | 30 | 544950 | 82858 | 3.510797 |

All30upstream responses were HTTP200; each call was observed, with six file excerpts and
no source gaps. There was no retry or hidden file crawl. The existing tree read supports
both explicit and auto modes; compare-enabled calls still have a maximum12GETbudget.
Output bytes count JSON text, not total HTTP envelopes, schema discovery, model tokens or
billed credits. Elapsed time is a local observation, not a latency guarantee or fair cost
comparison against the earlier explicit sample (which selected different files/ranges).

## Actual automatic choices

### Furox-Art/scientific-toolkit

- `README.md` — overview; `conventional_overview_path`; [observed lines 1–80](https://github.com/Furox-Art/scientific-toolkit/blob/3f8fb75a917d02128e1fe3e1dfe4edcb5a6599c4/README.md#L1-L80).
- `pyproject.toml` — runtime; `conventional_runtime_path`; [observed lines 1–40](https://github.com/Furox-Art/scientific-toolkit/blob/3f8fb75a917d02128e1fe3e1dfe4edcb5a6599c4/pyproject.toml#L1-L40).
- `LICENSE` — license; `conventional_license_path`; [observed lines 1–80](https://github.com/Furox-Art/scientific-toolkit/blob/3f8fb75a917d02128e1fe3e1dfe4edcb5a6599c4/LICENSE#L1-L80).
- `scientific_toolkit_mcp/server.py` — implementation; `conventional_implementation_path`; [observed lines 1–80](https://github.com/Furox-Art/scientific-toolkit/blob/3f8fb75a917d02128e1fe3e1dfe4edcb5a6599c4/scientific_toolkit_mcp/server.py#L1-L80).
- `scientific_toolkit_mcp/tools.py` — implementation; `conventional_implementation_path`; [observed lines 1–80](https://github.com/Furox-Art/scientific-toolkit/blob/3f8fb75a917d02128e1fe3e1dfe4edcb5a6599c4/scientific_toolkit_mcp/tools.py#L1-L80).
- `scientific_toolkit_mcp/catalog.py` — implementation; `conventional_implementation_path`; [observed lines 1–50](https://github.com/Furox-Art/scientific-toolkit/blob/3f8fb75a917d02128e1fe3e1dfe4edcb5a6599c4/scientific_toolkit_mcp/catalog.py#L1-L50).

### Primexz/netops-mcp

- `README.md` — overview; `conventional_overview_path`; [observed lines 1–62](https://github.com/Primexz/netops-mcp/blob/748bf3aaa14454e48a1ddb4320fcdde35b99e401/README.md#L1-L62).
- `go.mod` — runtime; `conventional_runtime_path`; [observed lines 1–23](https://github.com/Primexz/netops-mcp/blob/748bf3aaa14454e48a1ddb4320fcdde35b99e401/go.mod#L1-L23).
- `docs/architecture.md` — architecture; `conventional_architecture_path`; [observed lines 1–16](https://github.com/Primexz/netops-mcp/blob/748bf3aaa14454e48a1ddb4320fcdde35b99e401/docs/architecture.md#L1-L16).
- `LICENSE` — license; `conventional_license_path`; [observed lines 1–21](https://github.com/Primexz/netops-mcp/blob/748bf3aaa14454e48a1ddb4320fcdde35b99e401/LICENSE#L1-L21).
- `internal/mikrotik/engine/engine.go` — implementation; `conventional_implementation_path`; [observed lines 1–80](https://github.com/Primexz/netops-mcp/blob/748bf3aaa14454e48a1ddb4320fcdde35b99e401/internal/mikrotik/engine/engine.go#L1-L80).
- `internal/securepoint/engine/engine.go` — implementation; `conventional_implementation_path`; [observed lines 1–80](https://github.com/Primexz/netops-mcp/blob/748bf3aaa14454e48a1ddb4320fcdde35b99e401/internal/securepoint/engine/engine.go#L1-L80).

### Johnmelo/codebadger-mola

- `README.md` — overview; `conventional_overview_path`; [observed lines 1–59](https://github.com/Johnmelo/codebadger-mola/blob/9fbb0b63b54a105cb14a9a7ddcdfd47dfee4217f/README.md#L1-L59).
- `pyproject.toml` — runtime; `conventional_runtime_path`; [observed lines 1–71](https://github.com/Johnmelo/codebadger-mola/blob/9fbb0b63b54a105cb14a9a7ddcdfd47dfee4217f/pyproject.toml#L1-L71).
- `docs/architecture.md` — architecture; `conventional_architecture_path`; [observed lines 1–80](https://github.com/Johnmelo/codebadger-mola/blob/9fbb0b63b54a105cb14a9a7ddcdfd47dfee4217f/docs/architecture.md#L1-L80).
- `LICENSE` — license; `conventional_license_path`; [observed lines 1–80](https://github.com/Johnmelo/codebadger-mola/blob/9fbb0b63b54a105cb14a9a7ddcdfd47dfee4217f/LICENSE#L1-L80).
- `src/tools/queries/android_intent_injection.scala` — implementation; `added_source_path_in_observed_comparison`; [observed lines 1–57](https://github.com/Johnmelo/codebadger-mola/blob/9fbb0b63b54a105cb14a9a7ddcdfd47dfee4217f/src/tools/queries/android_intent_injection.scala#L1-L57).
- `src/tools/queries/android_webview_sinks.scala` — implementation; `added_source_path_in_observed_comparison`; [observed lines 1–80](https://github.com/Johnmelo/codebadger-mola/blob/9fbb0b63b54a105cb14a9a7ddcdfd47dfee4217f/src/tools/queries/android_webview_sinks.scala#L1-L80).

## What improved during validation

The first live pass selected changed `main.py` and `query_executor.py` for the fork, missing
the added Android queries. That was a real relevance weakness, not a runtime failure.
The final policy prioritizes added source paths before modified ones within observed changed
paths. It selected both Android query files without caller-provided paths. Added does not
mean innovative, exploitable, important or correct; this is an exploration tie-breaker.

The first pass also spent a scientific-toolkit slot on a Python `__main__.py` wrapper.
The final policy excludes common Python wrapper names and instead selected `catalog.py`.
These heuristics are deliberately general path rules, not hardcoded repository/file exceptions.
Tests cover a modified engine competing against added deeper source paths and shuffled tree order.

## What the observation does not establish

- Role labels are **hints from path names**. The collector did not generate or verify a summary
  of behavior. Neither names nor changes prove semantic relevance.
- First80line excerpts can miss the useful function deep in a correct file. For example, choosing
  the Securepoint engine does not automatically read its mutation guards hundreds of lines below.
  The earlier analyst-selected sample read lines317–416; this auto call did not.
- The WebView query excerpt ends before the full file. Complete requested80lines does not mean
  complete inspection of all query logic. Vulnerabilities require context and manual validation.
- No CI, equipment, scientific correctness, Joern runtime, deployment or commercial demand was
  verified by these calls. Previous independent manual observations must remain separately cited.
- Parent comparison only contributes its displayed paths (max40); it is not a complete change or
  novelty analysis. Incomplete tree/comparison observations can distort automatic selection.
- Large repositories whose tree exceeds the bounded response are conservatively unavailable.
  Monorepos/unconventional naming and useful example/test code can be missed.
- Three fixed, previously discovered repositories are not a representative sample or a trend.
  No minimum-star filter was applied, but this does not prove GitHub-wide coverage.

The committed sample contains source hashes, citation ranges, plan reasons and measurements,
not verbatim third-party source excerpts. Raw source snapshots were retained locally only.
Historical explicit-selection measurements keep their earlier runtime hashes; they are not
silently relabelled as a run of this later implementation.
