"""The Stop hook's loop logic, run against a stub verify.sh so no stack tools are needed."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
STOP_HOOK = ROOT / "hooks" / "verify-stop.sh"
SESSION_START = ROOT / "hooks" / "session-start.sh"

STUB_VERIFY = """#!/bin/sh
echo "stub verify ran (rc $STUB_RC)"
exit "${STUB_RC:-0}"
"""


def git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def plugin(tmp_path: Path) -> Path:
    """A fake plugin root whose verify.sh exits with $STUB_RC."""
    root = tmp_path / "plugin"
    script = root / "skills" / "verify" / "scripts" / "verify.sh"
    script.parent.mkdir(parents=True)
    script.write_text(STUB_VERIFY)
    return root


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git("init", "-q", "-b", "main", cwd=repo)
    (repo / "README.md").write_text("x\n")
    return repo


def arm(repo: Path, session: str = "s1", iteration: int = 0, maximum: int = 5) -> Path:
    state = repo / ".factory" / "loop.local.md"
    state.parent.mkdir(exist_ok=True)
    state.write_text(
        f"---\nsession_id: {session}\niteration: {iteration}\nmax_iterations: {maximum}\n---\n"
    )
    return state


def iteration_of(state: Path) -> int:
    for line in state.read_text().splitlines():
        if line.startswith("iteration:"):
            return int(line.split(":", 1)[1])
    raise AssertionError("no iteration line")


def run_hook(
    repo: Path,
    plugin: Path,
    rc: int = 0,
    session: str = "s1",
    stop_hook_active: bool = False,
    cwd: Path | None = None,
    path: str | None = None,
) -> subprocess.CompletedProcess:
    payload = {
        "session_id": session,
        "stop_hook_active": stop_hook_active,
        "cwd": str(repo),
        "hook_event_name": "Stop",
    }
    env = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(plugin), "STUB_RC": str(rc)}
    env.pop("CLAUDE_PROJECT_DIR", None)
    if path is not None:
        env["PATH"] = path
    return subprocess.run(
        ["sh", str(STOP_HOOK)],
        cwd=cwd or repo,
        env=env,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )


def decision(result: subprocess.CompletedProcess) -> dict:
    assert result.stdout.strip(), f"expected a decision on stdout, got stderr {result.stderr!r}"
    return json.loads(result.stdout)


def test_no_state_file_lets_the_turn_end(repo: Path, plugin: Path):
    result = run_hook(repo, plugin, rc=1)
    assert result.returncode == 0
    assert result.stdout == ""


def test_another_sessions_loop_is_left_alone(repo: Path, plugin: Path):
    state = arm(repo, session="other")
    result = run_hook(repo, plugin, rc=1, session="s1")
    assert result.returncode == 0
    assert result.stdout == ""
    assert iteration_of(state) == 0


def test_blank_session_in_state_acts_for_any_session(repo: Path, plugin: Path):
    arm(repo, session="")
    result = run_hook(repo, plugin, rc=1, session="whoever")
    assert decision(result)["decision"] == "block"


def test_red_blocks_with_the_summary_and_bumps_the_iteration(repo: Path, plugin: Path):
    state = arm(repo)
    result = run_hook(repo, plugin, rc=1)
    assert result.returncode == 0
    body = decision(result)
    assert body["decision"] == "block"
    assert "loop 1 of 5" in body["reason"]
    assert "stub verify ran (rc 1)" in body["reason"]
    assert "Do not weaken tests" in body["reason"]
    assert iteration_of(state) == 1
    assert (repo / ".verify" / "stop.log").is_file()


def test_exit_two_blocks_with_the_setup_reason(repo: Path, plugin: Path):
    arm(repo)
    body = decision(run_hook(repo, plugin, rc=2))
    assert body["decision"] == "block"
    assert "could not run (exit 2" in body["reason"]
    assert "Fix the setup it names, not the code" in body["reason"]


def test_green_disarms(repo: Path, plugin: Path):
    state = arm(repo, iteration=3)
    result = run_hook(repo, plugin, rc=0)
    assert result.returncode == 0
    assert result.stdout == ""
    assert not state.exists()


def test_cap_disarms_and_lets_the_turn_end(repo: Path, plugin: Path):
    state = arm(repo, iteration=5, maximum=5)
    result = run_hook(repo, plugin, rc=1)
    assert result.returncode == 0
    assert result.stdout == ""
    assert "reached 5 iterations; disarmed" in result.stderr
    assert not state.exists()


def test_continuation_forced_by_this_hook_still_blocks_while_red(repo: Path, plugin: Path):
    # The loop is bounded by max_iterations, not by a single forced continuation.
    state = arm(repo, iteration=1)
    body = decision(run_hook(repo, plugin, rc=1, stop_hook_active=True))
    assert body["decision"] == "block"
    assert "loop 2 of 5" in body["reason"]
    assert iteration_of(state) == 2


def test_payload_cwd_wins_over_the_hooks_working_directory(repo: Path, plugin: Path, tmp_path: Path):
    # A worktree agent's stop carries the worktree as cwd; the hook must gate that tree.
    state = arm(repo)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    body = decision(run_hook(repo, plugin, rc=1, cwd=elsewhere))
    assert body["decision"] == "block"
    assert iteration_of(state) == 1


def test_without_jq_the_hook_still_blocks(repo: Path, plugin: Path, tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in ("sh", "git", "sed", "head", "tail", "cat", "mkdir", "rm", "mv", "dirname", "tee"):
        found = shutil.which(tool)
        assert found, tool
        (bin_dir / tool).symlink_to(found)
    state = arm(repo)
    result = run_hook(repo, plugin, rc=1, path=str(bin_dir))
    assert result.returncode == 0
    body = decision(result)
    assert body["decision"] == "block"
    assert "loop 1 of 5" in body["reason"]
    assert ".verify/stop.tail" in body["reason"]
    assert iteration_of(state) == 1


def test_session_start_reports_tools_and_never_fails(repo: Path):
    result = subprocess.run(
        ["sh", str(SESSION_START)],
        cwd=repo,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(repo)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.startswith("factory: ")
    assert "factory.toml absent" in result.stdout
    assert "/factory:setup" in result.stdout
