# Instructions for AI agents — mcp-server

Owner-facing communication is in Russian. Historical runbooks never override the
rules below.

## Standard rollout: `mcp-deploy`

Routine production/TEST updates use the installed root-owned command
`/usr/local/sbin/mcp-deploy` (source: `scripts/ops/mcp-deploy`, reviewed and
tested in CI). The agent gives the owner one line, for example:

```bash
mcp-deploy prod <full-40-hex-sha>
```

Before giving it, the agent verifies: the SHA is on `main` (production), CI for
that exact SHA is green, no dependency files changed, PR/merge state. After
`RESULT=ROLLOUT_PASS` the agent verifies externally via MCP (`list_my_tools`,
`describe_tool`, bounded read-only smoke) and records evidence in the PR and
`docs/deployment-status.md`. Rollback: `mcp-deploy prod <old-sha> --downgrade`.
`mcp-deploy status` shows current revisions. Changes to `mcp-deploy` itself are
installed by an inline paste block that reads the file from git by exact commit
SHA (`git show <sha>:scripts/ops/mcp-deploy`), never via `curl`.

Inline paste blocks (below) remain for non-standard one-off operations.

## Operator scripts for the root Linux console

The owner runs every VPS/root operation himself by **pasting a block into the
root console**. Agents give the script inline in chat, **not as a file** (no
`scripts/ops/*.sh` to download, no `curl`/`wget` of scripts, never `curl | bash`).

The block must be paste-safe in an interactive root shell:

1. Wrap the whole script so it runs in a child bash, passed as an argument (stdin
   stays the terminal, `set -e`/`exit` cannot kill the root session, a partial
   paste does nothing until the closing line):

```bash
bash -c "$(cat <<'MCP_OPS_EOF'
set -Eeuo pipefail
# ... script body ...
MCP_OPS_EOF
)" 2>&1 | tee /root/<task>-$(date +%Y%m%d-%H%M%S).log
```

2. Pin exact full SHAs, service, user and paths in the body. No branch-name
   checkouts, no `reset --hard`, no force, no deleting unfamiliar files.
3. Structure: read-only preflight with `STOP` (changes nothing) → private
   root-only backup → change → post-checks → automatic rollback on any error.
4. Never print secrets, env values (only filtered `ENABLE_*` flags), DB contents
   or private logs. Never ask for passwords or tokens in output.
5. The last line is a machine-readable `RESULT=...` (for example
   `ROLLOUT_PASS`, `STOP`, `ROLLED_BACK`, `ALREADY_AT_TARGET`) that the owner sends
   back to the agent.
6. Check the body with `bash -n` before handing it over; the body must not
   contain the line `MCP_OPS_EOF`.

## Other standing constraints

- No main merge, deployment, Caddy/systemd, production DB or key changes without
  separate explicit owner approval. No force push, no bypassing branch protection.
- Production keeps `ENABLE_AGENT_ROOMS`, `ENABLE_LOCAL_SHELL`, `ENABLE_LOCAL_TOOLS`
  and `ENABLE_SYNAPSE` disabled; rooms live in `LeonidYasin/mcp-rooms`.
- Preserve branches and history of previous work; do not delete source branches.
