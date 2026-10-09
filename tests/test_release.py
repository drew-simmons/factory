import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "release.py"
spec = importlib.util.spec_from_file_location("release", SCRIPT)
release = importlib.util.module_from_spec(spec)
sys.modules["release"] = release
spec.loader.exec_module(release)

Version = release.Version
Commit = release.Commit

CHANGELOG = """# Changelog

## Unreleased

- existing bullet

## 0.1.0 (2026-10-08)

First release.

- one thing
"""

PYPROJECT = """[project]
name = "x"
version = "0.1.0"

[tool.decoy]
version = "9.9.9"
"""


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def commit(repo: Path, message: str) -> None:
    git("add", "-A", cwd=repo)
    git("commit", "-q", "--allow-empty", "-m", message, cwd=repo)


def manifest(version: str) -> str:
    return json.dumps({"name": "factory", "version": version, "license": "MIT"}, indent=2) + "\n"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "factory"
    (root / ".claude-plugin").mkdir(parents=True)
    git("init", "-q", "-b", "main", cwd=root)
    git("config", "commit.gpgsign", "false", cwd=root)
    git("config", "tag.gpgsign", "false", cwd=root)
    git("config", "user.name", "t", cwd=root)
    git("config", "user.email", "t@t", cwd=root)
    (root / ".claude-plugin" / "plugin.json").write_text(manifest("0.1.0"))
    (root / "plugin.json").write_text(manifest("0.1.0"))
    (root / "pyproject.toml").write_text(PYPROJECT)
    (root / "CHANGELOG.md").write_text(CHANGELOG)
    commit(root, "chore: initial commit")
    git("tag", "v0.1.0", cwd=root)
    return root


def run(root: Path, *argv: str) -> int:
    return release.main(["--root", str(root), *argv])


@pytest.mark.parametrize(
    ("subject", "body", "kind"),
    [
        ("feat: x", "", "minor"),
        ("fix(scope): y", "", "patch"),
        ("feat!: z", "", "major"),
        ("refactor: q", "BREAKING CHANGE: api", "major"),
        ("refactor: q", "BREAKING-CHANGE: api", "major"),
        ("chore(release): v0.2.0", "", None),
        ("ci: x", "", None),
        ("docs: x", "", None),
        ("not conventional", "", None),
    ],
)
def test_bump_kind_classification(subject, body, kind):
    assert Commit(subject, body).bump_kind() == kind


def test_version_bump_rules():
    assert Version(0, 1, 0).bump("major") == Version(0, 2, 0)
    assert Version(1, 2, 3).bump("major") == Version(2, 0, 0)
    assert Version(1, 2, 3).bump("minor") == Version(1, 3, 0)
    assert Version(1, 2, 3).bump("patch") == Version(1, 2, 4)
    assert str(Version.parse("v1.2.3")) == "1.2.3"
    with pytest.raises(release.ReleaseError):
        Version.parse("1.2")
    with pytest.raises(release.ReleaseError):
        Version(0, 1, 0).bump("huge")


def test_classify_takes_strongest_kind():
    commits = [Commit("chore: a"), Commit("fix: b"), Commit("feat: c")]
    assert release.classify(commits) == "minor"
    assert release.classify([Commit("feat: c"), Commit("fix!: b")]) == "major"
    assert release.classify([]) is None


def test_next_reports_minor_after_feat(repo: Path, capsys):
    commit(repo, "feat: thing")
    assert run(repo, "next") == 0
    assert capsys.readouterr().out == "0.2.0\n"
    assert run(repo, "next", "--json") == 0
    report = json.loads(capsys.readouterr().out)
    assert report == {
        "current": "0.1.0",
        "tag": "v0.1.0",
        "bump": "minor",
        "next": "0.2.0",
        "commits": 1,
    }


def test_next_without_tag_falls_back_to_file_version(repo: Path, capsys):
    git("tag", "-d", "v0.1.0", cwd=repo)
    commit(repo, "fix: x")
    assert run(repo, "next", "--json") == 0
    report = json.loads(capsys.readouterr().out)
    assert report["tag"] is None
    assert report["next"] == "0.1.1"
    assert report["commits"] == 2


def test_next_prints_nothing_for_non_release_commits(repo: Path, capsys):
    commit(repo, "ci: x")
    commit(repo, "chore(release): v0.1.0")
    assert run(repo, "next") == 0
    assert capsys.readouterr().out == ""


def test_next_refuses_tag_and_file_mismatch(repo: Path, capsys):
    commit(repo, "feat: x")
    git("tag", "v0.3.0", cwd=repo)
    assert run(repo, "next") == 2
    err = capsys.readouterr().err
    assert "0.1.0" in err
    assert "v0.3.0" in err


def test_next_refuses_disagreeing_files(repo: Path, capsys):
    (repo / "plugin.json").write_text(manifest("0.1.1"))
    assert run(repo, "next") == 2
    assert "disagree" in capsys.readouterr().err


def test_release_changelog_keeps_existing_bullets():
    out = release.release_changelog(CHANGELOG, Version(0, 2, 0), "2026-10-09", ["- nope"])
    assert out.startswith(
        "# Changelog\n\n## Unreleased\n\n## 0.2.0 (2026-10-09)\n\n- existing bullet\n\n"
    )
    assert out.endswith(CHANGELOG[CHANGELOG.index("## 0.1.0") :])
    assert "nope" not in out


def test_release_changelog_generates_bullets_when_empty():
    commits = [
        Commit("fix(verify): first thing — with a dash"),
        Commit("feat: " + "long word " * 12),
        Commit("ci: skipped"),
    ]
    fallback = release.bullets_from_commits(commits)
    text = "# Changelog\n\n## Unreleased\n"
    out = release.release_changelog(text, Version(0, 2, 0), "2026-10-09", fallback)
    body = out.split("## 0.2.0 (2026-10-09)\n\n", 1)[1]
    lines = body.splitlines()
    assert lines[0] == "- verify: first thing, with a dash"
    assert lines[1].startswith("- long word")
    assert all(len(line) <= 80 for line in lines)
    assert "skipped" not in out
    assert out.endswith("\n") and not out.endswith("\n\n")


def test_release_changelog_requires_unreleased_heading_and_content():
    with pytest.raises(release.ReleaseError):
        release.release_changelog("# Changelog\n", Version(0, 2, 0), "d", [])
    with pytest.raises(release.ReleaseError):
        release.release_changelog("# Changelog\n\n## Unreleased\n", Version(0, 2, 0), "d", [])


def test_set_json_version_changes_one_line():
    before = manifest("0.1.0")
    after = release.set_json_version(before, Version(0, 2, 0))
    changed = [(a, b) for a, b in zip(before.splitlines(), after.splitlines()) if a != b]
    assert changed == [('  "version": "0.1.0",', '  "version": "0.2.0",')]
    assert after.endswith("\n")
    assert json.loads(after)["version"] == "0.2.0"
    with pytest.raises(release.ReleaseError):
        release.set_json_version("{}\n", Version(0, 2, 0))


def test_set_toml_version_only_touches_project_table():
    after = release.set_toml_version(PYPROJECT, Version(0, 2, 0))
    assert 'version = "0.2.0"' in after
    assert 'version = "9.9.9"' in after
    assert release.read_toml_version(after) == "0.2.0"
    with pytest.raises(release.ReleaseError):
        release.set_toml_version('[tool.decoy]\nversion = "1.0.0"\n', Version(0, 2, 0))


def test_bump_rewrites_files_and_changelog(repo: Path, capsys):
    commit(repo, "feat: thing")
    assert run(repo, "bump", "0.2.0", "--date", "2026-10-09") == 0
    assert "pyproject.toml: 0.1.0 -> 0.2.0" in capsys.readouterr().out
    assert release.current_version(repo) == Version(0, 2, 0)
    assert json.loads((repo / "plugin.json").read_text())["version"] == "0.2.0"
    text = (repo / "CHANGELOG.md").read_text()
    assert "## Unreleased\n\n## 0.2.0 (2026-10-09)\n\n- existing bullet\n\n## 0.1.0" in text


def test_bump_refuses_non_increasing_version(repo: Path, capsys):
    assert run(repo, "bump", "0.1.0") == 2
    assert "not newer" in capsys.readouterr().err
    assert release.current_version(repo) == Version(0, 1, 0)


def test_notes_prints_section_body_only(repo: Path, capsys):
    assert run(repo, "notes", "0.1.0") == 0
    assert capsys.readouterr().out == "First release.\n\n- one thing\n"
    assert run(repo, "notes", "9.9.9") == 2


def test_release_commit_alone_yields_no_bump(repo: Path, capsys):
    commit(repo, "feat: thing")
    run(repo, "bump", "0.2.0", "--date", "2026-10-09")
    capsys.readouterr()
    commit(repo, "chore(release): v0.2.0")
    git("tag", "v0.2.0", cwd=repo)
    assert run(repo, "next") == 0
    assert capsys.readouterr().out == ""
    assert run(repo, "notes", "0.2.0") == 0
    assert capsys.readouterr().out == "- existing bullet\n"
