# download_artifact: resolved, sensitive download capability

The metadata field archive_download_url is an authenticated GitHub **API endpoint**,
not a signed ZIP URL. This tool now reads artifact metadata, then makes an
authenticated request to the fixed GitHub /actions/artifacts/{id}/zip endpoint
with redirect following explicitly disabled. Only HTTP 302 with a validated
Location produces outcome=resolved. No downstream CDN request is made.

```json
{"owner":"OWNER","repo":"REPO","artifact_id":123}
```

Or locate a unique exact name within a specific workflow run:

```json
{"owner":"OWNER","repo":"REPO","name":"dist-3.13","run_id":456,"max_pages":5}
```

IDs are positive integers (booleans are not integers here). artifact_id takes
precedence over name. Name lookup now requires run_id: the old implicit
repository-wide/first-match search is intentionally refused. Exact-name lookup
fetches up to max_pages (integer 1–20, default 5), 100 entries per page. Pagination
uses only the fixed endpoint and page numbers, never arbitrary Link URLs.
Changed/malformed totals, duplicates, empty pages before the end or API failures
prevent resolution. A cap yields lookup_incomplete, never an assumed unique match.
Duplicate names yield ambiguous with at most 20 candidate IDs; select the exact
artifact_id rather than guessing. Run identity is checked when run_id is supplied.

## Redirect and credential boundary

- Destination metadata URLs are never fetched or trusted. The redirect must come
  from the authenticated fixed GitHub API request, not a caller-supplied URL.
- HTTPS only, port absent/443; no userinfo, fragment, backslash, whitespace/control
  characters or oversized URL (maximum 16 KiB).
- Narrow delivery-host family allowlist: objects.githubusercontent.com,
  subdomains of actions.githubusercontent.com, and numeric
  productionresultssaN.blob.core.windows.net hosts. Generic Azure tenant domains,
  lookalike suffixes, API URLs, arbitrary hosts and IP destinations are rejected.
- The Azure naming pattern alone is not a universal proof of account ownership:
  provenance from the authenticated GitHub API is essential. No redirect from
  metadata/user input is accepted, and the server never contacts the destination.
  Unknown delivery families fail closed; review upstream changes rather than
  broadening to arbitrary *.blob.core.windows.net.
- The GitHub PAT is sent only to the fixed API endpoint, never to a CDN. If our
  literal PAT is reflected in Location, reject it without returning that URL.
- Use a streaming response context: inspect status/headers only, never load a
  ZIP or error body into memory. Close the API response afterward.
- HTTP 200 inline content and other redirect statuses are unsupported, not falsely
  resolved. 401/403/404/410/429 are reported by status without raw bodies;
  transport failures are unknown with generated diagnostic text. No hidden retry.

## Output and freshness

MCP text has a short outcome heading and one JSON metadata line, avoiding duplicate
URL/prose output. Outcomes include resolved, expired, not_found, ambiguous,
lookup_incomplete, invalid_input, unknown, redirect_rejected, api_refused and
unexpected_response. Failed outcomes never return an API URL as a download link.

A resolved result includes artifact_id/name/size_in_bytes/created_at/expired,
artifact_expires_at, lookup_complete, http_status=302, download_url,
requires_github_authorization=false and sensitive_download_url=true.

**The download_url itself is a short-lived bearer capability.** Fetch it promptly
without adding GitHub Authorization/PAT. Do not post it in issues/docs, persist it
in diagnostic logs, or forward it unnecessarily. GitHub documents a short expiry
for its redirect; this tool does not invent an exact timestamp or parse/rewrite
opaque signed query parameters. url_expires_at remains null unless an exact
upstream expiry is explicitly supported. artifact_expires_at is retention expiry,
**not** link expiry. An unexpired artifact does not prove its prior link is fresh.

The resolver does not print Location/error bodies; ordinary HTTP logs contain
only the fixed API URL. External verbose tracing and MCP hosts can retain tool
results, including the intentionally returned capability: this server cannot
promise universal host-side redaction. Avoid debug header/body dumps. The URL is
opaque, issuer-provided; the tool does not cryptographically validate its signature.

## Verification

Tests use real httpx MockTransport with follow_redirects=True globally to prove
this endpoint overrides it, issues one API request, never contacts a CDN and does
not consume bodies. Metadata/name pagination, ambiguity, expired artifacts,
unsafe redirects, refusal/transport errors, PAT redaction and Flask MCP schema
are fixture-tested. Actual authenticated API redirect resolution and live TEST
runtime read-back remain explicit PR gates; mocked URLs are not live evidence.
No artifact deletion, workflow reruns, repository setting edits or production
rollout are part of this tool.
