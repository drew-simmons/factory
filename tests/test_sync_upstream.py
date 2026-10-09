import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "sync-upstream.py"
spec = importlib.util.spec_from_file_location("sync_upstream", SCRIPT)
sync = importlib.util.module_from_spec(spec)
sys.modules["sync_upstream"] = sync
spec.loader.exec_module(sync)


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def commit_all(repo: Path, message: str) -> str:
    git("add", "-A", cwd=repo)
    git("commit", "-q", "-m", message, cwd=repo)
    return git("rev-parse", "HEAD", cwd=repo).strip()


@pytest.fixture
def upstream(tmp_path: Path) -> Path:
    repo = tmp_path / "upstream-repo"
    repo.mkdir()
    git("init", "-q", "-b", "main", cwd=repo)
    git("config", "uploadpack.allowAnySHA1InWant", "true", cwd=repo)
    git("config", "commit.gpgsign", "false", cwd=repo)
    git("config", "tag.gpgsign", "false", cwd=repo)
    git("config", "user.name", "t", cwd=repo)
    git("config", "user.email", "t@t", cwd=repo)
    (repo / "LICENSE").write_text("MIT License\n")
    skill = repo / "skills" / "engineering" / "tdd"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: tdd\n---\nred green\n")
    (skill / "tests.md").write_text("what a good test is\n")
    (repo / "playbooks").mkdir()
    (repo / "playbooks" / "pr.md").write_text("open a pr\n")
    commit_all(repo, "v1")
    git("tag", "v1.0.0", cwd=repo)
    return repo


@pytest.fixture
def project(tmp_path: Path, upstream: Path) -> Path:
    root = tmp_path / "factory"
    (root / "upstream").mkdir(parents=True)
    manifest = {
        "version": 1,
        "entries": {
            "upstream-repo/tdd": {
                "repo": str(upstream),
                "ref": "v1.0.0",
                "resolved": "",
                "paths": ["skills/engineering/tdd"],
                "license": "MIT",
                "licensePath": "LICENSE",
                "hash": "",
                "why": "test",
            },
            "upstream-repo/playbooks": {
                "repo": str(upstream),
                "ref": "main",
                "resolved": "",
                "paths": ["playbooks/pr.md"],
                "license": "MIT",
                "licensePath": "LICENSE",
                "hash": "",
                "why": "test",
            },
        },
    }
    (root / "upstream" / "upstream.json").write_text(json.dumps(manifest))
    return root


def run(root: Path, *argv: str) -> int:
    return sync.main(["--root", str(root), *argv])


def test_repo_slug_variants():
    assert sync.repo_slug("mattpocock/skills") == "mattpocock-skills"
    assert sync.repo_slug("https://github.com/cursor/plugins.git") == "cursor-plugins"
    assert sync.repo_slug("/tmp/x/upstream-repo") == "x-upstream-repo"


def test_update_vendors_files_and_pins_sha(project: Path, upstream: Path, capsys):
    assert run(project, "update", "--force") == 0
    vendored = next(p for p in (project / "upstream").iterdir() if p.is_dir())
    assert (vendored / "skills" / "engineering" / "tdd" / "SKILL.md").read_text().startswith("---")
    assert (vendored / "skills" / "engineering" / "tdd" / "tests.md").exists()
    assert (vendored / "playbooks" / "pr.md").exists()
    assert (vendored / "LICENSE").read_text() == "MIT License\n"
    manifest = json.loads((project / "upstream" / "upstream.json").read_text())
    tdd = manifest["entries"]["upstream-repo/tdd"]
    assert tdd["resolved"] == git("rev-parse", "v1.0.0^{commit}", cwd=upstream).strip()
    assert tdd["hash"].startswith("sha256:")
    assert (project / "THIRD_PARTY_NOTICES.md").read_text().count("MIT License") == 1
    assert "chore(upstream): bump upstream-repo/tdd" in capsys.readouterr().out


def test_verify_passes_after_update_and_detects_hand_edits(project: Path, capsys):
    run(project, "update", "--force")
    assert run(project, "verify") == 0
    vendored = next(p for p in (project / "upstream").iterdir() if p.is_dir())
    skill = vendored / "skills" / "engineering" / "tdd" / "SKILL.md"
    skill.write_text(skill.read_text() + "edited\n")
    assert run(project, "verify") == 1
    assert "content changed" in capsys.readouterr().out
    assert run(project, "update") == 2


def test_verify_detects_orphans_and_stale_notices(project: Path, capsys):
    run(project, "update", "--force")
    vendored = next(p for p in (project / "upstream").iterdir() if p.is_dir())
    (vendored / "stray.md").write_text("x\n")
    assert run(project, "verify") == 1
    out = capsys.readouterr().out
    assert "orphan" in out
    (vendored / "stray.md").unlink()
    (project / "THIRD_PARTY_NOTICES.md").write_text("stale\n")
    assert run(project, "verify") == 1
    assert "stale" in capsys.readouterr().out
    assert run(project, "notices") == 0
    assert run(project, "verify") == 0


def test_check_reports_behind_and_newer_tag(project: Path, upstream: Path, capsys):
    run(project, "update", "--force")
    assert run(project, "check") == 0
    assert "current" in capsys.readouterr().out
    (upstream / "playbooks" / "pr.md").write_text("open a better pr\n")
    commit_all(upstream, "v2")
    git("tag", "v1.1.0", cwd=upstream)
    assert run(project, "check", "--json") == 0
    rows = {r["entry"]: r for r in json.loads(capsys.readouterr().out)}
    assert rows["upstream-repo/playbooks"]["status"] == "behind"
    assert rows["upstream-repo/tdd"]["status"] == "tag-available"
    assert rows["upstream-repo/tdd"]["newerTags"] == ["v1.1.0"]
    assert run(project, "check", "--fail-if-behind") == 1


def test_diff_and_update_apply_upstream_change(project: Path, upstream: Path, capsys):
    run(project, "update", "--force")
    (upstream / "playbooks" / "pr.md").write_text("open a better pr\n")
    commit_all(upstream, "v2")
    assert run(project, "diff", "upstream-repo/playbooks") == 0
    out = capsys.readouterr().out
    assert "-open a pr" in out
    assert "+open a better pr" in out
    assert run(project, "update", "upstream-repo/playbooks") == 0
    vendored = next(p for p in (project / "upstream").iterdir() if p.is_dir())
    assert (vendored / "playbooks" / "pr.md").read_text() == "open a better pr\n"
    assert run(project, "verify") == 0


def test_update_with_ref_moves_tag_pin(project: Path, upstream: Path):
    run(project, "update", "--force")
    (upstream / "skills" / "engineering" / "tdd" / "SKILL.md").write_text("---\nname: tdd\n---\nnew\n")
    commit_all(upstream, "v2")
    git("tag", "v2.0.0", cwd=upstream)
    assert run(project, "update", "upstream-repo/tdd", "--ref", "v2.0.0") == 0
    manifest = json.loads((project / "upstream" / "upstream.json").read_text())
    assert manifest["entries"]["upstream-repo/tdd"]["ref"] == "v2.0.0"
    assert run(project, "verify") == 0


def test_unknown_entry_exits_two(project: Path, capsys):
    assert run(project, "diff", "nope") == 2
    assert "unknown entries" in capsys.readouterr().err
