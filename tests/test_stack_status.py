"""stack-status.sh against a stub gh that serves canned JSON."""

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "steward" / "scripts" / "stack-status.sh"

PLAN = """# f plan

Base: origin/main

## Slices

### 01 A

- Requirements: R1
- Blocked by: none
- Branch: f/01-a
- Parent: origin/main
- Acceptance:
  - [ ] a

### 02 B

- Requirements: R2
- Blocked by: 01
- Branch: f/02-b
- Parent: f/01-a
- Acceptance:
  - [ ] b

### 03 C

- Requirements: R3
- Blocked by: 02
- Branch: f/03-c
- Parent: f/02-b
- Acceptance:
  - [ ] c

## Waves

```json
{"waves": [{"id": 0, "slices": ["01"]}, {"id": 1, "slices": ["02"]}, {"id": 2, "slices": ["03"]}]}
```
"""

# gh is replaced by a script that answers `gh pr list --head <branch>` from
# list-<branch>.json and `gh pr view <n>` from view-<n>.json in $GH_STUB_DIR.
GH_STUB = """#!/bin/sh
case "$1 $2" in
  "pr list")
    while [ $# -gt 0 ]; do [ "$1" = "--head" ] && head=$2; shift; done
    f="$GH_STUB_DIR/list-$(printf '%s' "$head" | tr '/' '_').json"
    [ -f "$f" ] && jq -r '.[0].number // empty' "$f"
    ;;
  "pr view")
    cat "$GH_STUB_DIR/view-$3.json" ;;
  *) echo "stub gh: unexpected $*" >&2; exit 1 ;;
esac
"""


def view(state="OPEN", base="main", checks=None, mergeable="MERGEABLE", review="REVIEW_REQUIRED"):
    return {
        "state": state,
        "isDraft": False,
        "mergeable": mergeable,
        "reviewDecision": review,
        "baseRefName": base,
        "url": f"https://example/pr/{state}",
        "statusCheckRollup": checks if checks is not None else [],
    }


@pytest.fixture
def forge(tmp_path: Path):
    stub_dir = tmp_path / "stub"
    stub_dir.mkdir()
    gh = tmp_path / "bin" / "gh"
    gh.parent.mkdir()
    gh.write_text(GH_STUB)
    gh.chmod(0o755)
    plan = tmp_path / "plan.md"
    plan.write_text(PLAN)

    def set_pr(branch: str, number: int, **kw) -> None:
        (stub_dir / f"list-{branch.replace('/', '_')}.json").write_text(
            json.dumps([{"number": number}])
        )
        (stub_dir / f"view-{number}.json").write_text(json.dumps(view(**kw)))

    def run() -> list[str]:
        env = {
            **os.environ,
            "PATH": f"{gh.parent}:{os.environ['PATH']}",
            "GH_STUB_DIR": str(stub_dir),
        }
        result = subprocess.run(
            ["sh", str(SCRIPT), str(plan)], env=env, capture_output=True, text=True, check=False
        )
        assert result.returncode == 0, result.stderr
        return result.stdout.splitlines()

    return set_pr, run


def rows(lines: list[str]) -> dict[str, list[str]]:
    return {line.split("\t")[0]: line.split("\t") for line in lines[1:] if line[:2].isdigit()}


def test_frontier_is_the_lowest_unmerged_slice(forge):
    set_pr, run = forge
    set_pr("f/01-a", 11, state="MERGED")
    set_pr("f/02-b", 12, base="f/01-a", checks=[{"status": "COMPLETED", "conclusion": "SUCCESS"}])
    set_pr("f/03-c", 13, base="f/02-b", checks=[{"status": "IN_PROGRESS", "conclusion": None}])
    lines = run()
    table = rows(lines)
    assert table["01"][4] == "MERGED"
    assert table["02"][7] == "green"
    assert table["03"][7] == "pending"
    assert table["02"][9] == "yes"  # parent 01 merged
    assert table["03"][9] == "no"
    assert "frontier: 02" in lines
    # 02 still targets f/01-a although 01 merged: it needs a restack.
    assert "restack: 02" in lines


def test_red_checks_and_a_slice_without_a_pr(forge):
    set_pr, run = forge
    set_pr(
        "f/01-a",
        11,
        checks=[{"status": "COMPLETED", "conclusion": "FAILURE"}],
        mergeable="CONFLICTING",
    )
    lines = run()
    table = rows(lines)
    assert table["01"][7] == "red"
    assert table["01"][6] == "CONFLICTING"
    assert table["01"][9] == "base"
    assert table["02"][4] == "NONE"
    assert "frontier: 01" in lines
    assert "restack: none" in lines


def test_everything_merged_has_no_frontier(forge):
    set_pr, run = forge
    for branch, number in (("f/01-a", 11), ("f/02-b", 12), ("f/03-c", 13)):
        set_pr(branch, number, state="MERGED")
    lines = run()
    assert "frontier: none" in lines
    assert "restack: none" in lines


def test_restacked_slice_is_not_flagged_again(forge):
    set_pr, run = forge
    set_pr("f/01-a", 11, state="MERGED")
    set_pr("f/02-b", 12, base="main")  # already retargeted at the base
    lines = run()
    assert "frontier: 02" in lines
    assert "restack: none" in lines
