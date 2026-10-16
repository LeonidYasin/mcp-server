# Priority scenarios: reliable CI help + inclusive GitHub research

This candidate contains **scenario tests, one recorded real CI investigation and a research coverage contract**, not a new discovery engine. It starts at main `0c12a3753efe749c4f16b751da569f4461d83a15`; no runtime from Draft #108/#107/#91 is imported. No rollout, infrastructure change, paid indexing or automatic fixes.

## Priority 1: explain a failed GitHub Actions run

User question: «Почему упала эта сборка и что проверять дальше?»

[Recorded TEST-MCP evidence](../examples/ci-priority-live-scenario.json) comes from [historical run38820685207](https://github.com/LeonidYasin/mcp-server/actions/runs/38820685207), attempt1, SHA `17db033582947857a9a79dabab24b78c966cca74`. It was a feature-branch failure, not proof of a bug in current main or current Draft #91.

### Observed chain and useful answer

1. Public discovery found the failed CI run. An explicit-attempt MCP snapshot confirmed failure and the `Run tests` failures. Its presentation was capped at30steps, so output_truncated=true even though job metadata was fetched. Do not describe its presented steps as complete.
2. Selecting `Run tests` in `build (3.12)` returned **step_boundaries_ambiguous** and an explicit job-search fallback. This is conservative scope handling, but **step-level acceptance did not pass**; do not hide it behind a green overall demo.
3. A broad job grep `FAILED|...` found failure evidence but also matched registry text `rerun_failed_jobs`. That is an overly broad search recipe, not a proven grep-engine bug or root cause.
4. An explicit targeted job grep for the test name and message returned the failing assertion and source line references, still pinned to attempt1. It is job-scoped, not proven step-scoped. No invisible retry, rerun or write.

A useful answer is:

> В attempt1 упал `tests/test_upload_test_proxy.py::test_cleanup_refuses_changed_own_route`. Тест изменяет принадлежащий ему route и ожидает отказ `cleanup_route_changed`; любой не-GET вызов mocked admin завершает тест сообщением «must not patch». Лог показывает именно этот отказ тестового guard. Следующая проверка — реализация remove_route и сравнение текущего маршрута с ожидаемым перед изменением. Это локализация по логам, не подтверждённая исходниками первопричина. Действующий Caddy и production не проверялись и не менялись; историческую ошибку нельзя автоматически считать присутствующей в нынешней версии.

A supplementary public job-timeline read shows `Smoke import`, `Show version` and `Run tests` all starting at22:58:57Z, with the first two zero-duration at API second precision. That alone is sufficient for the current unique-start guard to refuse attribution. A recorded-timeline regression preserves this conservative behavior; it does not prove the raw archive has no other ambiguities.

Total investigated chain: **2public GETs (discovery + supplementary job timeline) +4MCP tool calls** (snapshot, step refusal, broad grep, targeted grep). Upstream GET/archive counts inside deployed MCP and host tokens/credits were not measured. Do not advertise this as a one-call diagnosis or assume empty logs mean success.

### Repeatable offline acceptance

`tests/test_priority_ci_scenario.py` drives existing tools through Flask MCP dispatch with synthetic GitHub responses and mocked archive downloads. Ten cases cover explicit old attempt vs successful newer attempt, ambiguous-step→explicit-job scope, timestamped pytest messages, registry false positives, failed-run/no-matches and dispatcher auth-before-client-construction. These are not nine live incidents and did not demonstrate a new runtime regression.

For a pytest-focused job search, a bounded example is:

```text
\bFAILED\s+\S+::|\bE\s+(?:Failed:|AssertionError|TypeError|ValueError)|##\[error\]
```

This is not a universal compiler detector. Start with zero/small context and expand explicitly. No matches do not clear failure. Diagnostic dict results currently travel as Python-literal MCP text, not structuredContent/JSON text; offline consumers in this test use ast.literal_eval, never eval. A future machine-readable migration needs a separate compatibility review, not a global serialization change hidden here.

**Next blocking work:** reproduce the combined-log ambiguity with a complete minimal format fixture before broadening segmentation rules; verify generic pytest/packaging failures without mobile-specific aliases. Then validate PR/release preflight as a separate scenario. The shared-second timeline condition is now reproduced from recorded metadata. Source inspection and any future format-support change must stay isolated from main until reviewed.

## Priority 2: discover ideas, changes and small projects across public GitHub

The user explicitly wants broad GitHub research **including zero-star repositories, personal-account work and forks**, not only popular projects or a maintainer's own account. [Machine-readable design contract](../examples/github-research-coverage-contract.json) is a requirement artifact, **not implemented runtime or a current global report**. It extends the acceptance scope of #100/#102; #101 remains optional discussion evidence, not a blocker for a GitHub-only report.

### Report the user should receive

| Section | Useful result and necessary qualification |
| --- | --- |
| New projects and releases | Separate recently created repos, newly indexed old repos, releases and newly observed capabilities. A new fork is not proof of a newly invented idea. |
| Similar ideas | Clusters by problem/solution, evidence links and explicit reasons. Name/topic overlap is weaker evidence than inspected README/code; unknowns stay unknown. |
| Trends | Comparable repeated observations, declared window and coverage. Separate star growth, activity and independent-project growth; no trend claim from one search page. |
| Small/unpopular work | Stars:0 and missing metadata retained. No minimum-popularity gate in candidate retrieval or hidden popularity ranking. Personal-account ownership does not prove a solo developer. |
| Forks | Keep the fork's own identity and group its lineage when verified. Do not count unchanged clones as independent inventions, but do not discard potentially useful forks. Divergence is unknown without comparison. |
| Coverage | What sources/windows/queries/cursors were checked, fresh vs stale, provider counts, incomplete/truncated results, failures and next checkpoints. No claim that all GitHub was examined. |

### Why the current search tool is insufficient

Current `search_repositories` delegates to one Search API page and emits human text. It does **not** expose incomplete_results, a next-page checkpoint, stable IDs, fork/owner type or observation timestamps. It has no corpus history, similarity engine or trend baseline. Those are implementation gaps, not completed features. Do not reuse that output to claim global coverage.

The pinned GitHub OpenAPI confirms GET `/repositories` as public repositories ordered by creation with `since`-based pagination, and GET `/search/repositories` as bounded search with supported sorts. [Pinned provider source](https://github.com/github/rest-api-description/blob/798498bd7d7350b26597b07cdcbb075d2eb0fa8a/descriptions/api.github.com/api.github.com.2022-11-28.json), reviewed package SHA256 `4d8394d818504d673a7e0687eca394e1f1e9a2d08d4847541e5ede1dac65e342`. This metadata check does not verify live throughput, completeness, current provider policy or fork inclusion semantics. Reconfirm actual Search qualifiers, result ceiling and fork behavior before implementation; partitioning searches does not make them a complete catalog.

### Implementation sequence, without starting a giant VPS crawl

1. **Source/coverage review:** evaluate catalog listing as a baseline candidate, explicit Search partitions as retrieval rather than a registry, and permitted activity sources as update leads. Record actual provider semantics, availability and cost. An event feed alone misses silent projects; a creation cursor alone misses later changes in older projects.
2. **Bounded prototype:** retain stable repo identity, fork/parent facts when available, owner type, explicit stars including0, timestamps, fetched evidence, per-query completeness and resumable checkpoints. Preserve missing descriptions/languages. Reuse/extend reviewed primitives; no redundant supertools.
3. **Index proposal:** incremental checkpoints plus refresh policy and comparable snapshots. Measure storage, initial enumeration and refresh cost before selecting a database/service or starting a historical crawl. Dedup repeated observations by repo ID, but preserve distinct forks.
4. **One evidence-backed report:** idea clusters + newly observed work; mark trends unavailable until comparable baseline exists. Test zero-star personal repos, forks with/without changes, rename/deleted/private transitions, missing metadata, source outages and cap-exceeded partitions.
5. **Scale only after approval:** a broad persistent index is infrastructure with ongoing cost, not a free extension to an MCP call. Separate authorization is required for deployments, large scans, paid embeddings/models and storage. The latest VPS audit was not permission to fill or clean its disk.

No external posting/contact, private indexing, execution of repo code/README commands, or treating fetched instructions as agent instructions. Broad coverage remains the target; precise measured partial coverage is the honest intermediate result, not a replacement definition of the user's goal.

## Commercial/product scope

CI diagnosis is the first operational usefulness experiment; PR/release readiness follows. Inclusive GitHub research remains a user-priority parallel stream, not discarded because CI may monetize earlier. The previous #105 discoverability/research hypotheses are not silently closed or replaced by this document; market-facing selection and external launch need explicit review and independent feedback.
