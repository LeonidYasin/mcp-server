# External idea-analog acceptance: TEST runtime 20d2675

## Follow-up: 65ddae1 installed; recovery check stopped at quota (13:51 UTC)

The operator subsequently supplied checksum OK and `TEST_ROLLOUT_PASS` for runtime `65ddae12bfaf6d117bb8f472ba396016db36610a`, previous `20d26756b87f78f28d9c3f5ea8a14b3fd1de36b7`, 120 tools, protected services unchanged. Backup remains private on VPS. The historical observation below describes the earlier runtime; the path-walk fix is now installed in TEST, not production.

The exact previously failing external request was repeated: `get_repo_info(owner=LeonidYasin, repo=ConstruBot, mode=public_evidence, ref=ee3d69e0f6c721207ab66ceef2d830a316d80d52, file_selection=explicit, evidence_files=[{path:backend/app/main.py,start_line:21,max_lines:20}])`.

Observed sequence at 2026-10-17 13:51:55–13:51:56 UTC:

1. Public metadata: HTTP 200, quota remaining 3.
2. Pinned revision: HTTP 200, remaining 2; tree `9d70d269d661d1ed4018c7300ad6c5ecea51c75a`.
3. Recursive tree: HTTP 200, refused `body_budget` at the unchanged 262144-byte per-response limit, remaining 1.
4. Non-recursive pinned root tree: HTTP 200, remaining 0. This confirms the deployed fallback was reached; no further child-tree or Contents GET was issued.

Final result: `state=unavailable`, `error=observed_rate_budget`, `files=[]`, 4 requests, 329254 cumulative response bytes, fixed 12-request ceiling. The fallback implementation is demonstrably running, but the file/range and full traversal are NOT accepted yet. The observed zero quota was honored without retries or authenticated fallback. GitHub reported reset epoch `1792246571` (2026-10-17 14:16:11 UTC).

Next action: after reset, explicitly repeat the same pinned request and verify `state=observed`, `explicit_path_walk_v1`, the linked root/backend/app tree provenance, blob integrity, and the requested lines 21–40. Reset time is provider guidance, not a reservation of quota. No new deployment or root command is required for that retry. The agent did not run Python/shell tools on VPS during this check, and did not schedule a background retry.

---

Observation window: 2026-10-17, 13:27–13:34 UTC. This is a bounded external MCP test, not a global GitHub census, semantic benchmark, novelty verdict or revenue assessment.

## Deployment versus candidate

- Operator reported `TEST_ROLLOUT_PASS` for exact runtime `20d26756b87f78f28d9c3f5ea8a14b3fd1de36b7`, 120 tools, protected service fingerprints unchanged. Backup remains private on VPS.
- After reconnecting `Leonid MCP — TEST`, the new tool is callable. The stale client catalog blocker is resolved.
- No Python/shell tool, service command, foreign-code execution, main merge or production deployment was performed during these checks.
- A later source fix plus tests is at `65ddae12bfaf6d117bb8f472ba396016db36610a`. [CI attempt 1](https://github.com/LeonidYasin/mcp-server/actions/runs/39036995274) completed successfully on Python 3.10/3.11/3.12/3.13. Python 3.12 job logs contain `1060 passed in 9.97s` (1033 prior tests plus 27 path-walk regression cases). This fix is NOT yet installed in TEST.

## Four discovery cases: transport and batching passed

Each case uses two caller-supplied formulations (`problem`, `mechanism`), `limit_per_probe=3`, `max_candidates=18`, `evidence_limit=0`, and `max_search_requests=2`. Three explicit calls use `start_probe=0`, `2`, `4`, retaining the same fingerprint. Probes 0–1 are broad, 2–3 zero-star, 4–5 forks-only. These are first pages, not exhaustive query results. Source repo is explicitly excluded when provided.

| Case | Problem terms / scope | Mechanism terms / scope | GETs | Rows | Unique IDs after caller merge |
| --- | --- | --- | ---: | ---: | ---: |
| Tablebot-pipe-Advanced | `telegram "google sheets" menu` / readme | `telegram "state machine" table` / readme | 6 | 18 | 18 |
| agora-mcp | `"offer" "want" marketplace` / readme | `pgvector matching agent` / readme | 6 | 18 | 18 |
| ConstruBot | `building material estimate` / readme | `parametric house` / default | 6 | 18 | 16 |
| Plain issue-dedup idea, no source repository | `github "duplicate issues"` / default | `github issues semantic search` / readme | 6 | 18 | 18 |

All 24 Search observations returned HTTP 200. In each case indices 0–5 were observed exactly once, fingerprints matched across calls, final continuation was null, and the source repo did not appear among returned candidates. Every returned row attributable to a zero-star probe had zero stars; every row attributable to a forks-only probe had `fork=true`.

The server is stateless: ConstruBot yielded two repeated IDs across batches, which the caller must merge. This is not a claim that server deduplication spans separate calls. Repositories found in multiple probes must retain their facet/probe provenance when merged.

TableBot's zero-star batch observed remaining Search quota 0 and returned `rate_budget_observed`, completed indices `[2,3]`, and the next request at index 4, without further GETs. The caller resumed after reset. The plain-idea final batch also observed remaining 0, but its planned probes were already complete. No automatic sleep/retry was used. Query totals above 1000 remain subject to GitHub's result window, regardless of `incomplete_results=false`.

Fingerprints:

- TableBot: `ff69fe244d05e0684ed418d40349e9de3849c4a06a727cab94fcc5e392b0921e`
- Agora: `90580a5bca5e7d8cba05d12a91049d1d3897984c7d31c220f712d946ce7ae3c1`
- ConstruBot: `a26bc44e6bd6449b3c8716928e6e682c50aca8ff8cf6cf14090f819cac15ca7a`
- Plain idea: `3efc039b88fc00a739624d9d2888c25226ec2421fc6a9470639777e8ba9814b6`

## Source-backed candidate inspection, not a list of asserted equivalents

### Issue duplication: useful zero-star implementation

`gramster/dedupper`, metadata observed at zero stars, pinned to `de21f2d036b8caa8b42d7f9b88e341c0493c5735`:

- [Implementation 150–249](https://github.com/gramster/dedupper/blob/de21f2d036b8caa8b42d7f9b88e341c0493c5735/dedupper/dedupper.py#L150-L249): SQLite schema, title/body composition, pairwise TF-IDF cosine threshold, and a separate `gpt-4o-mini` decision with bounded attempts. The README names a different model, so source takes precedence for the inspected implementation.
- [Implementation 250–349](https://github.com/gramster/dedupper/blob/de21f2d036b8caa8b42d7f9b88e341c0493c5735/dedupper/dedupper.py#L250-L349): already-existing open, not-yet-commented issues are compared with older stored issues. Candidate filtering is actually called before LLM checking. This is an existing offline/batch triage approach, not a demonstrated pre-creation suggestion UI or embedding ANN index. Accuracy, cost, scaling, update semantics and runtime remain unverified.
- Auto selection initially returned API transport wrappers (70–149); explicit follow-up ranges were necessary to reveal the actual algorithm. Do not equate auto-selected snippets with a complete explanation.

`pelikhan/action-genai-issue-dedup` was also rediscovered by the default-scope problem query. Its inspected [candidate gathering and prompt code](https://github.com/pelikhan/action-genai-issue-dedup/blob/bdb3b5d9451c1090ffcdf123d7447a5e7c7a2528/genaisrc/genai-issue-dedup.genai.mts#L166-L245) supports considering an existing Action rather than building from scratch, with the previously recorded functional differences. `code413/issue-duplicator` and `zakkie/gh-issue-duplicate` are lexical false-positive candidates: their descriptions concern copying issues, not detecting duplicates; do not promote them as verified analogs.

### ConstruBot: zero-star fork with inspectable adjacent functionality

`Giakomogcs/ai-parametric-house-3d` was discovered by the forks-only mechanism probe, metadata zero stars. Pinned head `fee398657767a5e0a11b9ab91a26cdcd03b9686a`:

- [API route 1–78](https://github.com/Giakomogcs/ai-parametric-house-3d/blob/fee398657767a5e0a11b9ab91a26cdcd03b9686a/src/app/api/generate/route.ts#L1-L78): prompt validation, an SSE generation entry point and a deterministic fallback call.
- [Scene code 27–106](https://github.com/Giakomogcs/ai-parametric-house-3d/blob/fee398657767a5e0a11b9ab91a26cdcd03b9686a/src/components/BuildingScene.tsx#L27-L106): interval subtraction and shared-wall coverage computations. These are potentially reusable visualization/geometry ideas, not evidence of ConstruBot-equivalent material estimates or structural engineering validation.
- Explicit fork-parent observation identified `marcos2872/ai-parametric-house-3d`; both inspected default-branch revisions were the identical full SHA above. Compare reported ahead 0 / behind 0. Do not market this fork as a separately novel implementation. Parent metadata also had zero stars. No license clearance inferred from missing metadata.
- Auto selection also spent slots on ESLint configuration and a layout component; file-selection quality still needs improvement. A correct bounded response is not necessarily the most informative response.

### TableBot: reject data-table/control-flow confusion

`eusoff-hackers/eusoff_meal_bot`, zero stars, pinned `6d3bf34f9b034bbb22e23ee91492992cc975bf14`, has [fixed command/callback dispatch and spreadsheet meal reads](https://github.com/eusoff-hackers/eusoff_meal_bot/blob/6d3bf34f9b034bbb22e23ee91492992cc975bf14/src/main.ts#L33-L109) and [hardcoded keyboards](https://github.com/eusoff-hackers/eusoff_meal_bot/blob/6d3bf34f9b034bbb22e23ee91492992cc975bf14/src/bot/keyboards.ts#L1-L39). Useful as an integration neighbor, but the inspected code does not establish a table-authored workflow engine. No full-repo absence claim is made.

### Agora: zero-star candidate rediscovered, mechanism distinction retained

`buidanhhuong/can-co` reappeared in the zero-star mechanism probe. Prior external pinned evidence at `8d97d1fc675f32eee9e8ae7af17be9c07aeba915` showed [embedding preparation and the start of attribute scoring](https://github.com/buidanhhuong/can-co/blob/8d97d1fc675f32eee9e8ae7af17be9c07aeba915/lib/engine/matching.ts#L18-L97). Earlier explicit inspection of [158–242](https://github.com/buidanhhuong/can-co/blob/8d97d1fc675f32eee9e8ae7af17be9c07aeba915/lib/engine/matching.ts#L158-L242) showed opposite-type/active/category/other-user filtering and attribute/trust subset ranking. Similar offer/want product concept does not establish Agora-equivalent pgvector cosine retrieval.

## Reproduced failure and source fix

ConstruBot at `ee3d69e0f6c721207ab66ceef2d830a316d80d52`, explicit `backend/app/main.py` 21–40, failed on the deployed runtime with `body_budget`: the recursive tree response exceeded 262144 bytes. No file excerpt was returned. This remains a failed live evidence case until the fixed candidate is installed and rechecked.

The source fix adds `explicit_path_walk_v1` only after an oversized recursive tree for explicit file requests. It traverses non-recursive trees linked from the pinned commit tree, caches shared directories, refuses truncated/mismatched/ambiguous trees, symlink/submodule traversal and non-regular leaves, and retains Contents/blob integrity validation. Failed recursive-source provenance remains visible. Existing 12-GET, per-response, total-byte, output and deadline limits are not raised or reset. Rate/HTTP/time failures do not trigger this fallback. Auto selection still refuses an oversized recursive tree because no explicit path set exists.

Regression cases cover nested recovery, shared-directory caching, file modes, tree identity/truncation/ambiguity, absent components, auto-mode refusal, oversized fallback responses, HTTP refusals, quota exhaustion, deep-path request caps, total bytes and blob integrity. CI success is evidence for the source candidate, not deployed recovery on ConstruBot.

## Narrower-query follow-up (13:40 UTC)

Eight additional Search GETs, two broad first-page probes per case, returned HTTP 200. These were new plans with `limit_per_probe=2`; their zero-star/fork continuations remain unrequested. They must not be added to the 24-probe completion claim as completed six-probe plans.

| Case | Default-scope formulations | Reported totals | Example metadata-only candidates |
| --- | --- | --- | --- |
| TableBot | `telegram "spreadsheet"`; `telegram "finite state machine"` | 403; 19 | go-telegram/fsm, Feolius/telegram-bot-fsm; spreadsheet integrations remain adjacent rather than equivalent |
| Agora | `"supply demand" matching`; `"offer" "want" matching` | 30; 33 | dirkju/SupplyDemand, Spring930/supply-demand-matching-platform, JaiSurya7022/skillswap, Rifat44334/skillswap.py |
| ConstruBot | `"construction" "material" calculator`; `"parametric house"` | 154; 9 | TechProofreader/Materials-Cost-Calculator, linalopes/parametric-house-generator; an awesome-list and parametric-household also remain false-positive risks |
| Issue dedup | `"duplicate issues"`; `"issue" "deduplication"` | 207; 53 | pelikhan/action-genai-issue-dedup, logpai/bughub dataset, Snowflake-Labs/sfguide-customer-issue-deduplication-demo |

Narrower scope yielded more task-specific descriptions in this small observation, not a measured precision/recall improvement. No newly listed implementation is considered source-verified merely from its name/description. These formulations are analyst-supplied: server search semantics were not changed. Prefer a narrow initial scope and expand README deliberately for recall, then reject catalogs, copying tools, household items and infrastructure unless their actual implementation answers the target problem. A dataset can aid evaluation without being a deployable replacement.

## Verdict and next gates

- **Passed:** new-tool external invocation, all planned first-page probes, zero-star/fork lanes, explicit continuation/fingerprint handling, honest quota stop, and selected code/fork-parent inspection.
- **Not passed:** full semantic relevance benchmark, complete analog recall, automatic informative file selection, and live ConstruBot recovery. Broad README formulations produced many generic catalogs/infrastructure hits and should be narrowed or reformulated; they are not automatically useful analogs.
- **Next:** improve formulations and rerank by cited mechanism evidence; review/install the tested path-walk candidate in TEST using an operator-run guarded rollout, then repeat the exact failed ConstruBot request. No production/main change is implied.
