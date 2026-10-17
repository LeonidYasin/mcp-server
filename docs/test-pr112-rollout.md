# Operator-run TEST rollout for idea analog tools (PR #112)

This procedure is manual: the operator runs it in the existing VPS root console.
Do not execute it via MCP `run_python`, and do not weaken the MCP service sandbox.
Saving these files in GitHub does not deploy or merge anything.

## Current follow-up: deploy the path-walk fix to TEST

The first rollout below already passed. Current installed TEST revision is `20d26756b87f78f28d9c3f5ea8a14b3fd1de36b7` with 120 tools. The next fixed runtime target is `65ddae12bfaf6d117bb8f472ba396016db36610a`, which includes the explicit-path oversized-tree fix and 27 regression cases. [CI attempt 1](https://github.com/LeonidYasin/mcp-server/actions/runs/39036995274) passed Python 3.10–3.13; Python 3.12 logs report 1060 tests passed. See [external acceptance](idea-analog-external-acceptance.md) for what is and is not accepted.

The updated operator script at `72719300c1f5042ddaf5845a358194868850b685` requires that exact existing 20d2675 HEAD and the existing analog-enabled 120-tool inventory. It retains the first rollout's backup, TEST-only restart, protected-service checks and rollback controls. It does not install dependencies or merge main. The agent has only saved the file, not run it.

Run this block in the existing VPS root console only when ready to update TEST:

```bash
(
  set -euo pipefail
  test "$(id -u)" -eq 0
  umask 077
  d=$(mktemp -d /root/mcp-test-pr112-command-XXXXXXXX)
  curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
    'https://raw.githubusercontent.com/LeonidYasin/mcp-server/72719300c1f5042ddaf5845a358194868850b685/scripts/deploy_test_pr112.py' \
    -o "$d/deploy_test_pr112.py"
  printf '%s  %s\n' \
    '61d9965cf74a6ba21b7a35c0dcae59b04a423927111b9f520a19c602dc25b891' \
    "$d/deploy_test_pr112.py" | sha256sum --check
  /usr/bin/python3 "$d/deploy_test_pr112.py"
)
```

Expected `TEST_ROLLOUT_PASS` target is 65ddae12bfaf6d117bb8f472ba396016db36610a; previous is 20d26756b87f78f28d9c3f5ea8a14b3fd1de36b7; tool count stays 120. The agent must then repeat external ConstruBot explicit evidence for `backend/app/main.py` lines 21–40 at `ee3d69e0f6c721207ab66ceef2d830a316d80d52`. Success of the operator script alone does not establish that recovery. On error, preserve backup and send only concise status, not private logs; do not blindly rerun.

## Historical first rollout — do not rerun after 20d2675 is installed

The remainder records the earlier 119-to-120-tool rollout. Its pinned script and checksum intentionally refer to the original version, not the current follow-up.

### Fixed scope of the first rollout

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
