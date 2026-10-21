"""Static/safe checks for scripts/ops/mcp-deploy (no root, no system changes)."""
from pathlib import Path
import shutil
import subprocess

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ops" / "mcp-deploy"
BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(BASH is None, reason="bash not available")


def run(*args):
    return subprocess.run([BASH, str(SCRIPT), *args], capture_output=True, text=True, timeout=30)


def test_syntax():
    assert subprocess.run([BASH, "-n", str(SCRIPT)], timeout=30).returncode == 0


def test_help_exits_zero():
    result = run("--help")
    assert result.returncode == 0
    assert "mcp-deploy prod" in result.stdout


@pytest.mark.parametrize("args", [(), ("staging", "a" * 40), ("prod", "abc123"), ("prod", "A" * 40), ("prod", "a" * 40, "--force")])
def test_invalid_arguments_stop_before_any_action(args):
    result = run(*args)
    assert result.returncode == 2
    assert "RESULT=STOP" in result.stdout


def test_production_guards_present():
    text = SCRIPT.read_text(encoding="utf-8")
    for needle in ("set -Eeuo pipefail", "flock -n 9", "merge-base --is-ancestor \"$TARGET\" origin/main",
                   "ENABLE_(AGENT_ROOMS|LOCAL_SHELL|LOCAL_TOOLS|SYNAPSE)", "trap rollback ERR",
                   "RESULT=ROLLOUT_PASS", "--downgrade"):
        assert needle in text
    for forbidden in ("reset --hard", "push --force", "rm -rf", "curl | bash", "pip install"):
        assert forbidden not in text
