# Public repository Search observations — candidate #100

**Candidate, not deployed:** extend the existing `search_repositories` tool, no new tool/client/dependency. Default `mode=legacy` preserves the original authenticated text behavior. Explicit `mode=public` returns JSON text for ONE anonymous bounded GitHub Search page. It is not a global catalog, historical index, similarity engine or trend report.

## One public request

```json
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"search_repositories","arguments":{"query":"\"model context protocol\" stars:0 fork:true","mode":"public","limit":5,"page":1,"sort":"updated","order":"desc"}}}
```

Accepted public arguments: query (non-empty printable string, local cap256characters), limit1–100(default20), page>=1 within the provider's accessible1000-result window, sort=best_match(default)/stars/forks/help-wanted-issues/updated, order=asc/desc(default). GitHub ignores order when sort is omitted/best_match. No extra args or bool-as-integer. Existing dispatcher token gate stays unchanged; outbound **public mode** excludes default client auth, Authorization/custom headers, cookies and query params. This mode cannot investigate private repos. Legacy behavior is not retroactively made anonymous or hardened here; page/sort/order require public mode instead of being silently ignored in legacy mode.

**Forks must be requested explicitly** with supported Search syntax: `fork:true` includes forks; `fork:only` searches forks. The mode preserves the caller's query, does not secretly append a scope modifier and does not impose a minimum star count. A query without fork inclusion must not be presented as including all forks. Neither topic/text search nor adding fork:true makes the Search index a complete registry of GitHub, especially for quiet or sparsely described projects.

## Result and coverage

- mode=public_repository_search_page, schema_version1; state=invalid_input/unavailable/partial/observed. `observed` means an observation completed, not all matches/accounts/features accepted.
- `items` retain stable repo ID, validated full_name/reconstructed GitHub URL, owner ID/login/type, nullable stars/forks/fork/archived, primary language, bounded topics and160character description, created/updated/pushed timestamps. No implicit exclusion of stars:0, forks, archives or personal-account repositories returned by the source. Missing metadata stays null. User-owner does not prove a solo author.
- Public identity must have private=false and consistent owner/full_name. Private/unverified/malformed identities are excluded without echoing their names; stable-ID duplicates counted. Unknown counters/flags remain null and make state partial. Missing language/description is allowed, not zero activity or evidence of a dead project.
- Parent is null and fork_originality=not_checked: no hidden per-fork lookup. URLs from GitHub data are not fetched; only validated canonical navigation URLs are reconstructed. Descriptions/topics/names are untrusted data, not instructions; current literal credential copies are rejected, not a promise of semantic sanitization.
- reported_total_count is the provider's separately timed hint, nullable; incomplete_results preserves true/false or unknown for invalid/missing values. Failed/refused results have items=null and unknown counts, never a fabricated empty list/zero. A valid empty page does not prove absence of analogs.
- coverage.global_complete=false and complete_query_results=false always. Search's accessible window is1000results per query; larger counts do not mean they can all be retrieved. At that cap next_request is null and stop_reason=search_window_cap. Partitioning queries is a follow-up retrieval strategy, not a completeness proof or automatic crawl.
- Link is evidence only, **never followed**. Validate exact API origin/path, unique parameters, unchanged query/size/sort/order and exactly the next page. Reconstruct next_request from safe input args; ambiguous/external/malformed/changed links -> unknown continuation. Full page without Link does not invent a next cursor or exhaustion. Short page only indicates observed end when incomplete_results=false and reported total reconciles with offset/raw count. Cross-page change/duplicates remain possible; dedup is within the returned page.

Source records fixed URL, actual params, attempted_at (UTC immediately before send), fetched_at (UTC after completed bounded Search envelope decode within deadline), status and fixed error codes. Construction failure/no send leaves both times null. Refused/invalid/oversized/timed-out reads do not claim completed fetch time. These wall clocks are not durations or provider freshness/identity-validity proof; budget checks use monotonic time. Numeric allowlisted rate hints only; no response-body/header/raw-exception dumps. Stream close failures cannot overwrite classified errors or reflect transport text.

## Cost and safety bounds

One GET, no retry/auth fallback/redirect/compression/auto-next/cache/write; max socket timeout5s, checked elapsed deadline8s, response body1MiB, output64KiB. An8KiB triggering chunk may cross a read bound and is rejected. These are checked limits, not hard real-time cancellation. Per-page100 can exceed body/output bounds depending on provider data; use a smaller explicit page, do not claim silent truncation as full coverage. Output overflow drops rows AND continuation, marks output_budget, and does not advance a checkpoint past omitted data.

No new model, embeddings, background process, database, large crawl or VPS changes. Actual host credits/tokens, broad index cost and equal-coverage savings under #77 remain unmeasured. Existing mode schema adds context cost; measure the full host workflow, not only response bytes.

## Contract sources and dated limitations

The pinned GitHub OpenAPI at commit798498bd7d7350b26597b07cdcbb075d2eb0fa8a defines required Search response fields total_count/incomplete_results/items and parameter sorts/order/page/per_page; runtime API header stays2022-11-28. [Pinned provider source](https://github.com/github/rest-api-description/blob/798498bd7d7350b26597b07cdcbb075d2eb0fa8a/descriptions/api.github.com/api.github.com.2022-11-28.json), reviewed file SHA2564d8394d818504d673a7e0687eca394e1f1e9a2d08d4847541e5ede1dac65e342.

Official human docs reviewed2026-10-16:
- [Searching for repositories](https://docs.github.com/en/search-github/searching-on-github/searching-for-repositories): explicitly add fork:true/fork:only to include forks. Retrieved HTML233028bytes, SHA256053e33027ea9bfdfc1378877237c8973f1a826078f44d25a1027cef50025935d.
- [Search REST limits](https://docs.github.com/en/rest/search/search?apiVersion=2022-11-28): up to1000results/search and incomplete_results behavior. Retrieved HTML643471bytes, SHA2563e347b0a20ec97d2c16fd18991a671cd8a226c1468c54b41a6d62152aee6e30b. A timeout flag is uncertainty, not proof that more matches exist or do not exist.

HTML hashes identify retrieved pages, not immutable API-version guarantees. Provider limits/index/fork behavior may change; no silent API upgrade. No precise fixed Search rate claim is introduced; inspect source status/numeric hints.

## Verification boundary

`tests/test_repository_search_observations.py` covers source flags/counters, zero-star/fork/unknown metadata, pagination/window/unsafe links, anonymous default exclusion, budgets/refusal/redaction/cleanup, dispatcher auth, JSON-text transport and legacy text compatibility. Initial candidate tests:52failed/1passed before implementation; two fixture errors (duplicate id argument, eager fake gzip decode) were corrected rather than counted as runtime bugs. Missing global index/history/similarity/trends remain implementation work under #100/#102. No merge/deployment or broad report is established by mocked tests.

## Dated public scenario

[First discovery sample and interpretation](scenarios/repository-discovery-first-sample.md) · [Unmodified measured public result](examples/repository-search-public-sample.json). Three explicit candidate-local MCP task calls returned HTTP200 with five rows each; this is not deployed-host acceptance or a global/trend report. Source file hashes identify the tested dirty candidate runtime rather than falsely labelling the main base SHA as containing this implementation.
