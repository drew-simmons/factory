"""End-to-end checks for skills/verify/scripts/verify.sh on a python fixture repo."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
VERIFY = ROOT / "skills" / "verify" / "scripts" / "verify.sh"
needs_tools = pytest.mark.skipif(
    not all(shutil.which(t) for t in ("uv", "poly-crap", "jq", "git")),
    reason="verify.sh end-to-end tests need uv, poly-crap, jq, and git",
)

PYPROJECT = """[project]
name = "fixture"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[dependency-groups]
dev = ["pytest>=8", "pytest-cov>=5"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]

[tool.coverage.run]
source = ["src"]
"""

MODULE = """def add(a: int, b: int) -> int:
    return a + b
"""

TEST = """from fixture import add


def test_add():
    assert add(1, 2) == 3
"""


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def commit_all(repo: Path, message: str) -> None:
    git("add", "-A", cwd=repo)
    git("commit", "-q", "-m", message, cwd=repo)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo = tmp_path / "fixture"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    git("init", "-q", "-b", "main", cwd=repo)
    for key, value in (("commit.gpgsign", "false"), ("user.name", "t"), ("user.email", "t@t")):
        git("config", key, value, cwd=repo)
    (repo / "pyproject.toml").write_text(PYPROJECT)
    (repo / "src" / "fixture.py").write_text(MODULE)
    (repo / "tests" / "test_fixture.py").write_text(TEST)
    (repo / ".gitignore").write_text(".venv/\n.verify/\n.pytest_cache/\n__pycache__/\n.coverage\n")
    (repo / "factory.toml").write_text("[factory]\nbase = 'main'\n")
    commit_all(repo, "base")
    git("switch", "-q", "-c", "feature", cwd=repo)
    return repo


def run_verify(repo: Path, **env: str) -> subprocess.CompletedProcess:
    full_env = {**os.environ, "HUNK": "0", **env}
    return subprocess.run(
        ["sh", str(VERIFY)], cwd=repo, env=full_env, capture_output=True, text=True, check=False
    )


@needs_tools
def test_green_change_exits_zero_and_stamps(repo: Path):
    (repo / "src" / "fixture.py").write_text(
        MODULE + "\n\ndef sub(a: int, b: int) -> int:\n    return a - b\n"
    )
    (repo / "tests" / "test_fixture.py").write_text(
        TEST.replace("from fixture import add", "from fixture import add, sub")
        + "\n\ndef test_sub():\n    assert sub(3, 1) == 2\n"
    )
    result = run_verify(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (repo / ".verify" / "green").is_file()
    assert "stack python" in result.stdout
    rerun = run_verify(repo)
    assert rerun.returncode == 0
    assert "unchanged since the last green run" in rerun.stdout


@needs_tools
def test_new_suppression_trips_the_floor(repo: Path):
    suppression = "# " + "noqa"  # split so this file does not trip the floor itself
    (repo / "src" / "fixture.py").write_text(MODULE + f"import os  {suppression}\n")
    result = run_verify(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "FLOOR new suppression" in result.stdout
    assert not (repo / ".verify" / "green").exists()


@needs_tools
def test_untested_complex_function_fails_poly_crap(repo: Path):
    complex_fn = """

def classify(n: int) -> str:
    if n < 0:
        return "negative"
    if n == 0:
        return "zero"
    if n < 10:
        return "small"
    if n < 100:
        return "medium"
    if n < 1000:
        return "large"
    return "huge"
"""
    (repo / "src" / "fixture.py").write_text(MODULE + complex_fn)
    result = run_verify(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "classify" in result.stdout
    summary = (repo / ".verify" / "summary.txt").read_text()
    assert "poly-crap" in summary
    assert (repo / ".verify" / "crap.json").is_file()


@needs_tools
def test_unknown_stack_without_commands_exits_two(tmp_path: Path):
    repo = tmp_path / "bare"
    repo.mkdir()
    git("init", "-q", "-b", "main", cwd=repo)
    for key, value in (("commit.gpgsign", "false"), ("user.name", "t"), ("user.email", "t@t")):
        git("config", key, value, cwd=repo)
    (repo / "README.md").write_text("x\n")
    commit_all(repo, "base")
    (repo / "README.md").write_text("y\n")
    result = run_verify(repo, BASE="main")
    assert result.returncode == 2
    assert "unknown stack" in result.stdout


@needs_tools
def test_root_level_source_file_does_not_hide_changes_under_src(repo: Path):
    # An unquoted *.py at the repository root used to expand to conftest.py
    # and turn the pathspec into that one file, so src/ changes went unseen.
    (repo / "conftest.py").write_text("")
    commit_all(repo, "add conftest")
    (repo / "src" / "fixture.py").write_text(MODULE + "import os  # no" + "qa\n")
    result = run_verify(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "FLOOR new suppression" in result.stdout
    assert "src/fixture.py" in result.stdout


@needs_tools
def test_loop_flag_arms_the_stop_hook_state_file(repo: Path):
    (repo / "src" / "fixture.py").write_text(
        MODULE + "\n\ndef sub(a: int, b: int) -> int:\n    return a - b\n"
    )
    (repo / "tests" / "test_fixture.py").write_text(
        TEST.replace("from fixture import add", "from fixture import add, sub")
        + "\n\ndef test_sub():\n    assert sub(3, 1) == 2\n"
    )
    result = subprocess.run(
        ["sh", str(VERIFY), "--loop"],
        cwd=repo,
        env={**os.environ, "HUNK": "0"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    state = (repo / ".factory" / "loop.local.md").read_text()
    assert "iteration: 0" in state
    assert "max_iterations: 5" in state
