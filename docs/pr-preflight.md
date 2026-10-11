# Pull request metadata and guarded merge

## Read-only get_pull_request

`owner`, `repo`, `number` are required. The tool performs GET PR and a best-effort
GET repository to discover merge-method flags. Output remains text with a single
JSON `metadata: ` line containing:

- full `head.sha` / `base.sha`, refs and repository names;
- `state`, `merged`, `draft`, tri-state `mergeable`, `mergeable_state`;
- `merge_commit_sha`, created/updated/closed/merged timestamps, `html_url`;
- author, additions/deletions/changed-files and bounded body in the text output;
- `merge_method_flags` for merge/squash/rebase, `allowed_merge_methods`,
  `merge_methods_complete`, `merge_methods_error`;
- `merge_eligibility=not_evaluated`: metadata is evidence, not permission to merge.

Unknown booleans are null, not false. An unavailable method flag is null, never
assumed allowed. A repository-read failure does not erase successfully read PR
metadata. Closed/unmerged differs from merged. Before merge, `merge_commit_sha`
may be GitHub's temporary test-merge SHA, **not** an already landed commit.
After merge its meaning depends on merge/squash/rebase.

## merge_pull_request: intentional safety change

Every call now requires a full 40-hex `expected_head_sha`, in addition to owner,
repo and a positive integer number. Legacy unguarded calls are refused before
any requests. The JSON schema advertises this requirement. Omitted/null original
owner/repo/number diagnostics are retained for malformed older clients.

```json
{
  "owner": "LeonidYasin", "repo": "mcp-server", "number": 74,
  "expected_head_sha": "0123456789abcdef0123456789abcdef01234567",
  "merge_method": "squash", "commit_title": "Reviewed change",
  "commit_message": "Verification recorded in the PR."
}
```

The SHA/PR number above are placeholders, not a command to merge an actual PR.
Read and review the real HEAD first. Supplying a SHA does not substitute for
human authorization. Valid methods are merge/squash/rebase; default is merge.
The tool never silently changes a forbidden method to squash or another method.
Optional title/message must be strings of at most 10,000 characters; only supplied
fields are sent (empty strings are preserved).

### Preflight and write sequence

1. Validate inputs without network requests.
2. GET PR: compare HEAD to expected SHA. A mismatch gives `head_conflict` with
   `http_status=409` **without sending PUT** (this is a local outcome, not a
   claim that GitHub received a conflicting write).
3. Refuse closed/unmerged, draft, unknown draft/state/mergeability, conflicts,
   or a mergeable_state other than clean/has_hooks. Null is not clean.
   Already-merged PRs are reported read-only, with confirmed merge SHA if present.
4. GET repository: selected method must be explicitly allowed. False means
   method_not_allowed, unknown means policy_unknown. No guessing or fallback.
5. Read `get_commit_status` for exactly the expected HEAD. Both sources must be
   complete and the aggregate success or no_checks. Failure/pending/unknown,
   malformed data or a foreign SHA prevent PUT.
6. GET PR again after checks. Re-check HEAD and state/draft/mergeability; a push
   during preflight prevents the write. No automatic polling to wait for clean.
7. Send **one** PUT /pulls/{n}/merge with `sha=expected_head_sha`, selected method,
   and only supplied commit_title/commit_message. GitHub's SHA guard protects the
   final interval between the last read and the write. No automatic retry.

`no_checks` is explicitly retained as no_checks, not fabricated success; it can
proceed to the guarded API. This is not proof that required checks are configured
or satisfied. Neutral/skipped follow get_commit_status's documented non-blocking
policy. Branch protection/rules, approvals, merge queues, required contexts and
permissions remain GitHub's responsibility; no bypass flags or settings edits
are made by this tool. Authorization privileges still affect server enforcement.

### Structured outcomes

The JSON metadata contains outcome/merged/sha/message, expected_head_sha,
merge_method and available preflight evidence (head_sha, method flags, checks).

- `merged`: GitHub returned literal merged=true with a valid full SHA.
- `already_merged`: read-only observation with a valid existing merge SHA.
- Input/preflight refusal: invalid_input, head_conflict, closed, draft,
  preflight_unknown, mergeability_unknown, not_mergeable, method_not_allowed,
  policy_unknown or checks_not_ready; no PUT issued.
- GitHub merged=false or an explicit HTTP 401/403/404/405/422 refusal: rejected.
  Explicit HTTP 409: head_conflict. Never retry with a new method/SHA automatically.
- Timeout/transport/5xx/JSON errors or malformed success response: unconfirmed,
  merged=null, sha=null. The write may have succeeded: inspect PR before another
  request. Do not interpret this as safe permission to repeat a mutation.

An operation refusal's merged=false is not a complete current PR-state snapshot.
Only merged/already_merged positively confirm a merge SHA. Messages are bounded,
common token patterns redacted, and raw exception bodies never reflected.

## Limitations and verification

Preflight reads are not atomic. Checks, policy, base branch and review state can
change after reading; the SHA guard covers the **head**, not base SHA or every
policy fact. The tool does not provide asynchronous merge, auto-merge, queue
support, force, protection override, or universal proof of merge eligibility.
The safe response to an unknown/unconfirmed outcome is inspection, not retries.

Regression tests cover metadata, tri-state, HEAD races, method policy, checks,
closed vs merged, exact PUT payload, errors and Flask MCP transport. Successful
PUT is fixture-tested unless a PR verification comment records an explicitly
authorized live disposable merge. Production rollout is separate from code merge.
