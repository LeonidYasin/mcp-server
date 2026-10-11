# update_pull_request: verified draft / ready transitions

`owner`, `repo`, and positive integer `number` remain required. Only supplied
non-null fields are operated on. `draft` must be a literal boolean; strings
such as "false", integers and containers are refused before API calls. Null
means omitted, not ready. Existing missing owner/repo/number diagnostics remain.

```json
{"owner":"OWNER","repo":"REPO","number":123,"draft":false}
```

This makes a draft ready for review. `draft:true` requests the reverse transition.
Use the intended PR only; neither operation merges it or changes its branch.

## Correct API and verification

REST PATCH /pulls/{number} is not used to change draft state. Draft-only calls:

1. GET the PR and validate its number, literal draft/merged booleans and state.
   Closed or merged PRs are rejected before any write, even in mixed requests.
2. If already in the desired state, return no_op with the observed draft value;
   no GraphQL mutation, PATCH, reviewer request or repeated transition is issued.
3. Otherwise obtain node_id from that PR. Pass it as a GraphQL **variable**, never
   interpolate it into a query. Missing/invalid identity prevents all writes.
4. POST /graphql with convertPullRequestToDraft or
   markPullRequestReadyForReview; select id/number/isDraft/state.
5. Check HTTP/JSON/GraphQL errors, and require the returned identity, OPEN state
   and requested isDraft. HTTP 200 or an arbitrary data object is not success.
6. Independently GET the same REST PR after the mutation attempt, including after
   GraphQL errors/timeouts. Check node_id/number, open/unmerged and actual draft.
7. Only matching, error-free GraphQL data **and** matching REST read-back confirm
   draft_outcome=applied. No mutation retries, REST fallback or implicit merge.

GraphQL permission errors, partial data, malformed success or an unchanged REST
state never produce a full-success claim. A transport timeout may still have
changed the PR: report the observed state and uncertainty, then inspect before
another write. The API calls are not atomic and read-back can observe another
actor's concurrent change; observations do not provide a locking guarantee.

## Structured result

Text retains a concise status heading and adds one JSON `metadata: ` line:

- `outcome`: updated, no_op, rejected, invalid_input, unconfirmed or partial;
- `requested_draft`: requested boolean, or null if omitted;
- `actual_draft`: independently observed boolean, or null if unavailable;
- `draft_outcome`: applied, no_op, rejected, unconfirmed, or null if omitted;
- `draft_applied`: true only for confirmed transition; false for a no-op/rejection;
  null when attribution/result cannot be confirmed. False on a no-op does not
  mean the target state is wrong; actual_draft states what was observed;
- `changes`: acknowledged ordinary REST fields, confirmed draft, or accepted
  explicit reviewer request. Empty on a draft-only no-op;
- `error`: bounded generated reason, not raw API exception/GraphQL error text.

GraphQL errors with unchanged read-back are rejected. Errors with target state
observed are unconfirmed (do not claim our mutation caused that state).
Read-back mismatch, changed identity, closed/merged state or read failure is
unconfirmed even when GraphQL reported success.

## Mixed requests and compatibility

Supported ordinary fields remain title/body/state/base; they are sent only in a
REST PATCH and **never include draft**. Explicit reviewers are requested via the
existing requested_reviewers endpoint. Draft-only never changes title/body/base
or sends reviewer requests. GitHub itself may emit notifications/request code-owner
reviews when a PR becomes ready; that normal platform behavior is not suppressed.

Mixed requests validate all inputs and draft preconditions before any write, then
run ordinary PATCH, draft transition, explicit reviewer request in that order.
Operations are not transactional. If ordinary fields were acknowledged but draft
fails, return partial with those changes retained; do not roll back automatically.
Reviewers are not requested after an uncertain/rejected draft transition.
The combination draft + state=closed is rejected before API calls. Reopening a
closed PR and changing draft requires separate deliberate calls.

The ordinary REST/reviewer paths record API acknowledgement; unlike draft they do
not add independent read-back verification in this scoped change. Their failures
are reported as unconfirmed/partial without reflecting raw exception bodies.
Legacy comma-separated reviewer strings remain accepted; empty lists are no-ops,
not instructions to remove reviewers. The successful heading is retained, but
consumers requiring exact whole-text equality must account for appended metadata.

## Tests and live gate

Fixtures cover both directions, no-op, closed/merged/unknown state, variable-safe
node IDs, permission/partial GraphQL data, malformed identities, contradictory
inputs, read-back mismatch/failure, mixed partial operations, no retries and Flask
MCP transport. Live acceptance requires both transitions and idempotent repetition
on an explicitly authorized disposable PR. Fixture passes are not presented as
proof of live GraphQL permissions. Do not test on an unrelated user's PR or merge
a fixture into main. Production rollout is separate.
