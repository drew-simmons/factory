"""release-worktree.sh on a real worktree."""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "implement" / "scripts" / "release-worktree.sh"


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo = tmp_path / "main"
    repo.mkdir()
    git("init", "-q", "-b", "main", cwd=repo)
    for key, value in (("commit.gpgsign", "false"), ("user.name", "t"), ("user.email", "t@t")):
        git("config", key, value, cwd=repo)
    (repo / "README.md").write_text("x\n")
    (repo / ".gitignore").write_text(".verify/\n.factory/\n")
    git("add", "-A", cwd=repo)
    git("commit", "-q", "-m", "base", cwd=repo)
    return repo


def worktree(repo: Path, tmp_path: Path, branch: str = "feat/01-a") -> Path:
    path = tmp_path / "wt"
    git("worktree", "add", "-q", "-b", branch, str(path), "main", cwd=repo)
    return path


def release(repo: Path, path: Path, slice_id: str = "01") -> subprocess.CompletedProcess:
    return subprocess.run(
        ["sh", str(SCRIPT), str(path), slice_id],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def test_releases_a_committed_worktree_and_keeps_its_evidence(repo: Path, tmp_path: Path):
    wt = worktree(repo, tmp_path)
    (wt / "a.txt").write_text("a\n")
    git("add", "-A", cwd=wt)
    git("commit", "-q", "-m", "feat: a (01, R1)", cwd=wt)
    (wt / ".verify").mkdir()
    (wt / ".verify" / "summary.txt").write_text("verify: clean\n")
    (wt / ".verify" / "stop.log").write_text("hook ran\n")
    result = release(repo, wt)
    assert result.returncode == 0, result.stderr
    assert not wt.exists()
    assert (repo / ".verify" / "slices" / "01" / "summary.txt").read_text() == "verify: clean\n"
    assert (repo / ".verify" / "slices" / "01" / "stop.log").read_text() == "hook ran\n"
    assert "feat/01-a" in git("branch", "--list", "feat/01-a", cwd=repo)
    git("switch", "-q", "feat/01-a", cwd=repo)  # the branch is free to check out again


def test_keeps_a_worktree_with_no_commit(repo: Path, tmp_path: Path):
    wt = worktree(repo, tmp_path)
    result = release(repo, wt)
    assert result.returncode == 1
    assert "no commit of its own" in result.stderr
    assert wt.exists()


def test_keeps_a_worktree_with_uncommitted_changes(repo: Path, tmp_path: Path):
    wt = worktree(repo, tmp_path)
    (wt / "a.txt").write_text("a\n")
    git("add", "-A", cwd=wt)
    git("commit", "-q", "-m", "feat: a (01, R1)", cwd=wt)
    (wt / "b.txt").write_text("dirty\n")
    result = release(repo, wt)
    assert result.returncode == 1
    assert "uncommitted changes" in result.stderr
    assert wt.exists()


def test_rejects_a_directory_that_is_not_a_worktree(repo: Path, tmp_path: Path):
    other = tmp_path / "other"
    other.mkdir()
    result = release(repo, other)
    assert result.returncode == 2
    assert "is not a worktree" in result.stderr
