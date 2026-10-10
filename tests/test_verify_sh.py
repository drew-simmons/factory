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


# verify.sh reads these from the environment; a test must not inherit them from
# the shell that runs pytest (CI runs this suite inside verify.sh itself).
OVERRIDES = (
    "BASE",
    "THRESHOLD",
    "VERIFY_LLM_OVERRIDE",
    "MAX_REQUESTS",
    "LAWBOOK_CONFIG",
    "CLAUDE_PROJECT_DIR",
)


def clean_env(**env: str) -> dict[str, str]:
    base = {k: v for k, v in os.environ.items() if k not in OVERRIDES}
    return {**base, "HUNK": "0", **env}


def run_verify(
    repo: Path, *args: str, cwd: Path | None = None, **env: str
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["sh", str(VERIFY), *args],
        cwd=cwd or repo,
        env=clean_env(**env),
        capture_output=True,
        text=True,
        check=False,
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
    result = run_verify(repo, "--loop")
    assert result.returncode == 0, result.stdout + result.stderr
    state = (repo / ".factory" / "loop.local.md").read_text()
    assert "iteration: 0" in state
    assert "max_iterations: 5" in state


@needs_tools
def test_planned_slice_is_measured_against_its_parent(repo: Path):
    # The parent branch carries a suppression; the slice stacked on it is
    # clean. Against main the floor would trip; against the parent it must not.
    suppression = "# " + "noqa"
    (repo / "src" / "fixture.py").write_text(f"import os  {suppression}: F401\n\n\n" + MODULE)
    commit_all(repo, "parent slice with a suppression")
    git("switch", "-q", "-c", "feature-02", "feature", cwd=repo)
    plan = repo / "docs" / "specs" / "stack" / "plan.md"
    plan.parent.mkdir(parents=True)
    plan.write_text(
        "# stack plan\n\n### 01 parent\n\n- Branch: feature\n- Parent: main\n\n"
        "### 02 child\n\n- Branch: feature-02\n- Parent: feature\n"
    )
    (repo / "src" / "fixture.py").write_text(
        (repo / "src" / "fixture.py").read_text()
        + "\n\ndef sub(a: int, b: int) -> int:\n    return a - b\n"
    )
    (repo / "tests" / "test_fixture.py").write_text(
        TEST.replace("from fixture import add", "from fixture import add, sub")
        + "\n\ndef test_sub():\n    assert sub(3, 1) == 2\n"
    )
    result = run_verify(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "verify: feature..working tree" in result.stdout
    against_main = run_verify(repo, BASE="main")
    assert against_main.returncode == 1
    assert "FLOOR new suppression" in against_main.stdout


def green_change(repo: Path) -> None:
    (repo / "src" / "fixture.py").write_text(
        MODULE + "\n\ndef sub(a: int, b: int) -> int:\n    return a - b\n"
    )
    (repo / "tests" / "test_fixture.py").write_text(
        TEST.replace("from fixture import add", "from fixture import add, sub")
        + "\n\ndef test_sub():\n    assert sub(3, 1) == 2\n"
    )


@needs_tools
def test_missing_base_ref_exits_two_and_names_it(repo: Path):
    green_change(repo)
    result = run_verify(repo, BASE="no-such-branch")
    assert result.returncode == 2, result.stdout + result.stderr
    assert "base ref no-such-branch does not exist" in result.stderr
    assert not (repo / ".verify" / "green").exists()


@needs_tools
def test_missing_slice_parent_exits_two(repo: Path):
    plan = repo / "docs" / "specs" / "stack" / "plan.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("# plan\n\n### 01 only\n\n- Branch: feature\n- Parent: not-fetched\n")
    green_change(repo)
    result = run_verify(repo)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "Parent not-fetched of branch feature" in result.stderr


@needs_tools
def test_no_merge_base_exits_two(repo: Path):
    git("switch", "-q", "--orphan", "island", cwd=repo)
    (repo / "pyproject.toml").write_text(PYPROJECT)
    (repo / "factory.toml").write_text("[factory]\nbase = 'main'\n")
    commit_all(repo, "unrelated history")
    result = run_verify(repo)
    assert result.returncode == 2
    assert "no merge base" in result.stderr


@needs_tools
def test_missing_tool_in_a_stage_command_is_a_broken_loop_not_a_failed_gate(repo: Path):
    (repo / "factory.toml").write_text(
        "[factory]\nbase = 'main'\n[verify.commands]\nlint = 'no-such-linter src'\n"
    )
    green_change(repo)
    result = run_verify(repo)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "command not found or not executable: no-such-linter" in result.stdout
    assert "Fix the setup, not the code" in result.stdout


@needs_tools
def test_malformed_factory_toml_exits_two(repo: Path):
    (repo / "factory.toml").write_text("[factory\nbase = \n")
    green_change(repo)
    result = run_verify(repo)
    assert result.returncode == 2
    assert "not valid TOML" in result.stderr


@needs_tools
def test_a_changed_threshold_is_a_new_run_not_a_stamp_hit(repo: Path):
    green_change(repo)
    assert run_verify(repo).returncode == 0
    rerun = run_verify(repo, THRESHOLD="1")
    assert "unchanged since the last green run" not in rerun.stdout


@needs_tools
def test_verify_from_a_worktree_measures_the_worktree(repo: Path, tmp_path: Path):
    worktree = tmp_path / "wt"
    git("worktree", "add", "-q", "-b", "slice", str(worktree), "main", cwd=repo)
    suppression = "# " + "noqa"
    (worktree / "src" / "fixture.py").write_text(MODULE + f"import os  {suppression}\n")
    result = run_verify(repo, cwd=worktree, CLAUDE_PROJECT_DIR=str(repo))
    assert result.returncode == 1, result.stdout + result.stderr
    assert "FLOOR new suppression" in result.stdout
    assert (worktree / ".verify" / "summary.txt").is_file()
    assert not (repo / ".verify").exists()


@needs_tools
def test_raising_the_crap_threshold_trips_the_floor_lowering_does_not(repo: Path):
    (repo / "factory.toml").write_text("[factory]\nbase = 'main'\n[verify]\ncrap_threshold = 30\n")
    raised = run_verify(repo)
    assert raised.returncode == 1, raised.stdout + raised.stderr
    assert "FLOOR factory.toml raises the CRAP threshold from 5 (default) to 30" in raised.stdout
    (repo / "factory.toml").write_text("[factory]\nbase = 'main'\n[verify]\ncrap_threshold = 3\n")
    lowered = run_verify(repo)
    assert lowered.returncode == 0, lowered.stdout + lowered.stderr


@needs_tools
def test_demoting_or_deleting_a_lawbook_rule_trips_the_floor(repo: Path):
    rules = (
        "version: 1\nrules:\n"
        "  - id: has-readme\n    exists: ['README.md']\n    level: error\n"
        "  - id: no-env-file\n    absent: ['.env']\n    level: error\n"
    )
    (repo / "lawbook.yaml").write_text(rules)
    (repo / "README.md").write_text("fixture\n")
    commit_all(repo, "add lawbook rules")
    (repo / "lawbook.yaml").write_text(
        rules.replace(
            "exists: ['README.md']\n    level: error", "exists: ['README.md']\n    level: warn"
        )
    )
    demoted = run_verify(repo, BASE="feature")
    assert demoted.returncode == 1, demoted.stdout + demoted.stderr
    assert "FLOOR lawbook.yaml demotes an error-level rule" in demoted.stdout
    (repo / "lawbook.yaml").write_text(rules.split("  - id: no-env-file")[0])
    deleted = run_verify(repo, BASE="feature")
    assert deleted.returncode == 1, deleted.stdout + deleted.stderr
    assert "FLOOR lawbook.yaml deletes rule no-env-file" in deleted.stdout


@needs_tools
def test_skipped_test_and_deleted_test_file_trip_the_floor(repo: Path):
    skip = "@pytest.mark." + "skip"
    (repo / "tests" / "test_fixture.py").write_text(
        "import pytest\n" + TEST.replace("def test_add", f"{skip}\ndef test_add")
    )
    skipped = run_verify(repo)
    assert skipped.returncode == 1, skipped.stdout + skipped.stderr
    assert "FLOOR skipped or focused test" in skipped.stdout
    git("checkout", "--", "tests", cwd=repo)
    (repo / "tests" / "test_fixture.py").unlink()
    git("add", "-A", cwd=repo)
    deleted = run_verify(repo)
    assert deleted.returncode == 1, deleted.stdout + deleted.stderr
    assert "FLOOR deleted test files" in deleted.stdout


@needs_tools
def test_removing_a_test_case_inside_a_kept_file_trips_the_floor(repo: Path):
    (repo / "tests" / "test_fixture.py").write_text(
        TEST + "\n\ndef test_add_zero():\n    assert add(0, 0) == 0\n"
    )
    commit_all(repo, "two tests")
    git("switch", "-q", "-c", "slice", cwd=repo)
    (repo / "tests" / "test_fixture.py").write_text(TEST)
    result = run_verify(repo, BASE="feature")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "FLOOR test definitions removed: 1 removed, 0 added" in result.stdout


@needs_tools
def test_a_slice_that_only_adds_a_test_does_not_inherit_old_debt(repo: Path):
    # A complex untested function already on main must not fail a slice that
    # did not touch it, even though a changed test file triggers the full scan.
    complex_fn = (
        "\n\ndef classify(n: int) -> str:\n"
        "    if n < 0:\n        return 'negative'\n"
        "    if n == 0:\n        return 'zero'\n"
        "    if n < 10:\n        return 'small'\n"
        "    if n < 100:\n        return 'medium'\n"
        "    if n < 1000:\n        return 'large'\n"
        "    return 'huge'\n"
    )
    git("switch", "-q", "main", cwd=repo)
    (repo / "src" / "fixture.py").write_text(MODULE + complex_fn)
    commit_all(repo, "old debt on main")
    git("switch", "-q", "-c", "slice", cwd=repo)
    (repo / "tests" / "test_fixture.py").write_text(
        TEST + "\n\ndef test_add_zero():\n    assert add(0, 0) == 0\n"
    )
    result = run_verify(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "entries outside the diff are advisory" in result.stdout
    assert "classify" in result.stdout
    assert (repo / ".verify" / "crap-full.json").is_file()


@needs_tools
def test_exclude_globs_reach_poly_crap(repo: Path):
    complex_fn = (
        "\n\ndef classify(n: int) -> str:\n"
        "    if n < 0:\n        return 'negative'\n"
        "    if n == 0:\n        return 'zero'\n"
        "    if n < 10:\n        return 'small'\n"
        "    if n < 100:\n        return 'medium'\n"
        "    if n < 1000:\n        return 'large'\n"
        "    return 'huge'\n"
    )
    (repo / "factory.toml").write_text(
        "[factory]\nbase = 'main'\n[verify]\nexclude = ['vendor/*']\n"
    )
    (repo / "vendor").mkdir()
    (repo / "vendor" / "third.py").write_text(MODULE + complex_fn)
    (repo / "pyproject.toml").write_text(
        PYPROJECT.replace('source = ["src"]', 'source = ["src", "vendor"]')
    )
    commit_all(repo, "config and vendored file on the branch base")
    git("switch", "-q", "-c", "slice", cwd=repo)
    (repo / "vendor" / "third.py").write_text(MODULE + complex_fn + "\n\nX = 1\n")
    green_change(repo)
    result = run_verify(repo, BASE="feature")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "classify" not in result.stdout
