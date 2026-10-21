# Instructions for AI agents — mcp-server

Owner-facing communication is in Russian. Historical runbooks never override the
rules below.

## Operator scripts for the root Linux console

The owner runs every VPS/root operation himself. Agents must never hand over a
multi-line script to be pasted line by line into an interactive root shell
(a pasted `set -e`/`exit` can kill the root session, and partial pastes leave the
server half-changed).

1. Put the script into a **file** in this repository: `scripts/ops/<task>.sh`,
   mode `100755`, `#!/usr/bin/env bash`, `set -Eeuo pipefail`.
2. Pin exact full SHAs, service, user and paths inside the file. No branch-name
   checkouts, no `reset --hard`, no force, no deleting unfamiliar files.
3. Structure: read-only preflight with `STOP` (changes nothing) → private
   root-only backup → change → post-checks → automatic rollback on any error.
4. Never print secrets, env values (only filtered `ENABLE_*` flags), DB contents
   or private logs. Never ask for passwords or tokens in output.
5. The last line is a machine-readable `RESULT=...` (for example
   `ROLLOUT_PASS`, `STOP`, `ROLLED_BACK`, `ALREADY_AT_TARGET`) that the owner sends
   back to the agent.
6. Check syntax with `bash -n` and compute SHA-256 before handing it over.
7. Give the owner **one paste-safe line** that downloads the file by **commit
   SHA** (not branch), verifies SHA-256 and runs it as a file with a log:

```bash
cd /root && curl -fsSLo <task>.sh https://raw.githubusercontent.com/LeonidYasin/mcp-server/<commit-sha>/scripts/ops/<task>.sh && echo "<sha256>  <task>.sh" | sha256sum -c - && bash <task>.sh 2>&1 | tee <task>.log
```

Never use `curl | bash`. If the checksum fails, nothing is executed.

## Other standing constraints

- No main merge, deployment, Caddy/systemd, production DB or key changes without
  separate explicit owner approval. No force push, no bypassing branch protection.
- Production keeps `ENABLE_AGENT_ROOMS`, `ENABLE_LOCAL_SHELL`, `ENABLE_LOCAL_TOOLS`
  and `ENABLE_SYNAPSE` disabled; rooms live in `LeonidYasin/mcp-rooms`.
- Preserve branches and history of previous work; do not delete source branches.
