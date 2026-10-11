# Bounded branch comparison

`compare_branches` returns text, with a machine-readable JSON line prefixed by
`metadata: `. It remains a read-only tool. No branch, tag or PR is modified.

## Arguments

| Argument | Default | Allowed | Meaning |
| --- | --- | --- | --- |
| `max_files` | 10 | integer 0–300 | Same limit for file summaries and patches; 0 is metadata-only |
| `include_patch` | false | boolean | Include patches for selected files |
| `max_patch_bytes` | 65536 | integer 0–262144 | Global UTF-8 byte budget, including diff headers/newlines |
| `max_patch_lines` | 1000 | integer 0–5000 | Global line budget, including diff headers |

Invalid limits (including booleans, fractional numbers, strings and null) fail
before any API request. Limits are not silently clamped. Patch limits apply to
the patch section only; status, metadata and bounded file summaries are outside
that budget. A truncated patch may end in the middle of a line, but never inside
a UTF-8 character; do not treat it as an apply-ready diff.

## Comparison semantics and snapshot

This uses GitHub's **three-dot** `base...head` comparison: changes introduced by
head since the merge base. It is **not** a two-tree comparison of base and head.
After squash merges, `ahead_by` does not establish that a branch adds new features.

Both refs are resolved via read-only `GET /repos/{owner}/{repo}/commits/{ref}`;
then the compare request uses those immutable SHAs. This adds two reads and
prevents head SHA from being guessed from a truncated commits list. The two refs
are resolved sequentially, not as an atomic snapshot of all repository refs.

## Metadata contract

- `base_sha`, `head_sha`, `merge_base_sha`: exact compared revisions; missing
  upstream merge-base metadata is null, never fabricated.
- `total_files`: exact count only when completeness is confirmed; otherwise
  null. `fetched_files` is the count actually received, `returned_files` is the
  count selected by the local limit.
- `truncated`: true if the local limit omits files **or** upstream completeness
  is not established. It is conservative, not proof that additional files exist.
- `upstream_files_complete`: false at GitHub's 300-file cap (even if there happen
  to be exactly 300 changes), or if the files field is absent. Compare provides
  no reliable total beyond that cap; do not advertise fetched count as full total.
- `total_commits`, `fetched_commits`, `upstream_commits_complete`: API total,
  received commits, and completeness. A next-page link or a mismatch means the
  received commits are not a confirmed complete set. This tool does not fetch
  further pages or print full commit lists.
- With `include_patch=true`: `patch_bytes`, `patch_lines`, `patch_truncated`,
  `patch_unavailable_files`, `patch_complete`. Budgets are global, not per-file.
  Missing/binary/omitted patches among selected files are counted as unavailable.
  `patch_complete` is false for missing patches, budget clipping or incomplete
  file selection. `patch_truncated` specifically describes local budget clipping.
  GitHub may shorten an individual patch without explicit completeness metadata;
  `patch_complete` covers the returned payload, **not** a verified full Git diff.

Example:

```text
compare_branches(owner="LeonidYasin", repo="mcp-server", base="main",
                 head="feature/example", max_files=5, include_patch=true,
                 max_patch_bytes=8192, max_patch_lines=100)
```

Existing callers still receive a text response, but the default summary now
honours the documented default of 10 files rather than the old hard-coded 30.
For larger summaries, explicitly set `max_files` (up to 300).
