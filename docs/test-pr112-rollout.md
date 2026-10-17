# Operator-run TEST rollout for idea analog tools (PR #112)

This procedure is manual: the operator runs it in the existing VPS root console.
Do not execute it via MCP `run_python`, and do not weaken the MCP service sandbox.
Saving these files in GitHub does not deploy or merge anything.

## Fixed scope

- Runtime target: `20d26756b87f78f28d9c3f5ea8a14b3fd1de36b7`.
- Required existing TEST HEAD: `ef7993b87e8d6ed6598065e46203dc6145f9286d`.
- Only service restarted: `mcp-test.service`.
- Checkout: `/home/mcp-test/mcp-server`; existing venv: `/home/mcp-test/venv`.
- No main merge, production/Caddy/Agora restart, dependency installation, package upgrade, reboot, unit edit, remount, or deletion of unknown files.
- Candidate pytest in a separate VPS workspace: 1033 passed in 48.59 seconds. This does not establish external MCP acceptance.

## Run from the existing root console

The download is copied into a private root-owned directory and checksum-verified before execution. The branch URL below may change, but changed bytes will fail the fixed checksum. For a pinned commit URL, use the publication commit reported by the agent instead of `refs/heads/feat/idea-analog-workflow`.

```bash
(
  set -euo pipefail
  test "$(id -u)" -eq 0
  umask 077
  d=$(mktemp -d /root/mcp-test-pr112-command-XXXXXXXX)
  curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
    'https://raw.githubusercontent.com/LeonidYasin/mcp-server/efcaf8145a1771c987021be62a8d40389fb5916f/scripts/deploy_test_pr112.py' \
    -o "$d/deploy_test_pr112.py"
  printf '%s  %s\n' \
    '7f5ab9dbc1378b793302b13c5ef50b24f5e3be8878501689f4ad7904de8525f2' \
    "$d/deploy_test_pr112.py" | sha256sum --check --status
  /usr/bin/python3 "$d/deploy_test_pr112.py"
)
```

Python is used here only when the operator explicitly runs this command; the agent does not execute it remotely. Root orchestrates the fixed TEST service. All Git and repository/Python-import subprocesses run as unprivileged `mcp-test` with a clean environment, no hooks, and no credential inheritance. No token is needed for localhost health/tools-list checks.

## Guardrails and expected result

The script refuses an unexpected service/user/path, changed current SHA, dirty or untracked files, existing/new tool-inventory mismatch, or less than 2 GiB free. It acquires a deployment lock, saves tracked old source and state in a private `/root/mcp-test-pr112-*` backup, fetches the fixed public target, and checks out that exact commit. It restarts only TEST and checks health, revision, 120-tool inventory, and the analog/evidence schema. Production/Caddy/Agora fingerprints must remain unchanged.

Success prints `TEST_ROLLOUT_PASS` with the backup location and `external_four_case_acceptance: pending`. A caught failure after checkout attempts return to the original SHA and TEST restart. `TEST_ROLLBACK_PASS` confirms the old health/inventory returned. `TEST_ROLLBACK_FAILED` needs operator investigation; do not blindly rerun. There is no promise of automatic recovery after host loss, reboot, or killing the orchestrator.

Send only the final status or concise error back to the agent. Do not paste the private log, environment variables, tokens, or credentials. After success the agent must verify the external MCP endpoint and run the four idea-analog scenarios; localhost checks are not a substitute.

If preflight stops, preserve the backup/log and inspect the specific cause. Do not use `git reset --hard`, disable sandbox restrictions, or remove unfamiliar files to force progress.
