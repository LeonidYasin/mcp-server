# GitHub author analytics — phase1 candidate (#99)

**Phase1 implemented in Draft #108, not deployed:** `analyze_github_author` now collects a public profile and ONE owned-repository page, including zero-star/fork/archive rows, plus primary-language counts. Events, private workflows and the complete original proposal remain unimplemented. The tool is registered only in this candidate code; it is not available merely because this branch exists. This branch starts from main `0c12a3753efe749c4f16b751da569f4461d83a15`; it does not include Draft #107 or #91 and does not modify either other candidate branch or any deployed service. #99 stays open.

[Machine-readable proposal](examples/github-author-analytics-contract.json) · [Synthetic design examples and pending handler test matrix](examples/github-author-analytics-design-fixtures.json).

## Current phase1 runtime contract

```json
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"analyze_github_author","arguments":{"username":"alice","repo_page":1,"per_page":20,"include_text":false}}}
```

Only username, repo_page(1–10000), per_page(1–20), include_text(boolean) are accepted. Events/allow_private/unknown keys are rejected before network; there is no ignored activity switch. Existing dispatcher authentication remains; outbound reads are anonymous even when the shared HTTP client has default Authorization, cookies, custom headers, auth or query params. Explicit send auth=None, fixed URL and replacement headers prevent forwarding those defaults; tested with synthetic secrets.

At most **2GETs**, profile then one repos page; JSON256KiB/response,512KiB total,64KiB output; socket<=5s within a checked10s deadline, not hard real-time cancellation. The triggering8KiB chunk can cross a read limit and is rejected. Identity encoding only, no retries/redirects/cache/external fetch. 401/403/429 stop future requests. Safe numeric rate hints only. Profile failure stops before enumeration; repo failure preserves independently observed profile. Counters missing/invalid are null, not0. Body/exception/header dumps are never returned.

Return schema_version1, runtime_phase=profile_repos_only, outcome invalid_input/unavailable/unsupported_account/partial/observed. observed means a bounded observation completed, NOT complete account coverage, feature acceptance or data freshness across endpoints. Sources carry fixed URL/query/fetched_at/status; no commit SHA invented for list/profile observations. User profile has stable ID/login, public counts with visibility caveat and parsed created/updated times. Row provenance uses source1. Profile count hint never proves repository exhaustion. Primary-language counts cover returned valid/deduplicated rows only, with known/unknown denominators. Size is size_kb_reported (provider size field), no conversion to bytes/KiB.

Private/foreign/malformed rows excluded without their identifiers; within-page duplicate IDs counted. Invalid numeric/bool fields become null/unverifiable and cause partial. Language too long/invalid is unknown, not a clipped language identity. Profile/repo timestamps are normalized UTC or unverifiable. Optional public prose is bounded, labelled untrusted, records truncation, and rejects literal current credential copies; this is **not** semantic prompt-injection sanitization. Email/blog/avatar/download/raw payload fields are not exposed or fetched.

Validated next Link is only evidence (the requested /users/login/repos path or /user/{verified_profile_id}/repos canonical alias observed from GitHub; no other user ID): reconstruct next_request from safe arguments, never request Link URL. Changed/duplicate scope params or external/malformed Links -> has_more=null, no continuation. Full page without Link does not prove exhaustion. Short page or consistent no-next Link can indicate observed listing exhaustion; complete_account_inventory is always false. Output overflow removes page content and continuation instead of advancing past dropped rows. Cross-page mutation/duplication cannot be ruled out. Unsupported account types (including organizations/bot aliases) are not called empty.

### Version-pinned verification

[Selected OpenAPI evidence](examples/github-author-openapi-2022-evidence.json) pins github/rest-api-description commit798498bd7d7350b26597b07cdcbb075d2eb0fa8a, file api.github.com.2022-11-28.json, SHA-2564d8394d818504d673a7e0687eca394e1f1e9a2d08d4847541e5ede1dac65e342. Verified the two implemented GET endpoints, owner/full_name/asc/page/per_page parameters and repository counter/owner/private/language/flags shape; the package info.version1.1.4 is **not** the API version. Existing runtime2022-11-28 header unchanged. Events endpoint was inspected but remains unimplemented; timeline retention still derives from dated human docs, not an immutable OpenAPI guarantee.

### Verification boundary

Handler/HTTP tests now exist separately in tests/test_author_analytics.py. The original14 hand-authored examples remain design examples, not retroactively generated outputs. Events matrix cases are still pending; handler tests do not establish actual host cost, permitted public live success or deployed acceptance. Source hash/shape review is not API live acceptance. Keep #99 open. Local registry114default/144all-enabled, no dependency/version bump; these are not deployment counts. #107 and #91 code are not imported. Documentation revision12 distinguishes this candidate from #91 revision9/#107 revision10 and the local-only integration revision11.

## Dated public phase1 smoke — local handler, not deployment

- [Initial partial observation](examples/github-author-phase1-initial-partial.json):2anonymous GETs returned200/200 and3rows, but continuation was unverifiable because GitHub Link used /user/79429232/repos rather than /users/LeonidYasin/repos. This result is retained, not relabelled successful.
- One bounded diagnostic run (2GETs) captured that Link locally. Regression tests then failed for the verified numeric-ID alias and missing profile-count partial state; both were fixed. The parser now accepts only the already observed profile ID as an evidence alias and reconstructs /users/{requested_login}/repos arguments; it never fetches the Link URL or accepts another ID.
- [Corrected local observation](examples/github-author-phase1-public-smoke.json):2anonymous GETs,200/200,3public rows, has_more=true, safe next_request, outcome observed. No automatic second-page fetch, authenticated fallback, private audit or deployed MCP acceptance occurred.

Across the three separately labelled local invocations:6GETs total, no retries within a call. This is one dated author/first-page smoke, not a representative sample or all-account inventory. Zero-star/fork/archive and failures have synthetic regression coverage; do not extrapolate the live3rows to every case. Runtime/HTTP suite and original artifact tests are separate; host credits/billing/equal-coverage cost remain pending #77.

## Original complete proposal — not implemented as a whole

The sections below retain the broader reviewed design. Their3-request/15s budgets and Events parameters describe a **future complete proposal**, not the current2-request/10s phase1 schema above. The machine JSON separates proposed_complete_input_schema from runtime_phase1. Reconfirm any future additions with regression/HTTP/cost/live gates before expanding this contract.

## Confirmed provider documentation, and a version caveat

Reviewed the official documentation on 2026-10-16, not assumptions from the PDF:

| Source | Observed contract | Consequence |
| --- | --- | --- |
| [Get a user](https://docs.github.com/en/rest/users/users#get-a-user) | Public profile can be requested anonymously; private-profile followers/following may be masked as0; unauthorized access to an Enterprise Managed User can return404 | A returned0 does not prove no followers;404 does not prove deleted/nonexistent. No authenticated fallback or outreach/email collection |
| [List repositories for a user](https://docs.github.com/en/rest/repos/repos#list-repositories-for-a-user) | Lists public repos; type defaults owner; sort includes full_name; per_page max100, default30; page-based pagination | Use owner/full_name/asc, no Search and no implicit star/fork/archive filter; local page cap20 is a deliberate tighter bound |
| [About GitHub events](https://docs.github.com/en/rest/activity/events#about-github-events) | Timeline includes up to300 events created within the past30days | Neither days=90 nor traversing every returned page promises a90-day history; window completeness remains false |
| [Public events for a user](https://docs.github.com/en/rest/activity/events#list-public-events-for-a-user) | GET /users/{username}/events/public; max100 per page; not real time, delay30s–6h | Public-only endpoint, no private events URL template, no raw payloads, no claim that PushEvent count equals commits |

Important: the documentation renderer reported **2026-03-10 latest**, even when the request included apiVersion=2022-11-28. The source hashes record the retrieved pages, **not proof that all statements were version-pinned**. Existing project requests use2022-11-28. Before implementing further phases, reconfirm those pinned API contracts/fixtures; do not upgrade the runtime header silently. Provider observations are dated and can change. No deployed acceptance is established by this documentation; any candidate local public smoke must be labelled separately.

## Reuse and non-goals

- Existing `list_my_repos` reads authenticated `/user/repos`, so it cannot stand in for arbitrary public-author enumeration. Keep its behavior unchanged in this design.
- Existing `get_repo_info` is single-repo metadata. Existing `get_repo_languages` exposes Languages API bytes for one repo; do not relabel that as the primary-language distribution proposed here.
- Reuse the existing GitHub client/dispatcher architecture. A future safe bounded reader must avoid the client's ordinary redirect-following/body-reflecting request wrapper. No second GitHub client stack, global crawler, new cache, persistent identity store, background process, paid service or install.
- Initial scope is public owned repositories of supported user accounts with verified stable numeric identity. The proposed strict validator does not support bracketed bot aliases such as github-actions[bot]; bot-alias support and Organizations require separately reviewed identity/endpoint contracts; do not silently use a different endpoint or call an unsupported account empty.
- Private data is **unsupported in the initial candidate**. Do not add a token selector, permission escalation or private flag that the endpoint cannot satisfy. An explicit private workflow would need separate design/authorization and isolation tests.
- No author-quality/risk/dead-project score, inferred employer identity, contact harvesting, competitor ranking, batch fan-out or byte-weighted cross-repo Languages API. #100/#101/#102 remain separate.

## Proposed request, not a callable tool

```json
{"username":"synthetic-author","per_page":20,"repo_page":1,"include_text":false,"include_activity":false,"activity_days":30,"event_page":1}
```

Reject unknown keys and wrong types (including booleans used as integers) before any network request. Username is1–39 ASCII letters/digits/hyphens, begins/ends alphanumeric; reject consecutive hyphens too. No URL, slash, percent-encoding, dot, whitespace or arbitrary endpoint. Project policy can be stricter than provider usernames; test it explicitly. Keep requested and observed login separately; case-only normalization is allowed, rename redirects are not followed. Verify profile stable numeric ID; repository owner ID must agree.

- repo_page1–10000; per_page1–20, default20. No automatic traversal. Continuation means another explicit bounded call with the same username/per_page and the next validated page.
- include_text=false by default. If true, selected public profile/repo prose is bounded and labelled untrusted data; never instructions. No public email/contact field. Never fetch blog/homepage/avatar or any payload URL.
- include_activity=false by default. When true, request one public event page (per_page100, event_page1–3). activity_days1–30 is a local UTC filter, **not a provider history guarantee**. At page3 stop at the documented timeline cap rather than inventing page4.
- No field modes that trigger hidden per-repo calls. Fixed columns plus optional bounded text keep fan-out and schema small.

## Execution plan and hard budget proposal

At most three fixed-origin GETs, one attempt each: profile, one repo page, optionally one public-event page. Public outbound requests must not contain Authorization, cookies or a credential inherited from shared client defaults; existing MCP dispatcher authentication remains separate. Recheck the existing token-gate policy with #53 before registration; “anonymous outbound” does not mean “unauthenticated MCP transport.”

Max retained JSON256KiB/response, total768KiB; output64KiB UTF-8. Identity encoding only; bounded8KiB streaming chunks; count the triggering chunk before rejecting overflow and stop future reads after a global budget is exhausted. Socket timeout<=5s with a15s monotonic deadline checked between requests/chunks, not hard real-time cancellation. A host disconnect cannot be promised to cancel synchronous upstream I/O; do not start background work or retries after the request.

401/403/429 stop future planned network reads. Return sanitized status and allowlisted numeric rate-limit/reset/retry hints only, never body/header dump, cookies or credentials. 404 is unavailable/visibility-ambiguous;3xx is redirect_rejected, not a renamed-user discovery mechanism. No sleeping/retry/rate-limit evasion. With profile success and repo/events failure preserve the successful independent section and label the other section partial/unverifiable, not empty.

These are **proposed limits, not enforced runtime guarantees**. They require handler/HTTP tests. JSON bytes, output bytes and actual model/host billing are separate measurements (#77).

## Report semantics

Top level: design/versioned report schema, requested identity, observation time, independent profile/repos/activity sections, sources, coverage, budget and limitations. No file SHA is invented for live profile/list metadata: source URL + exact query + fetched_at describe a non-atomic observation, not a commit-pinned snapshot.

Repository rows: stable ID, constructed GitHub URL, full_name, description only with include_text, primary language or null, stars/forks integer or null, timestamps, size_kb_reported, fork/archived flags and source index. Zero is retained, unknown is null with a field state; booleans/negative counts are invalid. Do not use `value or fallback` for counters. The default list includes zero-star, forked and archived repositories. It is not a list of every repo the author contributes to. No watchers/subscriber ambiguity or issue-vs-PR inference is introduced.

Bound text before formatting: profile prose<=250 chars/field, repo description<=160, topics<=5×50 if later enabled, repository identifiers<=200. Drop unselected raw fields, event payload/commit messages and unknown headers. Escaping/filters are not semantic prompt-injection sanitization. Unexpected private rows or foreign/invalid identities must never be reflected; record exclusions/partial state without sensitive identifiers. Stable-ID dedup is within the observed page, not a persistent cross-call history.

### Repository pagination and coverage

Expose requested_page/per_page, raw_received, returned, duplicate/invalid/private exclusions, has_more (true/false/null), next_page (validated integer or null), stop_reason, profile public_repos hint, and complete_account_inventory=false. `public_repos` is a separately timed profile count, **not the total for this query or proof of complete enumeration**. No all-GitHub total.

Parse only the expected fixed-origin/path next-page relation and validate page/page-size; reconstruct the next request from allowlisted arguments. Never request a Link URL directly. A malformed/external/ambiguous Link makes continuation unknown. No Link on a full page is not automatically proof of exhaustion. A short valid page without a next relation can establish observed listing exhaustion, not an immutable account inventory. Source changes between pages can cause repeats/omissions; disclose that even with full_name sorting. No exactly-once or atomic snapshot promise.

Output overflow must return a small partial/output_budget result, with no advanced page cursor. Never silently drop the tail and advance to the next page. No automatic field expansion/traversal on retry.

### Language denominator

Mode is **primary_language_by_returned_repository_count**, not code bytes, proficiency or all-account languages. Return all_returned_repos, known_language_repos, unknown_language_repos and integer counts. Sum(counts)=known_language_repos; known+unknown=all_returned. The primary percentage denominator, if rendered, is explicitly known_language_repos, with unknown count shown separately. Empty/unknown-only samples have no percentage. Fork/archive rows stay in the default denominator; do not silently change it or normalize away missing data. Use existing single-repo Languages API only in an explicitly separate workflow.

### Public events

Deduplicate observed event IDs, validate UTC timestamps, filter by reference-time window; reject future/malformed timestamps from counts and record exclusions. Return counts by event type and a bounded repo breakdown with remainder, source/page, oldest/newest observed times, filtered/unknown counts, next_page and provider cap/retention/delay caveats. Do not return arbitrary raw payloads. Empty/denied public events do not establish inactivity, private activity or a zero contribution graph. PushEvent count is not commit count. Even an exhausted timeline has complete_window=false.

## Design examples and tests: exact boundary

The14 checked-in examples are **hand-authored synthetic expected reports**, not handler outputs or live results. Artifact tests check their zero/null/denominator/source/continuation consistency and distinguish the historical full proposal from the phase1 runtime schema. They do not prove transport enforcement, pagination, cancellation, parsing or runtime behavior. The original handler matrix is retained for traceability; its phase1 coverage map distinguishes covered mock cases, documented-only limitations and deferred Events cases. The full #99 acceptance is still open.

Next implementation gate: validate the version-pinned provider contract; then regression-first fake transport and MCP HTTP tests, runtime/schema/doc discovery, output/budget safety and one permitted public live smoke. Compare one composition against existing primitives with catalog+args+results, equal coverage and parallel-call bounds; do not assume fewer tool names/calls means fewer model turns or credits. No current cost savings or new registered tools are claimed.
