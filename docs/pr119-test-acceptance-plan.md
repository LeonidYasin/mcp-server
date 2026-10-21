# PR #119 — guarded TEST acceptance plan

Candidate: `a3d0768e0382dff1381ccd3e25133e362b9f8796`  
Base reviewed `main`: `8c2aa3ac6972e680cd9df7af982e66731d21f2ce`

This is a plan, not permission or an executable deployment helper. Do not run old
PR #112 rollout scripts: their fixed old/target SHAs and 120-tool assumptions are
historical and do not match the current 128-tool TEST composite.

## Accepted source gates

- GitHub Actions run `39629612221`: Python 3.10–3.13 all successful for the exact
  candidate SHA.
- Candidate inventory: default 114 tools; `find_repository_analogs` present;
  zero `rooms_*`; zero shell/process tools in the default profile.
- Current live TEST completed the previously pending pinned ConstruBot read at
  `ee3d69e0f6c721207ab66ceef2d830a316d80d52`, `backend/app/main.py` lines 21–40:
  `state=observed`, `explicit_path_walk_v1`, complete 20-line range, blob
  `ca1e04909a43c1ae1c4a7d8ad46ecbee75d80a1a`, content SHA-256
  `bfa7ad9f91230143826a1572033b039e49589722b0b17d43eae4ffc4aab47dc4`.

The live evidence proves the current TEST composite behavior, not installation of
this fresh candidate.

## Required operator decision

Prefer a separate temporary loopback candidate service so the current TEST Rooms
and its SQLite state are not replaced. Reusing `mcp-test.service` is allowed only
with an explicit owner decision, a private backup and a verified rollback to the
actual current checkout SHA.

Every remote shell/SSH/Python/process operation requires separate explicit owner
approval and the special password for that operation. A generic “continue” is not
approval. Never put that password, PAT, API key, environment, database or private
service output in GitHub or chat.

## Preflight — read-only first

The operator must record privately and verify before any checkout or service edit:

1. Actual current TEST checkout full SHA and clean worktree; do not infer it from
   old handoff reports or the public endpoint.
2. Exact systemd unit identity, user/group, working directory, venv, bind address,
   current MainPID and current feature flags.
3. Current `/health` revision/tool list and external `tools/list` inventory.
4. At least 2 GiB free space and a private root-owned backup location.
5. Fingerprints/status of production, Caddy and unrelated services; these must not
   change.
6. Current Rooms SQLite path/state if the existing TEST service might be touched.
   Never delete, migrate or publish it as part of this candidate.

Stop on an unexpected path, user, dirty/untracked file, unknown revision, missing
backup, changed service definition or incomplete inventory. Do not use hard reset,
force checkout, chmod 777, disable guards or remove unfamiliar files.

## Production-like candidate profile

The acceptance runtime must explicitly keep these disabled:

- `ENABLE_AGENT_ROOMS`
- `ENABLE_LOCAL_SHELL`
- `ENABLE_LOCAL_TOOLS`
- `ENABLE_SYNAPSE`

Expected registry: exactly 114 tools. Required: `find_repository_analogs`.
Forbidden: every `rooms_*` tool plus `run_command`, `run_python`,
`start_background`, `stop_process`, `process_status`, and `tail_log`.

Do not merely install the source into the existing TEST environment with its old
feature flags: that would not test the intended production profile.

## Runtime acceptance for the exact SHA

After an explicitly approved operator rollout:

1. Health reports commit prefix matching `a3d0768e0382dff1381ccd3e25133e362b9f8796`.
2. Service is active with a new PID; only the chosen TEST/candidate service changed.
3. `tools/list` equals the 114-tool default inventory and contains none of the
   forbidden tools.
4. `create_branch` schema exposes mutually exclusive `from_sha` / `from_branch` and
   the exact-SHA/read-back behavior from current main.
5. `search_repositories` exposes bounded public mode.
6. `get_repo_info` exposes `public_evidence` and explicit file selection.
7. `find_repository_analogs` exposes the reviewed bounded continuation/fingerprint
   schema.
8. Repeat the pinned ConstruBot lines 21–40 request and verify tree/blob/content
   integrity and `explicit_path_walk_v1` without retries or auth fallback.
9. Run one small bounded analog search with no writes; record exact candidate SHA,
   request counts, continuation and honest coverage limits.
10. External endpoint and localhost results agree. No mutation tool is invoked.

Success is `TEST_ACCEPTANCE_PASS` for this exact SHA only. It does not authorize
main merge or production deployment.

## Rollback and evidence

On any failure, restore the privately captured previous full SHA and original unit
environment, restart only the affected TEST/candidate service, and verify the old
health/inventory. Preserve private logs/backups; publish only concise status and
non-secret evidence. A failed rollback requires manual operator investigation and
must not be retried blindly.

After passing, add evidence to PR #119 with exact SHA, Actions run, inventory,
forbidden-tool absence, bounded smoke results and rollback readiness. Main merge
and production rollout remain two separate explicit approvals.