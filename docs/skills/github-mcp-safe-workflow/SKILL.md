---
name: github-mcp-safe-workflow
description: Use this Skill for every GitHub-related task on the mcp-server repository (LeonidYasin/mcp-server) or any external repo. Activate it whenever the request touches a GitHub repository — creating or updating files, opening or merging pull requests, comparing branches, running or debugging GitHub Actions, reviewing diffs, diagnosing failed builds. It enforces the correct use of the 109 MCP tools, prevents silently-lost tool calls, requires verification against real repository state, stops repeating known mistakes (branch hygiene, read-before-write, architectural drift), and reads long-term memory on every activation so new lessons apply automatically.
memoryEnabled: true
---

# GitHub MCP Safe Workflow

You are operating with a custom MCP server that exposes ~109 GitHub tools. These tools work, but they are easy to misuse in ways that silently fail. This Skill encodes hard-won rules. Follow every rule below; do not improvise.

## Rule 0 — Read memory before acting

Before starting any GitHub task, scan loaded memory entries for notes tagged `github`, `mcp-server`, `pr`, `branch`, `ci`, or `workflow`. These notes contain the latest feedback from the user and **override any conflicting rule below**. When a new note contradicts a rule in this Skill, follow the note and explicitly mention the conflict in your reply. Never silently ignore either the note or the Skill rule.

## Rule 1 — Always use the FULL prefixed tag name

NEVER call a tool with a short tag like `<create_or_update_file>`. The plugin routes only fully-prefixed tags, e.g. `<mcp_t_550b42a7_3184_4979_bfd3_1054d43d55be_create_or_update_file>`. Short tags are silently dropped: the call appears in the transcript but the tool never runs, and you will see results from a neighbouring call instead.

## Rule 2 — Verify against repository state, never trust the fact of a call

After any write operation (`create_or_update_file`, `push_multiple_files`, `move_file`, `delete_file`, PR creation, merge), immediately verify the result by reading the repository back:

- After pushing files → `compare_branches(base, head)` — `ahead_by` must increase by the expected count.
- After updating a specific file → `grep_file(path, unique_marker)` — the new content must appear.
- After creating a PR → `get_pull_request(number)` — the PR must exist with the expected head/base.

If verification fails, treat the operation as failed and retry with the full-prefixed tag. Do NOT conclude "it worked" from the tool call being present in the transcript.

## Rule 3 — Read before write; prefer `_with_sha` for updates

Before updating any existing file, obtain the current content and SHA — not just to satisfy the API but to **see what is actually there** before overwriting it. This prevents clobbering concurrent edits, silently reverting recently added code, or replacing a file that has changed since your last read.

Two valid paths:
1. **`get_file_contents` → `create_or_update_file_with_sha`** (preferred): read the file, verify what you are about to replace, then call the updater. `_with_sha` re-fetches the SHA internally, so you do not need a separate `get_file_sha`.
2. **`get_file_sha` + `create_or_update_file`** (fallback): if you already fetched the SHA via the dedicated tool, pass it explicitly.

For NEW files, `sha` must be omitted — send nothing, not an empty string.

Never update a file you have not read in this session.

## Rule 4 — Branch hygiene: never reuse a merged branch

When working with pull requests:
1. Create a NEW branch from the CURRENT `main`: `create_branch(from_branch='main', branch='feat/...')` or `fix/...`.
2. Push the files to that branch.
3. Open a PR: `create_pull_request(title, head=<new branch>, base='main')`.
4. The USER merges the PR. Do NOT merge it yourself unless explicitly told to.
5. Only after the merge is confirmed via `get_pull_request` (state=closed, merged=true) start the next task from a fresh branch off updated `main`.

NEVER push follow-up commits into an already-merged branch. If a bug is found in merged code, open a separate `fix/*` branch off `main`.

## Rule 5 — One failed request is not proof

A single 404 or empty response is NOT evidence that a path, branch, or file does not exist. Before concluding anything about repository structure:

1. If the user named a path, check exactly that path first with an explicit `ref`.
2. If the result is partial or contradictory, use `get_repo_tree(recursive=1)` to dump the whole tree before making claims.
3. Do NOT conflate distinct directories just because one exists and another 404s — they may coexist.
4. Confirm both the path AND the `ref` (branch/tag/commit) before saying "not found".

The correct tool for structure discovery is `get_repo_tree`, not repeated `list_directory` calls.

## Rule 6 — CI debugging: use the narrow tools, not the full dump

When a GitHub Actions run fails:

1. `get_workflow_run_status(owner, repo, run_id)` — first, to see which jobs and steps failed.
2. `get_workflow_run_logs(owner, repo, run_id)` with `grep_pattern` (e.g. `'e: file|Unresolved|error:|Caused by'`) and `tail_lines=0` — returns only matching lines.
3. `get_run_logs_by_step(step_name, direction='tail')` for the end of the failing step.
4. `read_run_logs_offset(offset, limit)` for a specific window in the middle of a log.

Do NOT call `get_full_workflow_logs` on a large run — the answer will be truncated.

For Android/iOS builds specifically, prefer: `get_android_build_error`, `get_ios_build_error`, `auto_fix_build`.

## Rule 7 — Do not touch project architecture without reading it first

The `mcp-server` project has a specific plugin architecture:
- `mcp_server/core/registry.py` discovers tools by importing `mcp_server.tools.<package>` and reading `dir()` of its `__init__.py`.
- Only functions explicitly imported in `<package>/__init__.py` are registered.
- The project uses topic-specific files (`file_ops.py`, `file_sha_ops.py`, `pull_requests.py`, ...) — NOT a single `files.py`.

Before adding or moving any `@mcp_tool` function:
1. Read `mcp_server/core/registry.py`.
2. Read `mcp_server/tools/<package>/__init__.py` to see which files are wired in.
3. Add code to an ALREADY-WIRED topic file.
4. Add the import and `__all__` entry to `<package>/__init__.py`.

NEVER create a parallel file that nobody imports — the tool will not exist even though the file compiles.

## Rule 8 — Architecture and quality proposals for mcp-server

When the task touches `LeonidYasin/mcp-server`, you may (and should) propose improvements aligned with world-class practice:

- **Test-first for tool changes**: any new or changed `@mcp_tool` function gets a small pytest that calls it with a mocked GitHub client and asserts the return shape.
- **Contract tests for tools/list**: a test that calls `list_tools()` and asserts the count and that all names are unique.
- **Idempotency for write tools**: file-update tools must accept (or auto-fetch) SHA; branch-creation must be idempotent.
- **Small, single-purpose modules**: one topic per file.
- **Typed return envelopes**: tools return serialisable dicts or strings, never Python objects the transport cannot serialise.
- **`description` budgets**: keep tool-level `description` short (1-2 sentences); do not shorten parameter descriptions.

When proposing, state: (a) the concrete change, (b) the file path, (c) the test that would prove it, (d) the risk if skipped. Propose as a PR comment or a new issue, not as a silent edit.

## Rule 9 — Pull request review protocol

When reviewing a PR:
1. `get_pull_request(number)` — read title, body, base/head.
2. `compare_branches(base, head, include_patch=true)` — read the diff.
3. `get_review_threads(number, only_unresolved=true)` — read existing review comments before duplicating them.
4. Post findings via `add_pr_comment(number, body)`. Reference file:line. Findings first, summary second.

Do not approve or merge on your own initiative. Report findings and let the user decide.

## Rule 10 — Search before reading the whole file

For large files, use in order:
1. `search_code(query)` — GitHub-wide code search with qualifiers.
2. `grep_file(path, pattern)` — regex search inside one file.
3. `read_file_chunk(path, offset, limit)` — paginated read.
4. `read_full_file(path)` — only if the file is small (< ~24 KB).

NEVER call `get_file_contents` on a large file expecting the full content — the client will truncate it.

## Rule 11 — One MCP call per assistant message

When a task requires several dependent calls (branch → file → PR → verify), issue them **one per assistant message**. Do NOT batch multiple `mcp_t_...` calls in a single reply.

Why: the DeepSeek++ extension processes MCP calls sequentially and may silently drop results when several are emitted together. From the user's perspective the agent then looks like it is looping, because it never receives the data it needs. Correct pattern:

1. Send exactly one `<mcp_t_..._get_branch>` call. Wait for the result.
2. Read the result.
3. Send exactly one `<mcp_t_..._create_branch>` call. Wait for the result.
4. Continue one call at a time.

If you genuinely need two independent pieces of information, still fetch them one per message, in two turns.

## Output conventions

- When you performed write operations, list them with the final SHA of the resulting commit.
- When you verified, state the verification command and the observed result.
- When something failed, quote the exact error string from the tool response.
- Never say "done" before Rule 2 verification has passed.

## How this Skill stays current

This Skill's static rules cover stable patterns. Dynamic lessons from real sessions are stored in **long-term memory**, not in this file. When you learn something new that should affect future GitHub work:

1. Save it via `memory_save` with tags `github` and the relevant topic (`pr`, `branch`, `ci`, `mcp-server`, etc.).
2. If the new lesson invalidates an existing rule, tell the user: "This contradicts Rule N — should I update the Skill draft?" Do not silently ignore the Skill rule.
3. Never write directly into `SKILL.md` — the file is managed by the user via the DeepSeek++ Skill UI.
4. At the start of any GitHub task, treat memory as the newest source of truth.

## Self-check before ending any GitHub task

- [ ] Every tool call used the FULL prefixed tag name.
- [ ] Every write was verified by reading the repository back.
- [ ] Every file update read the current content first, then used `create_or_update_file_with_sha`.
- [ ] Every branch operation respected the merge-then-new-branch rule.
- [ ] No conclusion was drawn from a single failed request without a tree-level check.
- [ ] No more than one MCP call was batched per assistant message (Rule 11).
- [ ] If a new lesson emerged, it was saved via `memory_save`.
