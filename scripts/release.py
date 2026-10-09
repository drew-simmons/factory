#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Cut releases from conventional commits.

Commands:
  next  [--json]              print the next version, or nothing when no release is due
  bump  <version> [--date D]  rewrite the version files and CHANGELOG.md
  notes <version>             print the CHANGELOG.md section body for <version>

The version is read from the plugin manifests and pyproject.toml, which must
agree with each other and with the last v* tag. feat bumps minor, fix bumps
patch, a `!` or a BREAKING CHANGE footer bumps major (minor while the major
is 0). Any other commit type does not release, so the release commit itself
never triggers another release. uv.lock is left to `uv lock`.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

VERSION_FILES = (
    Path(".claude-plugin") / "plugin.json",
    Path("plugin.json"),
    Path("pyproject.toml"),
)
CHANGELOG = Path("CHANGELOG.md")
TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
SUBJECT = re.compile(r"^(?P<type>[a-z]+)(?:\((?P<scope>[^)]*)\))?(?P<bang>!)?: (?P<desc>.+)$")
BREAKING = re.compile(r"^BREAKING[ -]CHANGE:", re.MULTILINE)
JSON_VERSION = re.compile(r'^(\s*"version": ")([^"]+)(")', re.MULTILINE)
TOML_VERSION = re.compile(r'^version = "([^"]+)"$')
HEADING = re.compile(r"^## ", re.MULTILINE)
UNRELEASED = re.compile(r"^## Unreleased[ \t]*$", re.MULTILINE)
RANK = {"patch": 1, "minor": 2, "major": 3}
RELEASING = {"feat": "minor", "fix": "patch"}
WIDTH = 80


class ReleaseError(Exception):
    """A command could not complete."""


@dataclass(frozen=True, order=True)
class Version:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, text: str) -> Version:
        match = TAG.match(text if text.startswith("v") else f"v{text}")
        if not match:
            raise ReleaseError(f"not a semver version: {text!r}")
        return cls(*(int(part) for part in match.groups()))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def bump(self, kind: str) -> Version:
        if kind == "major" and self.major == 0:
            kind = "minor"
        if kind == "major":
            return Version(self.major + 1, 0, 0)
        if kind == "minor":
            return Version(self.major, self.minor + 1, 0)
        if kind == "patch":
            return Version(self.major, self.minor, self.patch + 1)
        raise ReleaseError(f"unknown bump kind: {kind!r}")


@dataclass(frozen=True)
class Commit:
    subject: str
    body: str = ""

    def parts(self) -> re.Match[str] | None:
        return SUBJECT.match(self.subject)

    def bump_kind(self) -> str | None:
        match = self.parts()
        if not match:
            return None
        if match["bang"] or BREAKING.search(self.body):
            return "major"
        return RELEASING.get(match["type"])


def classify(commits: list[Commit]) -> str | None:
    kinds = [kind for kind in (c.bump_kind() for c in commits) if kind]
    return max(kinds, key=RANK.__getitem__) if kinds else None


def git(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise ReleaseError(f"git {' '.join(args)} failed:\n{result.stderr.strip()}")
    return result.stdout


def last_tag(root: Path) -> str | None:
    out = git("tag", "--list", "v[0-9]*", "--merged", "HEAD", cwd=root)
    tags = [t for t in out.split() if TAG.match(t)]
    return max(tags, key=Version.parse) if tags else None


def commits_since(root: Path, tag: str | None) -> list[Commit]:
    span = f"{tag}..HEAD" if tag else "HEAD"
    out = git("log", "--reverse", "--format=%B%x1e", span, cwd=root)
    commits = []
    for record in out.split("\x1e"):
        lines = record.strip().splitlines()
        if lines:
            commits.append(Commit(lines[0].strip(), "\n".join(lines[1:])))
    return commits


def project_lines(text: str) -> list[tuple[int, str]]:
    """(index, line) for every line inside the [project] table of a pyproject.toml."""
    inside = False
    found = []
    for index, line in enumerate(text.splitlines()):
        if line.startswith("["):
            inside = line.strip() == "[project]"
        elif inside:
            found.append((index, line))
    return found


def read_json_version(text: str) -> str:
    match = JSON_VERSION.search(text)
    if not match:
        raise ReleaseError("no version field in JSON manifest")
    return match.group(2)


def read_toml_version(text: str) -> str:
    for _, line in project_lines(text):
        match = TOML_VERSION.match(line)
        if match:
            return match.group(1)
    raise ReleaseError("no version under [project] in pyproject.toml")


def set_json_version(text: str, version: Version) -> str:
    read_json_version(text)
    new = JSON_VERSION.sub(rf"\g<1>{version}\g<3>", text, count=1)
    json.loads(new)
    return new


def set_toml_version(text: str, version: Version) -> str:
    lines = text.splitlines(keepends=True)
    for index, line in project_lines(text):
        if TOML_VERSION.match(line):
            lines[index] = f'version = "{version}"\n'
            return "".join(lines)
    raise ReleaseError("no version under [project] in pyproject.toml")


def read_version(path: Path, text: str) -> str:
    return read_json_version(text) if path.suffix == ".json" else read_toml_version(text)


def set_version(path: Path, text: str, version: Version) -> str:
    if path.suffix == ".json":
        return set_json_version(text, version)
    return set_toml_version(text, version)


def current_version(root: Path) -> Version:
    found = {path: read_version(path, (root / path).read_text()) for path in VERSION_FILES}
    if len(set(found.values())) != 1:
        listing = ", ".join(f"{p}={v}" for p, v in found.items())
        raise ReleaseError(f"version files disagree: {listing}")
    return Version.parse(next(iter(found.values())))


def plain_punctuation(text: str) -> str:
    return re.sub(r"\s*[—–]\s*", ", ", text)


def bullets_from_commits(commits: list[Commit]) -> list[str]:
    bullets = []
    for commit in commits:
        match = commit.parts()
        if not match or not commit.bump_kind():
            continue
        line = f"{match['scope']}: {match['desc']}" if match["scope"] else match["desc"]
        bullets.append(
            textwrap.fill(
                plain_punctuation(line), WIDTH, initial_indent="- ", subsequent_indent="  "
            )
        )
    return bullets


def section_span(text: str, heading_start: int) -> tuple[int, int]:
    """Return (body_start, body_end) for the section whose heading starts at heading_start."""
    body_start = text.index("\n", heading_start) + 1
    following = HEADING.search(text, body_start)
    return body_start, following.start() if following else len(text)


def release_changelog(text: str, version: Version, date: str, fallback: list[str]) -> str:
    heading = UNRELEASED.search(text)
    if not heading:
        raise ReleaseError("CHANGELOG.md has no '## Unreleased' heading")
    body_start, body_end = section_span(text, heading.start())
    body = text[body_start:body_end].strip()
    if not any(line.startswith("- ") for line in body.splitlines()):
        body = "\n".join(fallback)
    if not body:
        raise ReleaseError("nothing to release: Unreleased is empty and no commit qualifies")
    section = f"## Unreleased\n\n## {version} ({date})\n\n{body}\n"
    rest = text[body_end:]
    if rest:
        section += "\n"
    return text[: heading.start()] + section + rest


def changelog_section(text: str, version: Version) -> str:
    heading = re.search(rf"^## {re.escape(str(version))} \(", text, re.MULTILINE)
    if not heading:
        raise ReleaseError(f"CHANGELOG.md has no section for {version}")
    body_start, body_end = section_span(text, heading.start())
    return text[body_start:body_end].strip() + "\n"


def cmd_next(root: Path, args: argparse.Namespace) -> int:
    tag = last_tag(root)
    current = current_version(root)
    if tag and Version.parse(tag) != current:
        raise ReleaseError(f"version files say {current} but the last tag is {tag}")
    commits = commits_since(root, tag)
    kind = classify(commits)
    nxt = current.bump(kind) if kind else None
    if args.json:
        report = {
            "current": str(current),
            "tag": tag,
            "bump": kind,
            "next": str(nxt) if nxt else None,
            "commits": len(commits),
        }
        print(json.dumps(report, indent=2))
    elif nxt:
        print(nxt)
    return 0


def cmd_bump(root: Path, args: argparse.Namespace) -> int:
    target = Version.parse(args.version)
    current = current_version(root)
    if target <= current:
        raise ReleaseError(f"{target} is not newer than {current}")
    changelog = root / CHANGELOG
    fallback = bullets_from_commits(commits_since(root, last_tag(root)))
    new_changelog = release_changelog(changelog.read_text(), target, args.date, fallback)
    for path in VERSION_FILES:
        file = root / path
        file.write_text(set_version(path, file.read_text(), target))
        print(f"{path}: {current} -> {target}")
    changelog.write_text(new_changelog)
    print(f"{CHANGELOG}: released {target} ({args.date})")
    return 0


def cmd_notes(root: Path, args: argparse.Namespace) -> int:
    print(changelog_section((root / CHANGELOG).read_text(), Version.parse(args.version)), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    sub = parser.add_subparsers(dest="command", required=True)

    nxt = sub.add_parser("next", help="print the next version, or nothing when no release is due")
    nxt.add_argument("--json", action="store_true")
    nxt.set_defaults(func=cmd_next)

    bump = sub.add_parser("bump", help="rewrite the version files and CHANGELOG.md")
    bump.add_argument("version")
    bump.add_argument("--date", default=datetime.datetime.now(tz=datetime.UTC).date().isoformat())
    bump.set_defaults(func=cmd_bump)

    notes = sub.add_parser("notes", help="print the CHANGELOG.md section body for a version")
    notes.add_argument("version")
    notes.set_defaults(func=cmd_notes)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args.root, args)
    except ReleaseError as error:
        print(f"release: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
