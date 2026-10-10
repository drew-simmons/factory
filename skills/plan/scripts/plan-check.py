#!/usr/bin/env python3
"""Check that a plan.md describes a stack an implementer can build.

Usage: python3 -I plan-check.py <spec_dir>/<slug>/plan.md [--stack]

Exit 0 when every slice has what it needs and the stack is linear, 1 with
one finding per line on stdout, 2 when the file cannot be parsed. With
--stack, print one line per slice in dependency order, `NN<TAB>branch<TAB>parent`,
for the skills that walk the stack.

The rules are the ones in skills/plan/SKILL.md that failed in simulation:
every blocker of a slice must be an ancestor of its Parent (a slice blocked
by two independent chains cannot be stacked), the Parent of a blocked slice
is one of its blockers, and the waves agree with the blockers.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

HEADING = re.compile(r"^### (\d\d) (.+?)\s*$")
FIELD = re.compile(r"^- ([A-Z][a-z ]+): *(.*?)\s*$")
CHECK = re.compile(r"^\s+- \[[ x]\] \S")
SLICE_ID = re.compile(r"\d\d")
REQUIRED_FIELDS = ("Requirements", "Branch", "Parent")


@dataclass
class Slice:
    id: str
    title: str
    line: int
    fields: dict[str, str] = field(default_factory=dict)
    acceptance: int = 0

    @property
    def blockers(self) -> list[str]:
        raw = self.fields.get("Blocked by", "")
        if not raw or raw.lower().startswith("none"):
            return []
        return SLICE_ID.findall(raw)

    @property
    def parent(self) -> str:
        return self.fields.get("Parent", "")

    def describe(self, message: str) -> str:
        return f"slice {self.id} ({self.title}, line {self.line}): {message}"


@dataclass
class Plan:
    base: str
    slices: list[Slice]
    waves: list[dict] | None

    @property
    def by_id(self) -> dict[str, Slice]:
        return {s.id: s for s in self.slices}

    @property
    def by_branch(self) -> dict[str, Slice]:
        return {s.fields["Branch"]: s for s in self.slices if s.fields.get("Branch")}

    @property
    def base_names(self) -> set[str]:
        return {self.base, self.base.removeprefix("origin/")} - {""}


class ParseError(Exception):
    pass


def split_fences(text: str) -> tuple[list[tuple[int, str]], list[str] | None]:
    """Prose lines with their numbers, and the body of the first ```json block."""
    prose: list[tuple[int, str]] = []
    first_json: list[str] | None = None
    collecting: list[str] | None = None
    in_fence = False
    for number, line in enumerate(text.splitlines(), start=1):
        if line.startswith("```"):
            if in_fence and collecting is not None:
                first_json, collecting = collecting, None
            elif not in_fence and line.strip() == "```json" and first_json is None:
                collecting = []
            in_fence = not in_fence
        elif in_fence:
            if collecting is not None:
                collecting.append(line)
        else:
            prose.append((number, line))
    return prose, first_json


def parse_slices(prose: list[tuple[int, str]]) -> tuple[str, list[Slice]]:
    base = ""
    slices: list[Slice] = []
    current: Slice | None = None
    for number, line in prose:
        heading = HEADING.match(line)
        if heading:
            current = Slice(heading.group(1), heading.group(2), number)
            slices.append(current)
        elif line.startswith("## "):
            current = None
        elif line.startswith("Base:") and not slices:
            base = line.split(":", 1)[1].strip()
        elif current is not None:
            parse_slice_line(current, line)
    return base, slices


def parse_slice_line(current: Slice, line: str) -> None:
    if CHECK.match(line):
        current.acceptance += 1
        return
    found = FIELD.match(line)
    if found:
        current.fields[found.group(1)] = found.group(2)


def parse_waves(block: list[str] | None) -> list[dict] | None:
    if block is None:
        return None
    try:
        return json.loads("\n".join(block))["waves"]
    except (json.JSONDecodeError, KeyError, TypeError) as err:
        raise ParseError(f"the json block does not hold a waves list: {err}") from err


def parse(text: str) -> Plan:
    prose, block = split_fences(text)
    base, slices = parse_slices(prose)
    if not slices:
        raise ParseError("no slices (headings of the form `### NN title`)")
    return Plan(base, slices, parse_waves(block))


def check_fields(plan: Plan) -> list[str]:
    findings: list[str] = []
    seen: set[str] = set()
    for s in plan.slices:
        if s.id in seen:
            findings.append(s.describe("duplicate id"))
        seen.add(s.id)
        for name in REQUIRED_FIELDS:
            if not s.fields.get(name):
                findings.append(s.describe(f"missing `- {name}:`"))
        if s.acceptance == 0:
            findings.append(
                s.describe("no acceptance checks (`- [ ] ...` items under `- Acceptance:`)")
            )
        if "Blocked by" not in s.fields:
            findings.append(s.describe("missing `- Blocked by:` (write `none` when there is none)"))
        findings.extend(check_blocker_ids(plan, s))
    return findings


def check_blocker_ids(plan: Plan, s: Slice) -> list[str]:
    findings = []
    for b in s.blockers:
        if b not in plan.by_id:
            findings.append(s.describe(f"blocked by unknown slice {b}"))
        elif b >= s.id:
            findings.append(
                s.describe(f"blocked by {b}, which is not an earlier slice; number blockers first")
            )
    return findings


def ancestors(plan: Plan, s: Slice) -> list[Slice]:
    """The slices below s in its stack, nearest first, following Parent."""
    by_branch = plan.by_branch
    chain: list[Slice] = []
    node = s
    while node.parent in by_branch:
        node = by_branch[node.parent]
        if node in chain or node is s:
            break
        chain.append(node)
    return chain


def check_stack(plan: Plan) -> list[str]:
    findings: list[str] = []
    for s in plan.slices:
        if s.parent:
            findings.extend(check_slice_parent(plan, s))
    return findings


def check_slice_parent(plan: Plan, s: Slice) -> list[str]:
    blockers = [plan.by_id[b] for b in s.blockers if b in plan.by_id]
    if s.parent in plan.base_names:
        if not blockers:
            return []
        ids = ", ".join(b.id for b in blockers)
        return [
            s.describe(
                f"Parent is the base but the slice is blocked by {ids}; "
                "stack it on the branch of the slice it is blocked by"
            )
        ]
    parent_slice = plan.by_branch.get(s.parent)
    if parent_slice is None:
        return [
            s.describe(
                f"Parent `{s.parent}` is neither the base `{plan.base}` nor another slice's Branch"
            )
        ]
    findings = []
    if parent_slice not in blockers:
        findings.append(
            s.describe(
                f"Parent is slice {parent_slice.id}'s branch, but {parent_slice.id} is not in `Blocked by`"
            )
        )
    chain = ancestors(plan, s)
    for b in blockers:
        if b not in chain:
            findings.append(
                s.describe(
                    f"blocked by {b.id}, which is not an ancestor of its Parent {parent_slice.id}; "
                    "a slice cannot stack on two chains, serialize them"
                )
            )
    return findings


def place_in_waves(plan: Plan) -> tuple[dict[str, int], list[str]]:
    """Map slice id to wave index; findings for unknown, repeated, or co-waved blockers."""
    findings: list[str] = []
    placed: dict[str, int] = {}
    for index, wave in enumerate(plan.waves or []):
        members = [str(m) for m in wave.get("slices", [])]
        for m in members:
            if m not in plan.by_id:
                findings.append(f"wave {index}: unknown slice {m}")
            elif m in placed:
                findings.append(plan.by_id[m].describe(f"in wave {placed[m]} and wave {index}"))
            else:
                placed[m] = index
        findings.extend(co_waved_blockers(plan, index, members))
    return placed, findings


def co_waved_blockers(plan: Plan, index: int, members: list[str]) -> list[str]:
    findings = []
    for m in members:
        if m not in plan.by_id:
            continue
        for b in plan.by_id[m].blockers:
            if b in members:
                findings.append(plan.by_id[m].describe(f"in wave {index} with its blocker {b}"))
    return findings


def check_waves(plan: Plan) -> list[str]:
    if plan.waves is None:
        return ['no waves block (a ```json fence holding {"waves": [...]})']
    placed, findings = place_in_waves(plan)
    for s in plan.slices:
        if s.id not in placed:
            findings.append(s.describe("in no wave"))
            continue
        for b in s.blockers:
            if b in placed and placed[b] >= placed[s.id]:
                findings.append(
                    s.describe(f"in wave {placed[s.id]} but its blocker {b} is in wave {placed[b]}")
                )
    return findings


def check(plan: Plan) -> list[str]:
    return check_fields(plan) + check_stack(plan) + check_waves(plan)


def stack(plan: Plan) -> str:
    rows = sorted(plan.slices, key=lambda s: s.id)
    return "\n".join(f"{s.id}\t{s.fields.get('Branch', '')}\t{s.parent}" for s in rows)


def load(argv: list[str]) -> tuple[Path, Plan]:
    args = [a for a in argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        raise ParseError("usage: plan-check.py <plan.md> [--stack]")
    path = Path(args[0])
    if not path.is_file():
        raise ParseError(f"{path} does not exist")
    try:
        return path, parse(path.read_text())
    except ParseError as err:
        raise ParseError(f"{path}: {err}") from err


def report(path: Path, plan: Plan) -> int:
    findings = check(plan)
    for finding in findings:
        print(f"plan-check: {path}: {finding}")
    if not findings:
        waves = len(plan.waves or [])
        print(f"plan-check: {path}: {len(plan.slices)} slices, {waves} waves, stack is linear")
    return 1 if findings else 0


def main(argv: list[str]) -> int:
    try:
        path, plan = load(argv)
    except ParseError as err:
        print(f"plan-check: {err}", file=sys.stderr)
        return 2
    if "--stack" in argv:
        print(stack(plan))
        return 0
    return report(path, plan)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
