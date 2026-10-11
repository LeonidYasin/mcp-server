# Process manager: safety and lifecycle contract

The four tools are Linux-only and opt-in under `ENABLE_LOCAL_SHELL=1`:
`start_background`, `stop_process`, `process_status`, `tail_log`.
They provide arbitrary-command execution with the server user's permissions,
not a security sandbox. A command deny-list is only a guardrail.

## Required deployment boundary

- Use a dedicated non-root OS user and a private `LOCAL_TOOLS_ROOT`.
- Keep authentication on the reverse proxy. Require confirmation for write tools
  in clients; do not expose shell/process tools to untrusted users.
- Enable the feature on an isolated TEST service first, not production.
- Use filesystem/cgroup restrictions, resource quotas and network restrictions
  appropriate to the deployment. Tools do not enforce disk/log rotation or a
  per-command lifetime. Logs can grow on disk even though reads are bounded.
- Commands inherit the service environment plus explicit `env` overrides.
  Never put credentials in argv: commands are returned and stored in metadata.
  Env values are not included in manager metadata/results, but the child itself
  can print them. This is not a guarantee of automatic secret redaction.

## Tracking and stopping

Processes start with `shell=False`, a new session and process group. Names are
limited to 64 ASCII letters/digits/underscore/hyphen. Cwd must resolve inside
`LOCAL_TOOLS_ROOT`; this does not restrict arbitrary filesystem reads made by
an executable. There are at most 100 tracked metadata entries for new starts.

Tracking records Linux boot ID, start ticks, effective UID, process group and
session in addition to PID. `stop_process` checks current identity/ownership
and group leadership before signaling, then checks again immediately before
`killpg`. PID reuse, a different boot or legacy/unverified identity never
receives a signal. A live but unverified PID is not reported as our running
process. Dead entries can be removed through `stop_process`.

Linux `/proc` entries can disappear after open while being read: ENOENT/ESRCH
are treated as gone, including during iteration. Permission and unrelated I/O
errors are not silently converted into proof of death. After zombie reaping,
one saved state read is used rather than combining two inconsistent reads.
This reduces observation races; it is not an atomic PID/identity or group lock.

Timeout is an integer 0–30 seconds; force is a boolean. Without force, only
SIGTERM is sent; timeout reports the still-running process and asks for explicit
force. Force sends SIGKILL. Signals reach the verified group, not processes that
have detached into a different group/session.

**Limits:** `killpg` is not an atomic pidfd-based group operation; identity
checks reduce stale-PID risk but leave a narrow check-to-signal kernel race.
If the group leader exits while descendants remain, the manager refuses to
signal an unverified/reused leader. Same-UID arbitrary commands can tamper with
metadata; the dedicated OS user is the trust boundary, not cryptographic
attestation. Legacy live records need operator review, not an automatic guess.

## Persistence and files

`.mcp_processes` must be a server-owned, non-symlink directory (mode 0700).
Files are opened relative to a no-follow directory descriptor; symlink,
non-regular, wrong-owner and multi-hardlink files are refused. Metadata writes
use a temporary 0600 file and atomic replace. A nonblocking Linux flock
serializes manager operations; a busy lock fails instead of waiting forever.
Tracking failure triggers best-effort cleanup of the just-created child/group.
Escaped/daemonized descendants are not guaranteed to be cleaned up.

`tail_log` ignores `log_file` from mutable JSON and opens only the canonical
`<name>.log`. It reads a bounded suffix, not the entire file; UTF-8 characters
are not split in returned output. `lines` is an integer 0–1000 (default 100;
0 returns an empty body). Body bytes use `LOCAL_TOOLS_MAX_OUTPUT_BYTES` (default
200000, effective range 1–1000000); the descriptive header is outside this
budget. A clipped first line can be partial; `bytes_truncated` reports clipping.
`process_status()` lists at most 100 records with an explicit truncation marker;
query a specific name for entries outside that subset.

## Restart semantics

A new session survives an individual request, **not necessarily a service
restart**. Default systemd `KillMode=control-group` stops children with the
service. Keep that policy for TEST and verify stale metadata after a restart.
Do not silently set `KillMode=process` just to make children survive: it weakens
service cleanup. Truly persistent applications should use their own supervised
systemd service with an explicit lifecycle and resource policy.

## Validation

Unit/security cases cover identity mismatch, legacy records, symlinks/hardlinks,
FIFO refusal, limits, atomic metadata, and feature gates. Disposable local live
process tests cover start/status/log/TERM, forced KILL, group descendants and
tracking failure. These tests do not establish that production deployment or
VPS transport checks have happened. After changing feature flags/tools, refresh
client tool discovery: a cached schema/catalog can differ from runtime.
