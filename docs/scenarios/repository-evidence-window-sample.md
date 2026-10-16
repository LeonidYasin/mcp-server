# Callable-centered repository excerpts: measured sample

**Candidate-local, not deployed; three fixed previously examined repositories.**
Observed 2026-10-16T21:58:52.342133+00:00. Three real Flask MCP `tools/call` requests to
`get_repo_info(mode=public_evidence, file_selection=auto)` with pinned refs and no caller
file paths or line ranges. Only the fork used explicit `compare_parent=true`.
All upstream requests were anonymous; the unchanged MCP token gate used a synthetic
local-only value. No code from the inspected projects was installed, imported or executed.

[Source metadata, arguments, ranges and runtime hashes](../examples/repository-evidence-window-sample.json)
· [Contract and limitations](../repository-evidence.md)

## Measurements

| Repository | Files returned | GETs | Upstream body bytes | Tool text UTF-8 bytes | Local elapsed seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| Furox-Art/scientific-toolkit | 6 | 9 | 102570 | 31938 | 0.990857 |
| Primexz/netops-mcp | 6 | 9 | 99348 | 25168 | 0.899406 |
| Johnmelo/codebadger-mola | 6 | 12 | 343032 | 34205 | 1.746526 |
| Total | 18 | 30 | 544950 | 91311 | 3.636789 |

All30upstream responses were HTTP200, all18file observations returned without source gaps.
The **same pinned files/content hashes** were selected as in the historical path-only auto
sample; no extra GETs were needed to choose local windows. Four excerpts moved from file
headers to callable declarations. Other files retained their beginnings with explicit reasons.

## Which windows changed

| Repository and file | Previous observed range | New observed range | Declaration hint | Method |
| --- | --- | --- | --- | --- |
| Furox-Art/scientific-toolkit: `scientific_toolkit_mcp/server.py` | 1–80 | [71–138](https://github.com/Furox-Art/scientific-toolkit/blob/3f8fb75a917d02128e1fe3e1dfe4edcb5a6599c4/scientific_toolkit_mcp/server.py#L71-L138) | `handle`, line73 | `python_ast` |
| Furox-Art/scientific-toolkit: `scientific_toolkit_mcp/tools.py` | 1–80 | [163–242](https://github.com/Furox-Art/scientific-toolkit/blob/3f8fb75a917d02128e1fe3e1dfe4edcb5a6599c4/scientific_toolkit_mcp/tools.py#L163-L242) | `_call`, line165 | `python_ast` |
| Primexz/netops-mcp: `internal/mikrotik/engine/engine.go` | 1–80 | [70–149](https://github.com/Primexz/netops-mcp/blob/748bf3aaa14454e48a1ddb4320fcdde35b99e401/internal/mikrotik/engine/engine.go#L70-L149) | `Call`, line72 | `go_lexical` |
| Primexz/netops-mcp: `internal/securepoint/engine/engine.go` | 1–80 | [373–452](https://github.com/Primexz/netops-mcp/blob/748bf3aaa14454e48a1ddb4320fcdde35b99e401/internal/securepoint/engine/engine.go#L373-L452) | `Execute`, line375 | `go_lexical` |

These names indicate where to inspect; they do not prove execution effects or relevance.
Both Python declarations and their parsed body endpoints fit the delivered excerpts. Go
matches have no verified body endpoint; full-callable verification stays false for all.
No complete-file/function/security-review claim follows from delivery of an80line window.

## Concrete information now visible

- **scientific-toolkit:** the `_call` excerpt contains the subprocess invocation and timeout
  handling, rather than only the introductory argument helpers. `handle` supplies the MCP
  request-dispatch implementation. The short catalog still appears whole from its beginning.
- **MikroTik:** the selected `Call` window includes the read-only profile mutation guard
  (lines86–87), not just constructors and imports. No real router was connected.
- **Securepoint:** the `Execute` window includes state-fingerprint comparison and plan discard
  on mismatch (lines410–416), then discards the plan before sending a mutation (lines421–423).
  This is static source evidence of the guard, not a demonstrated rollback/transaction or
  proof of complete network safety.
- **codebadger-mola:** the57line Intent query remains whole. The larger WebView query has no
  recognized callable declaration, so it honestly falls back to its first80lines with
  `reason=no_callable_declaration`. Relevant later query fragments still require a follow-up
  explicit range; the collector does not invent a function anchor or confirmed vulnerability.

All implementation claims above refer only to the linked pinned source excerpts, not to an
inferred marketing summary. No live scientific validation, network mutation or Joern query
was performed.

## Cost and evaluation boundaries

Upstream bodies were544950bytes across30GETs, the same measured totals as the previous sample.
Tool JSON text **grew** from82858to91311UTF-8 bytes as code windows/metadata changed; this is
not a demonstrated token/credit saving. No model calls are part of the collector. Model
context, billed host credits and latency guarantees remain unmeasured; local elapsed is a
single observation, not a fair benchmark.

This is a targeted regression sample with known repositories, not held-out quality evaluation
or GitHub-wide coverage. Source-name heuristics can select wrappers, irrelevant or nested
functions and miss useful code elsewhere. Python AST parses without executing; other supported
languages use incomplete lexical recognizers. Unsupported syntax/languages, scan limits and
absence of declarations have explicit header fallbacks. Character clipping can even omit the
chosen anchor; retention flags and actual line citations must be checked before interpretation.
A complete requested window is not a complete function/file audit.

The committed metadata excludes verbatim third-party source snapshots; local snapshots were
retained for verification. Earlier samples keep their original runtime hashes and are not
retroactively relabelled as this later implementation.
