# Batch push: modes and concurrency

`push_multiple_files` creates one commit containing the supplied UTF-8 text
files. Existing blob modes are preserved by default:

| Mode | Meaning |
| --- | --- |
| `100644` | Ordinary file; default for a new path |
| `100755` | Executable file |
| `120000` | Symlink; content is the new link target, not the target file |

Each item accepts `{path, content, mode?}`. Explicit mode overrides are limited
to those three values. Existing directory/submodule/unsupported entries and
non-directory ancestors are refused rather than implicitly converted. Paths
must be normalized relative POSIX paths; duplicates and file/directory conflicts
within the batch fail before any request. Backslashes, NUL, absolute paths,
empty components, `.` and `..` components are not accepted.

## Single tree read

For an existing branch, one recursive Git Trees read obtains modes for all
paths. `base_tree` preserves untouched entries; only selected files get new
blobs. Truncated trees, missing completeness metadata and malformed entries
fail before blob creation: missing entries in a partial tree are not safely
assumed to be new ordinary files. This tool does not use per-file Contents reads
or silently fall back to guessed modes for large trees.

## Expected HEAD and final update

Optional `expected_head_sha` must be a full 40-character hexadecimal SHA.
Case is normalized. A mismatch with the initial HEAD returns a conflict before
any write. Without the option, the initial HEAD is still the operation's snapshot.

The commit parent and base tree use that snapshot. HEAD is read again before
updating the ref; a changed HEAD returns conflict without a PATCH. GitHub receives
`force=false`, so normal concurrent forward commits are not overwritten; a
fast-forward rejection is reported as conflict. The successful ref response
must confirm the exact new commit SHA, not merely return HTTP success.

**This is not an atomic compare-and-swap or a transaction.** GitHub REST ref
updates do not provide an expected-old-SHA CAS here. There is a narrow gap between
the final read and PATCH; an external rewind to an ancestor can make a non-force
update eligible despite the changed intermediate HEAD. Do not promise strict
serializability. Branch protection and permissions are not bypassed.

Blobs/tree/commit objects may already exist if a late conflict occurs. These
unreferenced objects are not changes to the branch and are not deleted by this
tool. A ref update transport failure can have an uncertain outcome; check the
ref before retrying rather than automatically repeating a write.

## Empty repository behavior

Bootstrap is retained only for an explicit `409: Git Repository is empty` on
initial ref lookup: no base tree/parent, then POST a new ref. An expected nonempty
HEAD against an empty repository conflicts without writes. A concurrent ref
creation is rejected instead of overwriting it.

An ambiguous 404 is **not** proof of an empty repository: it can mean a missing
branch or missing permission. Such errors, and commit/tree lookup failures, no
longer trigger implicit bootstrap. Create an intended missing branch explicitly.
This is a deliberate safety change from the previous broad 404 fallback.

## Result contract

The result remains MCP text, followed by a machine-readable `metadata: {JSON}`
line containing `outcome`, `expected_head_sha`, `base_head_sha`,
`observed_head_sha`, `new_commit_sha` and `file_count`.

- `applied`: GitHub's ref response confirmed the candidate SHA; another actor can
  still advance the branch later. This is not a guarantee of the current HEAD.
- `conflict`: initial/final HEAD mismatch or a recognized ref conflict; do not
  force-push as a workaround. With a late conflict, unreferenced objects can exist.
- `unconfirmed`: ref response/transport did not establish the update; no success
  claim or automatic mutation retry. Other validation/read/API failures can
  propagate as ordinary MCP errors before the ref-update phase.

## Testing boundary

Regression tests use mocked GitHub requests for modes, complete-tree policy,
expected SHA, concurrent update and response/error handling. A native local bare
Git fixture verifies actual tree modes, link-target blobs, untouched entries and
one-commit parenting through an API-shaped adapter. It is not a live GitHub API
or production test, and its local `git update-ref` CAS must not be mistaken for
an atomic CAS guarantee of GitHub REST.

Any live write validation should use only an explicitly designated disposable
branch/repository, with a recorded initial SHA and no changes to workflows,
secrets, production branches or permissions.
