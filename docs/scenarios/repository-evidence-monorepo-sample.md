# Monorepo role-diversity regression sample — candidate, not deployed

## Outcome and scope

`auto_paths_v2` replaces the fixed two-source allowance with all slots remaining after
README, manifest, architecture and license. Source selection uses explained path-role/group
hints and a weak owner/repository-token match for domain directories. The six-file ceiling,
anonymous verified reads, callable-window policy, explicit mode and legacy default remain.
Changed/added paths from an explicitly requested fork comparison retain priority.

This is **regression testing of three previously inspected repositories**, not a fresh
held-out evaluation, a random sample, global GitHub coverage or proof of commercial value.
Their commits were fixed before this run; no upstream project was installed or executed.
All three used the candidate-local Flask MCP dispatcher with `public_evidence`, auto paths,
full pinned ref and `compare_parent=false`; this is not deployed-host validation.

The run completed at `2026-10-16T23:10:10.830985+00:00` with 25 anonymous GETs,
533,465 response-body bytes, 70,528 aggregate MCP text bytes and 16 returned file excerpts.
All three responses were `observed`, with no reported gaps or errors, and at most nine
requests per call (ceiling twelve). These counts do not establish general performance.
[Machine-readable observations](../examples/repository-evidence-monorepo-sample.json)
contain pins, source records, content hashes, ranges, selection reasons and runtime hashes,
without third-party verbatim excerpts.

**Revision caveat:** live reads preceded one final defensive guard rejecting dot-only
owner/repository identity components. Live and final runtime hashes are recorded separately.
After that guard, the final path policy reproduced all three plans on saved trees, comparing
all plan fields after normalizing excerpt start lines/reasons populated during reading.
This is not a final-revision live rerun; full final-revision unit/integration and distribution
checks are reported below. No authenticated fallback, retry or extra discovery was used.

## Before / after

| Repository at fixed commit | `auto_paths_v1` source/fallback choices | `auto_paths_v2` source choices | Meaning |
| --- | --- | --- | --- |
| `peakflo/pfMCP`, `25b8cb988d6e0ca23dce445bc2bdb47fb897fdfb` | launcher, alphabetically early Ahrefs integration, Dockerfile | launcher, auth factory, Peakflo integration | Three distinct path-role hints in the three source slots. Identity match is a hint, not proof Peakflo is the primary integration. |
| `bradsjm/mail-imap-mcp-rs`, `10a73f41b3851e3cd7e3a07ba823088e1a264d13` | server, main, Dockerfile | server, main, config | Adds a configuration file without increasing the six-file budget; deployment context is displaced. |
| `Aristide021/solana-dev-mcp`, `edcab432766f377d1506d163cd2f5bbbd48db759` | `index.ts` | `index.ts` | No eligible alternative source path; four total files remain. |

README, manifest and license choices stayed unchanged. The older
[framework sample](repository-evidence-framework-sample.md) is a historical observation,
not retroactively relabeled as v2 path selection.

## What became more concrete — and what did not

### pfMCP: credential-provider wiring and domain dispatch

The selected [auth factory, lines 1–67](https://github.com/peakflo/pfMCP/blob/25b8cb988d6e0ca23dce445bc2bdb47fb897fdfb/src/auth/factory.py#L1-L67)
contains `create_auth_client`: an explicit client class is instantiated directly; otherwise
`ENVIRONMENT` branches to Gumloop or Nango, with a LocalAuthClient fallback. The Nango branch
reads `NANGO_SECRET_KEY` and `NANGO_HOST`. This is static evidence of configurable credential
provider wiring, not evidence these providers authenticate successfully or protect secrets.
The imported client implementations were **not** read in this six-file sample.

The selected [Peakflo handler, lines 870–941](https://github.com/peakflo/pfMCP/blob/25b8cb988d6e0ca23dce445bc2bdb47fb897fdfb/src/servers/peakflo/main.py#L870-L941)
includes a `@server.call_tool()` callback: it obtains a token, branches through source-system
integration matching, otherwise checks known tool names, makes a request and checks status.
Helper names/call sites do not prove authorization, endpoint behavior, data isolation or a
working integration; their implementations are mostly outside the returned window.

**Commercial hypothesis, not a finding:** provider abstraction and domain routing could be
useful when packaging reusable business integrations. Demand, licensing suitability, support
cost, reliability and willingness to pay remain untested. Existing fork status does not show
which of these lines differ from upstream: parent comparison was not requested in this run.

### Rust: more context, still a window blind spot

The additional [config excerpt, lines 240–319](https://github.com/bradsjm/mail-imap-mcp-rs/blob/10a73f41b3851e3cd7e3a07ba823088e1a264d13/src/config.rs#L240-L319)
shows environment parsing helpers for booleans and numeric values. Its callable hint centers
on a helper, **not** necessarily the configuration fields or write-control settings a reviewer
would want. Selecting a configuration-role file is not proof of security-control coverage.
An explicit follow-up range is needed for a targeted question; do not infer write safety
from this result. This limitation was recorded, not tuned away on this known example.

## Final local verification

- 22 added path-policy tests: diversity, identity hints and invalid identities, role caps,
  namespace diversity, changed-path priority, input-order determinism, excluded paths and
  deployment fallback accounting.
- 845 full tests passed, including existing verified-source/budget/auth/legacy/window tests.
- Source distribution and wheel built; 845 tests also passed from the extracted sdist.
- No new registered MCP tool or dependency; no merge, release or VPS deployment.

## Limits / next work

The role inventory is only a heuristic over eligible observed paths. Documents can leave
only two source slots; unknown wiring, generic factories, unusual names and generated code
can be missed. Identity tokens can match an incidental integration. Path-role diversity is
not semantic relevance, completeness, novelty or a quality score. Giving source files more
slots deliberately reduces deployment/extra-manifest context.

`requirements.in` and equivalent direct-dependency inputs remain unrecognized by this path
policy; pfMCP still selects `requirements.txt`. Broader trend/similarity claims need a separate,
dated discovery/cohort protocol including low-star repositories and forks, followed by
source-backed comparison; this regression sample supplies neither a global index nor trends.
