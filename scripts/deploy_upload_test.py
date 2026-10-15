"""Root orchestration for a NEW loopback-only #88 TEST, never existing units.

Git, pip and project Python run as a dedicated unprivileged user. No PAT, Caddy
configuration, public bind, autostart, system upgrade or production rollout.
"""
import argparse
import fcntl
import grp
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import socket
import stat
import subprocess
import tempfile
import time
from urllib.request import urlopen

USER = "mcp-upload-test"
UNIT = USER + ".service"
HOME = Path("/home") / USER
REPO = HOME / "repo"
VENV = HOME / "venv"
STAGING = HOME / "staging"
UNIT_FILE = Path("/etc/systemd/system") / UNIT
PORT = 3004
PROTECTED = ("mcp-server.service", "mcp-test.service", "caddy.service", "agora-mcp.service")
# Versions observed in the native environment that passed the candidate tests.
LOCK = (
    "flask==3.1.3", "flask-cors==6.0.5", "httpx==0.28.1", "python-dotenv==1.2.4",
    "gunicorn==26.2.0", "Werkzeug==3.1.9", "Jinja2==3.1.6", "MarkupSafe==3.0.4",
    "itsdangerous==2.2.0", "click==8.5.0", "blinker==1.9.0", "anyio==4.15.1",
    "httpcore==1.0.9", "idna==3.20", "h11==0.16.0", "certifi==2026.7.22",
    "packaging==26.3", "typing_extensions==4.16.0",
)


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def validate(target, users):
    require(isinstance(target, str) and re.fullmatch(r"[0-9a-f]{40}", target), "invalid full target SHA")
    require(users and all(type(u) is int and u > 0 for u in users), "explicit positive GitHub IDs required")
    return ",".join(str(u) for u in sorted(set(users)))


def properties(unit):
    raw = subprocess.check_output([
        "/usr/bin/systemctl", "show", unit, "--no-pager",
        "--property=LoadState,ActiveState,MainPID,User,Group,WorkingDirectory",
    ], text=True, timeout=15)
    return dict(line.split("=", 1) for line in raw.splitlines() if "=" in line)


def available_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", PORT))


def run_as_user(args, log, cwd=None, timeout=180, capture=False):
    # Never inherit root credentials, pip indexes, Git config or Python paths.
    env = ["PATH=/usr/bin:/bin", f"HOME={HOME}", "LANG=C.UTF-8",
           "GIT_TERMINAL_PROMPT=0", "GIT_CONFIG_NOSYSTEM=1", "GIT_CONFIG_GLOBAL=/dev/null",
           "PIP_CONFIG_FILE=/dev/null", "PIP_DISABLE_PIP_VERSION_CHECK=1",
           "PYTHONNOUSERSITE=1", "PYTHONDONTWRITEBYTECODE=1"]
    return subprocess.run(["/usr/sbin/runuser", "-u", USER, "--", "/usr/bin/env", "-i", *env, *map(str, args)],
                          cwd=cwd, stdout=subprocess.PIPE if capture else log,
                          stderr=log if capture else subprocess.STDOUT, text=capture,
                          timeout=timeout, check=True)


def seal_tree(path):
    for parent, directories, files in os.walk(path, followlinks=False):
        p = Path(parent)
        os.chown(p, 0, 0)
        os.chmod(p, 0o755)
        for name in directories + files:
            item = p / name
            mode = item.lstat().st_mode
            os.chown(item, 0, 0, follow_symlinks=False)
            if not stat.S_ISLNK(mode):
                os.chmod(item, 0o755 if stat.S_ISDIR(mode) or mode & 0o111 else 0o644)


def unit_text(target, users):
    allowed = validate(target, users)
    return f"""[Unit]
Description=Isolated binary upload TEST for PR 91 (loopback only)
After=network.target

[Service]
Type=simple
User={USER}
Group={USER}
WorkingDirectory={REPO}
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=PYTHONNOUSERSITE=1
Environment=ENABLE_LOCAL_TOOLS=0
Environment=ENABLE_LOCAL_SHELL=0
Environment=ENABLE_SYNAPSE=0
Environment=ENABLE_FILE_UPLOADS=1
Environment=FILE_UPLOAD_ROOT={STAGING}
Environment=FILE_UPLOAD_ALLOWED_USERS={allowed}
Environment=GIT_COMMIT={target}
Environment=GIT_CONFIG_COUNT=1
Environment=GIT_CONFIG_KEY_0=safe.directory
Environment=GIT_CONFIG_VALUE_0={REPO}
ExecStart={VENV}/bin/gunicorn --bind 127.0.0.1:{PORT} --workers 1 --timeout 60 --worker-tmp-dir /run/{USER} mcp_server.server:app
Restart=no
RuntimeMaxSec=7200
RuntimeDirectory={USER}
RuntimeDirectoryMode=0700
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths={STAGING}
InaccessiblePaths=-/home/mcp -/home/mcp-test -/root -/etc/caddy
CapabilityBoundingSet=
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
RestrictRealtime=true
LockPersonality=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
MemoryMax=256M
CPUQuota=25%
TasksMax=32
LimitNOFILE=256
"""


def health_gate(target):
    for _ in range(30):
        try:
            with urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2) as response:
                data = json.load(response)
            commit = data.get("commit", "")
            tools = set(data.get("tools", []))
            expected = {"begin_file_upload", "append_file_chunk", "finish_file_upload",
                        "get_file_upload_status", "cancel_file_upload", "cleanup_file_uploads"}
            require(data.get("status") == "ok" and isinstance(commit, str)
                    and len(commit) >= 7 and target.startswith(commit), "wrong build health")
            require(data.get("tool_count") == 119 and expected <= tools, "wrong upload registry")
            require(not {"run_command", "run_python", "start_process", "read_local_file"} & tools,
                    "unsafe local tools enabled")
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError("new loopback health gate failed")


def deploy(target, users):
    require(os.geteuid() == 0, "run from root console")
    validate(target, users)
    os.umask(0o077)
    lock_fd = os.open("/run/mcp-upload-test-setup.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_fd, "w") as lock:
        mode = os.fstat(lock.fileno())
        require(stat.S_ISREG(mode.st_mode) and mode.st_uid == 0 and mode.st_nlink == 1, "unsafe setup lock")
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        for lookup in (pwd.getpwnam, grp.getgrnam):
            try:
                lookup(USER)
            except KeyError:
                pass
            else:
                raise RuntimeError("upload account/group already exists; refusing to overwrite")
        require(not os.path.lexists(HOME) and not os.path.lexists(UNIT_FILE), "upload paths already exist")
        require(properties(UNIT).get("LoadState") == "not-found", "upload unit already exists")
        before = {u: properties(u) for u in PROTECTED}
        require(all(before[u].get("ActiveState") == "active" for u in PROTECTED[:3]), "existing services not active")
        available_port()
        require(shutil.disk_usage("/home").free >= 2 * 1024**3, "less than 2 GiB free")
        audit = Path(tempfile.mkdtemp(prefix="mcp-upload-setup-", dir="/root"))
        (audit / "before.json").write_text(json.dumps(before, indent=2))
        created_unit = False
        try:
            with (audit / "setup.log").open("w") as log:
                subprocess.run(["/usr/sbin/useradd", "--system", "--user-group", "--create-home",
                                "--home-dir", str(HOME), "--shell", "/usr/sbin/nologin", USER], check=True,
                               stdout=log, stderr=subprocess.STDOUT, timeout=30)
                user = pwd.getpwnam(USER)
                os.chmod(HOME, 0o700)
                for path in (REPO, STAGING):
                    path.mkdir(mode=0o700)
                    os.chown(path, user.pw_uid, user.pw_gid)
                run_as_user(["/usr/bin/git", "init", "-q", "--template=", REPO], log)
                run_as_user(["/usr/bin/git", "remote", "add", "origin", "https://github.com/LeonidYasin/mcp-server.git"], log, REPO)
                run_as_user(["/usr/bin/git", "fetch", "--depth=1", "origin", "refs/pull/91/head"], log, REPO)
                fetched = run_as_user(["/usr/bin/git", "rev-parse", "FETCH_HEAD"], log, REPO, capture=True).stdout.strip()
                require(fetched == target, "PR HEAD changed; stopping before project execution")
                run_as_user(["/usr/bin/git", "checkout", "--detach", "-q", target], log, REPO)
                run_as_user(["/usr/bin/python3", "-m", "venv", VENV], log)
                run_as_user([VENV / "bin/python", "-m", "pip", "install", "--only-binary=:all:", "--no-cache-dir",
                             "--index-url", "https://pypi.org/simple", *LOCK], log, timeout=300)
                run_as_user([VENV / "bin/python", "-m", "pip", "check"], log)
                for tree in (REPO, VENV):
                    seal_tree(tree)
                os.chown(HOME, 0, 0)
                os.chmod(HOME, 0o755)
                available_port()
                with UNIT_FILE.open("x") as unit:
                    unit.write(unit_text(target, users))
                created_unit = True
                UNIT_FILE.chmod(0o644)
                subprocess.run(["/usr/bin/systemd-analyze", "verify", str(UNIT_FILE)], check=True,
                               stdout=log, stderr=subprocess.STDOUT, timeout=30)
                subprocess.run(["/usr/bin/systemctl", "daemon-reload"], check=True, timeout=30)
                subprocess.run(["/usr/bin/systemctl", "start", UNIT], check=True, timeout=30)
                health_gate(target)
                require(properties(UNIT).get("ActiveState") == "active", "new unit not active")
                after = {u: properties(u) for u in PROTECTED}
                require(after == before, "protected service fingerprint changed; inspect separately")
                (audit / "after.json").write_text(json.dumps(after, indent=2))
        except Exception:
            if created_unit:
                subprocess.run(["/usr/bin/systemctl", "stop", UNIT], timeout=30, check=False)
            print(f"STOP: new upload TEST setup failed. Private log: {audit}/setup.log")
            print("Only the NEW unit was stopped. Account/files retained for inspection; no blind rerun.")
            raise
        print(json.dumps({"result":"LOOPBACK TEST READY", "sha":target, "unit":UNIT,
                          "listen":f"127.0.0.1:{PORT}", "tools":119, "allowed_github_users":users,
                          "auto_stop_seconds":7200, "enabled_at_boot":False,
                          "protected_services_unchanged":True, "public_endpoint":False,
                          "live_authenticated_upload_gate":False, "private_log":str(audit / "setup.log")}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--allow-user", type=int, action="append", required=True)
    args = parser.parse_args()
    deploy(args.target, args.allow_user)


if __name__ == "__main__":
    main()
