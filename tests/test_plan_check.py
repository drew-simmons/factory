import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "plan" / "scripts" / "plan-check.py"
spec = importlib.util.spec_from_file_location("plan_check", SCRIPT)
plan_check = importlib.util.module_from_spec(spec)
sys.modules["plan_check"] = plan_check
spec.loader.exec_module(plan_check)


def slice_block(
    id_: str,
    blocked: str,
    branch: str,
    parent: str,
    *,
    requirements: str = "R1",
    acceptance: int = 1,
    tracker: str = "./issues/x.md",
) -> str:
    checks = "".join(f"  - [ ] check {i}\n" for i in range(acceptance))
    return (
        f"### {id_} Do the thing {id_}\n\n"
        f"- Requirements: {requirements}\n"
        f"- Blocked by: {blocked}\n"
        f"- Branch: {branch}\n"
        f"- Parent: {parent}\n"
        f"- Delivers: something\n"
        f"- Acceptance:\n{checks}"
        f"- Tracker: {tracker}\n\n"
    )


def plan(slices: str, waves: list[list[str]] | None, base: str = "origin/main") -> str:
    head = f"# Feature plan\n\nSpec: ./spec.md\nBase: {base}\nTracker: local\n\n## Slices\n\n"
    tail = "## Notes\n\nnone\n"
    if waves is None:
        return head + slices + tail
    rows = ",\n".join(
        f'    {{ "id": {i}, "slices": [{", ".join(f"{chr(34)}{s}{chr(34)}" for s in w)}] }}'
        for i, w in enumerate(waves)
    )
    waves_md = f'## Waves\n\nText.\n\n```json\n{{\n  "waves": [\n{rows}\n  ]\n}}\n```\n\n'
    return head + slices + waves_md + tail


def run(tmp_path: Path, text: str, *flags: str, capsys) -> tuple[int, str, str]:
    path = tmp_path / "plan.md"
    path.write_text(text)
    code = plan_check.main(["plan-check.py", str(path), *flags])
    out = capsys.readouterr()
    return code, out.out, out.err


LINEAR = (
    slice_block("01", "none", "f/01-a", "origin/main")
    + slice_block("02", "01", "f/02-b", "f/01-a")
    + slice_block("03", "02", "f/03-c", "f/02-b")
)


def test_linear_stack_passes(tmp_path, capsys):
    code, out, _ = run(tmp_path, plan(LINEAR, [["01"], ["02"], ["03"]]), capsys=capsys)
    assert code == 0, out
    assert "3 slices, 3 waves, stack is linear" in out


def test_fork_passes(tmp_path, capsys):
    fork = (
        slice_block("01", "none", "f/01-a", "origin/main")
        + slice_block("02", "01", "f/02-b", "f/01-a")
        + slice_block("03", "01", "f/03-c", "f/01-a")
    )
    code, out, _ = run(tmp_path, plan(fork, [["01"], ["02", "03"]]), capsys=capsys)
    assert code == 0, out


def test_two_roots_in_one_wave_pass(tmp_path, capsys):
    roots = (
        slice_block("01", "none", "f/01-a", "origin/main")
        + slice_block("02", "none", "f/02-b", "origin/main")
        + slice_block("03", "01, 02", "f/03-c", "f/02-b")
    )
    # 03 is blocked by two independent chains: the report's slice 04 shape.
    code, out, _ = run(tmp_path, plan(roots, [["01", "02"], ["03"]]), capsys=capsys)
    assert code == 1
    assert "slice 03" in out
    assert "blocked by 01, which is not an ancestor of its Parent 02" in out
    assert "serialize them" in out


def test_diamond_from_the_report_fails(tmp_path, capsys):
    # 01 and 02 in parallel, 03 on 02, 04 blocked by 01 and 03 and stacked on 03.
    diamond = (
        slice_block("01", "none", "f/01-a", "origin/main")
        + slice_block("02", "none", "f/02-b", "origin/main")
        + slice_block("03", "02", "f/03-c", "f/02-b")
        + slice_block("04", "01, 03", "f/04-d", "f/03-c")
    )
    code, out, _ = run(tmp_path, plan(diamond, [["01", "02"], ["03"], ["04"]]), capsys=capsys)
    assert code == 1
    assert "slice 04" in out and "blocked by 01, which is not an ancestor" in out
    assert "slice 03" not in out


def test_serialized_chains_pass(tmp_path, capsys):
    # The fix for the diamond: 01 blocks 02, so 04's blockers are all ancestors.
    serialized = (
        slice_block("01", "none", "f/01-a", "origin/main")
        + slice_block("02", "01", "f/02-b", "f/01-a")
        + slice_block("03", "02", "f/03-c", "f/02-b")
        + slice_block("04", "01, 03", "f/04-d", "f/03-c")
    )
    code, out, _ = run(tmp_path, plan(serialized, [["01"], ["02"], ["03"], ["04"]]), capsys=capsys)
    assert code == 0, out


def test_parent_must_be_a_blocker(tmp_path, capsys):
    text = slice_block("01", "none", "f/01-a", "origin/main") + slice_block(
        "02", "none", "f/02-b", "f/01-a"
    )
    code, out, _ = run(tmp_path, plan(text, [["01"], ["02"]]), capsys=capsys)
    assert code == 1
    assert "01 is not in `Blocked by`" in out


def test_blocked_slice_on_the_base_fails(tmp_path, capsys):
    text = slice_block("01", "none", "f/01-a", "origin/main") + slice_block(
        "02", "01", "f/02-b", "origin/main"
    )
    code, out, _ = run(tmp_path, plan(text, [["01"], ["02"]]), capsys=capsys)
    assert code == 1
    assert "Parent is the base but the slice is blocked by 01" in out


def test_unknown_parent_fails(tmp_path, capsys):
    text = slice_block("01", "none", "f/01-a", "origin/main") + slice_block(
        "02", "01", "f/02-b", "f/99-nope"
    )
    code, out, _ = run(tmp_path, plan(text, [["01"], ["02"]]), capsys=capsys)
    assert code == 1
    assert "Parent `f/99-nope` is neither the base" in out


def test_missing_fields_and_acceptance_are_named(tmp_path, capsys):
    text = "### 01 Bare\n\n- Blocked by: none\n- Branch: f/01\n- Parent: origin/main\n- Delivers: x\n\n"
    code, out, _ = run(tmp_path, plan(text, [["01"]]), capsys=capsys)
    assert code == 1
    assert "missing `- Requirements:`" in out
    assert "no acceptance checks" in out


def test_waves_must_agree_with_blockers(tmp_path, capsys):
    code, out, _ = run(tmp_path, plan(LINEAR, [["01", "02"], ["03"]]), capsys=capsys)
    assert code == 1
    assert "slice 02" in out and "in wave 0 with its blocker 01" in out
    code, out, _ = run(tmp_path, plan(LINEAR, [["01"], ["03"], ["02"]]), capsys=capsys)
    assert code == 1
    assert "slice 03" in out and "its blocker 02 is in wave 2" in out
    code, out, _ = run(tmp_path, plan(LINEAR, [["01"], ["02"]]), capsys=capsys)
    assert code == 1
    assert "slice 03" in out and "in no wave" in out
    code, out, _ = run(tmp_path, plan(LINEAR, [["01"], ["02", "03"], ["03"]]), capsys=capsys)
    assert code == 1
    assert "in wave 1 and wave 2" in out


def test_missing_waves_block_is_a_finding(tmp_path, capsys):
    code, out, _ = run(tmp_path, plan(LINEAR, None), capsys=capsys)
    assert code == 1
    assert "no waves block" in out


def test_unparseable_plan_exits_two(tmp_path, capsys):
    code, _, err = run(tmp_path, "# nothing here\n", capsys=capsys)
    assert code == 2
    assert "no slices" in err
    code, _, err = run(tmp_path, plan(LINEAR, None) + "```json\n{not json\n```\n", capsys=capsys)
    assert code == 2
    assert "waves" in err


def test_stack_prints_slices_in_order(tmp_path, capsys):
    code, out, _ = run(tmp_path, plan(LINEAR, [["01"], ["02"], ["03"]]), "--stack", capsys=capsys)
    assert code == 0
    assert out.splitlines() == [
        "01\tf/01-a\torigin/main",
        "02\tf/02-b\tf/01-a",
        "03\tf/03-c\tf/02-b",
    ]


def test_this_repositorys_plan_passes(capsys):
    code = plan_check.main(["plan-check.py", str(ROOT / "docs/specs/close-the-gaps/plan.md")])
    assert code == 0, capsys.readouterr().out


@pytest.mark.parametrize("bad", ["", "nonexistent.md"])
def test_bad_arguments_exit_two(tmp_path, bad, capsys):
    args = ["plan-check.py"] + ([str(tmp_path / bad)] if bad else [])
    assert plan_check.main(args) == 2
