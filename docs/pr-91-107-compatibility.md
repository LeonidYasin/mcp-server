# Local compatibility check: Draft #91 + Draft #107

This is an isolated integration experiment, **not a merge, deployment, maintainer approval, or closure of #88/#103**. [Machine-readable evidence](examples/pr-91-107-compatibility.json) records exact inputs and observed checks. Only this report and an offline benchmark environment pin are added to #107; no upload implementation or conflict resolution is imported into that branch.

## Pinned inputs and direction

- main: `0c12a3753efe749c4f16b751da569f4461d83a15`.
- [#91 upload candidate](https://github.com/LeonidYasin/mcp-server/pull/91): `4edf84e3c67809122ec41d6b3de98970bb840f34`.
- [#107 audit candidate](https://github.com/LeonidYasin/mcp-server/pull/107): `0ed59daa35bc4374b7524d8bd29f3f7bc21d4493`.
- merge base: `a9a303f2434bc67a6f41a3dcb8524461cb2407b1`.
- Direction: detached #107 tree receives pinned #91 using `git merge --no-commit --no-ff`; no merge commit created. Reverse-order rebases/merges and later commits have not been tested.

## Conflicts and resolution checklist

Seven files overlap. MANIFEST.in merged automatically. Six content conflicts require deliberate resolution:

| File | Local resolution policy, not a pushed merge |
| --- | --- |
| README.md | Retain audit and upload candidate contracts, preserve dated #91 acceptance evidence and pending gates; use local integration revision11 |
| ROADMAP.md | Keep both workstreams and dependency order; local revision11, no completed live/E2E claim |
| SANDBOX.md | Keep upload owner/quota/TTL/budget boundaries and audit read-only restrictions; preserve acceptance evidence |
| TOOLS.md | Reconcile four feature flags and measured counts below; retain both contracts and deployed snapshots separately |
| docs/project-map.md | Preserve both workstreams and dated upload acceptance status; local revision11 |
| docs/tool-inventory.json | Regenerate from merged code, never select one side's stale counts |

Revision11 exists **only in the local integration tree**. #107 remains revision10, #91 revision9. Historical production/TEST snapshot counts are not replaced by candidate registry totals.

Initial combined suite: **823 passed, 2 failed**. Both failures were hardcoded totals in `tests/test_uploads.py::test_fresh_discovery_default_and_upload_only`: old113/119 need114/120 in a future combined branch. No runtime source conflict was observed; that is not a promise of behavioral compatibility outside these tests.

## Measured combined profiles

| Profile | Tools | Upload tools |
| --- | ---: | ---: |
| All flags off (default) | 114 | 0 |
| Uploads only | 120 | 6 |
| Previous three flags on, uploads off | 144 | 0 |
| All four flags on | 150 | 6 |

All names unique. `audit_repo_seo` remains present with the same schema and existing token gate in each profile. All-four-flags evidence is **discovery only**, not full execution acceptance for every tool. Default/ uploads-only profiles do not expose run_command. Uploads remain default OFF; when enabled, #91's 1MiB envelope cap applies to **every POST /mcp**, including legacy calls. Its existing policy tests pass; real-host payload compatibility is still a separate gate.

## Offline benchmark isolation fix

The benchmark initially reset only the older three feature flags. In the combined tree, an inherited ENABLE_FILE_UPLOADS=1 changed the tool catalog and evidence. The script now explicitly resets that flag to0 too. With incoming flag0 and1, both reruns exactly reproduce all six checked-in baseline rows. No savings percentage, equal-evidence comparison, actual Notion credits, billing or observed model-turn claim is added. The checked-in benchmark baseline describes the audit-only candidate, **not** an uploads-enabled production catalog.

## Validation performed locally

- Resolved combined checkout: **825 passed**.
- Audit suite with ENABLE_FILE_UPLOADS=1: **75 passed**, including real in-process MCP dispatch with mocked upstreams.
- Combined wheel/sdist build succeeded; extracted sdist: **825 passed**.
- Docs guard: **141 links**, inventory114 default/150 all-enabled.
- Local tested integration tree: `efbafcbeb9fdf1295a2aca6d5a389f2deab3b55b` (Git tree object only; no commit or remote ref).

The initial and final failures/results are recorded separately. These are local tests, not CI for a merged PR. Previously recorded public API403 is not retried or bypassed here; no successful current live/private/deployed acceptance is claimed.

## Reproduce before any actual merge

1. Fetch exact input commits and confirm all three heads; do not substitute a moving branch silently.
2. Create a detached worktree at pinned #107; locally merge pinned #91 with --no-commit --no-ff.
3. Reconcile the six files above, preserving both candidate contracts and historical evidence; reserve a fresh documentation revision for an actual integration.
4. Adjust the two discovery totals to114/120 **in the combined test tree only**; force ENABLE_FILE_UPLOADS=0 in the offline benchmark alongside the older three flags.
5. Regenerate inventory with `python scripts/check_docs.py --write-inventory`; rerun all four discovery profiles and the docs guard.
6. Run `pytest -q`, then `ENABLE_FILE_UPLOADS=1 pytest -q tests/test_repo_discoverability.py`; build wheel/sdist and run the extracted sdist suite. Run the benchmark twice with incoming upload flag0/1 and compare the complete output JSON to its baseline.
7. Recheck the latest PR heads/CI/reviews and outstanding live, identity, quota, retention and host-cost gates. The local experiment is not permission to merge/deploy.

For contracts on this audit-only branch see [audit contract](repo-discoverability.md) and [benchmark method](repo-audit-benchmark.md). Upload acceptance remains in pinned #91; its evidence is not reclassified as complete by this experiment.
