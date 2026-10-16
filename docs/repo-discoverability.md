# Read-only repository discoverability audit (#103)

`audit_repo_seo(owner, repo, project_type="unknown", allow_private=false, max_requests=10)` is one bounded evidence collector, not an SEO score or adoption predictor. No duplicate `audit_my_repo` wrapper has been added. This candidate is separate from #91 and is **not deployed** merely because its schema exists in a feature branch.

## Example

```json
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"audit_repo_seo","arguments":{"owner":"LeonidYasin","repo":"mcp-server","project_type":"mcp"}}}
```

The MCP dispatcher still requires the existing Bearer gate for this GitHub-category tool. **Default outbound requests are anonymous**: it does not forward that credential to GitHub. Explicit `allow_private=true` uses the current request's credential only on fixed `https://api.github.com` GET endpoints. It neither discovers nor chooses credentials. Do not broaden token permissions for this audit. A public repository that cannot be read anonymously yields unavailable/partial, not a hidden authenticated fallback.

`project_type` is an explicit user declaration: unknown, mcp, library, cli, web, android. It is not inferred from programming language. Android distribution is not applicable to a declared non-Android project; Android/unknown eligibility remains unverified.

## Evidence / states

The JSON text inside MCP content has schema_version=1, outcome, snapshot, checks, prioritized actions, review-only suggestions, sources, limitations and budget. A check references a zero-based `source` index; package checks additionally list `manifest_sources`. Sources carry fixed API URL, fetched_at, HTTP status, request ref where applicable, and verified-format blob SHA for decoded files. Repo snapshot contains requested identity, explicit type, private flag, scope=root_only and resolved commit SHA.

- `present`: observed metadata or content/heading heuristic, **not** proof of usefulness, legality, working install or publication.
- `missing`: an observed metadata field is empty/false, or an expected heading pattern was not found. Heading absence is a heuristic; linked docs can satisfy the real need. It is not proof the capability is absent.
- `unverifiable`: no sufficient evidence, unsupported/oversized content, failed/forbidden read, unknown publication or HTTP state. A 404 is not treated as definitive absence (permissions and endpoint semantics differ).
- `not_applicable`: no supported root manifests in a complete small listing, or an explicitly declared non-Android type for APK catalogs. Nested packages are not audited.

`completed` means the bounded observation pass completed with a pinned README; it does **not** mean every check was verified or every recommendation accepted. `partial` means a required snapshot/README or request/time/response budget was unavailable; individual unknown checks can also exist in a completed pass. Root API listings at the 1000-entry ceiling are not considered complete. Malformed entries, invalid root paths/types and duplicate names also prevent conclusions about package absence; candidate manifest responses must match the requested root path as well as the listed blob SHA. Metadata is observed at request time, not an atomic GitHub-wide snapshot. README/root manifests are pinned to resolved default-branch commit. No cache exists.

## What is checked

- Description/homepage/topics/license identity and disabled Issues from repository metadata. Null/unrecognized SPDX is not a legal conclusion; no license is selected automatically.
- Preferred README at pinned ref. UTF-8, base64 and declared byte size are validated. Heading heuristics cover problem/why, quick start, limitations and examples/image markup (Markdown and basic Setext/RST headings). Source prose/commands/links are never executed or followed. Bounded static package descriptions can be copied as explicitly untrusted, review-only About drafts (see below).
- Up to two root `pyproject.toml` / `package.json` manifests. Static name/description/keywords only, no build, install, dynamic metadata resolution, package registry query or dependency execution. Symlinks/submodules/invalid TOML/JSON are not traversed. Monorepo/nested metadata remains outside scope.
- Latest stable release metadata (not arbitrary prereleases or proof of verified/installable assets).
- Pages GET configuration only when not already reported disabled. Built/building/errored are configuration/build observations, **not HTTP reachability**. The audit never requests a homepage/custom domain or enables Pages (#68).
- Social preview, search-engine indexing and registry publication remain unverifiable; a README image, `has_pages`, tag, or language is not a substitute.

Actions and all suggestions require maintainer review. About.description drafts copy a bounded (3–250 characters), printable static manifest description with exact source index/field, not inferred features. Obvious secrets, URLs, markup and instruction-like strings are rejected as defense in depth; this is not a semantic prompt-injection sanitizer. Each copy is marked untrusted_source_text=true and requires_review=true. Topic candidates are at most six distinct allowlisted, explicitly declared static keywords, excluding current topics; no keywords are invented from language, project_type or arbitrary README prose. Dynamic/invalid/unknown metadata may yield no drafts. Blank package names, malformed static fields or dynamic declarations, and parser-depth failures are unverifiable and yield no manifest-derived copy; blank-only keyword lists are missing, not present. No draft claims package publication or verified functionality. Image generation, competitor comparison and publishing workflows remain follow-ups (#100/#104). There is no automatic write, PR, publication, paid service, crawler or external contact. Other projects' settings are unchanged.

## Hard bounds and safety

At most 10 fixed-host GETs (max_requests 2–10), one attempt each; per-response retained JSON <=256 KiB, total response budget 1 MiB (the triggering 8 KiB chunk can cross a read limit and is rejected; further reads stop after total-budget exhaustion), README/manifest <=64 KiB decoded, per-request timeout <=5s within a 20s observation deadline checked between chunks/requests. Socket blocking can overrun the deadline by up to the active read timeout; this is not hard real-time cancellation. Content-Encoding other than identity is rejected to avoid decompression expansion. Redirects are rejected even back to GitHub (renamed repo requires an explicit new identity).

403/401/429 stop remaining network reads; no retry/rate-limit evasion. HTTP failure bodies and arbitrary external URLs are not returned; static package description copies are separately marked untrusted review data; error codes are fixed/redacted. No persistent credential, response cache or cross-owner storage. Unknown/missing data is not converted to zero stars or a judgement that a project is dead. Budget is not an authorization boundary or a promise that every MCP host saves tokens.

## Validation

`tests/test_repo_discoverability.py` covers fixed-host GET-only transport, no default Authorization, private opt-in/refusal, invalid arguments, redirection/refusal/429, byte/time/request budgets, malformed content, unknown types, unavailable README, monorepo limits, dynamic metadata, redaction and real Flask MCP dispatch/schema discovery. Public live smoke evidence is recorded separately in the PR/issue; no private live audit or deployed acceptance is implied.

GitHub API references: [repository README](https://docs.github.com/en/rest/repos/contents#get-a-repository-readme), [root contents](https://docs.github.com/en/rest/repos/contents#get-repository-content), [Pages configuration](https://docs.github.com/en/rest/pages/pages#get-a-github-pages-site). Provider behavior/permissions may change; refusal remains unknown, not guessed.

## Public live smoke evidence (candidate only; dated observations)

- [mcp-server report](examples/repo-audit-mcp-server.json): 7 anonymous GETs, pinned `0c12a3753efe749c4f16b751da569f4461d83a15`, completed observation pass. Pages unavailable via anonymous API remains unverifiable, not absent.
- [Flask library report](examples/repo-audit-flask.json): 6 anonymous GETs, pinned `d086db856be187255b8ec61ef409357393020f32`, completed observation pass. README section signals are heuristics, not claims that Flask lacks usage documentation.

Initial mcp-server smoke returned partial because README exceeded the first 32 KiB design cap; that honest result led to a reviewed increase to 64 KiB, with unchanged 256 KiB response / 1 MiB total limits. The earlier successful smoke above used the current cap and the initial PR implementation; it is historical evidence, not a successful rerun of the follow-up code.

The follow-up rerun was refused by the anonymous GitHub API: [mcp-server refusal report](examples/repo-audit-mcp-server-refused.json) is partial after 3 GETs (403 followed by stopped reads); [Flask refusal report](examples/repo-audit-flask-refused.json) is unavailable after 1 GET (403). No retry, authenticated fallback or successful live acceptance is claimed. Source-backed draft behavior in this follow-up is covered by deterministic tests, not these denied live reads.

No private audit, external website request, package install from audited repos or deployed MCP test occurred. Reports are dated observations, not permanent evaluations.

## Quality and cost follow-up

Regression review found/fixed whitespace-only metadata, code-fence/comment false signals and further requests after total-byte budget exhaustion. Nested/longer/unclosed fences and HTML comments no longer provide README heading signals. Absence of a heading still does not prove absence of functionality or linked documentation.

[Offline token-accounting experiment](repo-audit-benchmark.md) includes full catalog, args, results, parallel/sequential response-round bounds and a batched legacy alternative. It is not actual host billing or an equal-evidence savings claim; #77 stays open. The formatter does not replace missing or denied evidence with invented drafts.

## Cross-candidate integration check

[Local compatibility review with Draft #91](pr-91-107-compatibility.md) records pinned inputs, six documentation/inventory conflicts, a detached resolved-tree test and registry profiles. This does not import uploads, resolve remote branches, change deployment, or complete either candidate acceptance.
