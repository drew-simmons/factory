#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Vendor upstream skill files under upstream/ and keep them pinned.

Commands:
  check  [entry...] [--json] [--fail-if-behind]
  diff   <entry> [--ref REF]
  update [entry...] [--ref REF] [--force]
  verify
  notices

The manifest upstream/upstream.json is owned by this script. Vendored files
are never edited by hand; `verify` fails when they are.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

MANIFEST = Path("upstream") / "upstream.json"
NOTICES = Path("THIRD_PARTY_NOTICES.md")
SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
SHA = re.compile(r"^[0-9a-f]{40}$")


class SyncError(Exception):
    """A command could not complete."""


@dataclass
class Entry:
    name: str
    repo: str
    ref: str
    resolved: str
    paths: list[str]
    license: str
    license_path: str
    hash: str
    why: str

    @classmethod
    def from_json(cls, name: str, data: dict) -> Entry:
        return cls(
            name=name,
            repo=data["repo"],
            ref=data["ref"],
            resolved=data.get("resolved", ""),
            paths=list(data["paths"]),
            license=data.get("license", ""),
            license_path=data.get("licensePath", "LICENSE"),
            hash=data.get("hash", ""),
            why=data.get("why", ""),
        )

    def to_json(self) -> dict:
        return {
            "repo": self.repo,
            "ref": self.ref,
            "resolved": self.resolved,
            "paths": self.paths,
            "license": self.license,
            "licensePath": self.license_path,
            "hash": self.hash,
            "why": self.why,
        }

    @property
    def url(self) -> str:
        return repo_url(self.repo)

    @property
    def slug(self) -> str:
        return repo_slug(self.repo)

    def vendor_dir(self, root: Path) -> Path:
        return root / "upstream" / self.slug


def repo_url(repo: str) -> str:
    if "://" in repo or repo.startswith(("/", ".")):
        return repo
    return f"https://github.com/{repo}.git"


def repo_slug(repo: str) -> str:
    name = repo.rstrip("/")
    for prefix in ("https://github.com/", "https://gitlab.com/"):
        name = name.removeprefix(prefix)
    name = name.removesuffix(".git")
    parts = [p for p in name.split("/") if p]
    return "-".join(parts[-2:])


def git(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SyncError(f"git {' '.join(args)} failed:\n{result.stderr.strip()}")
    return result.stdout


def load_manifest(root: Path) -> dict[str, Entry]:
    path = root / MANIFEST
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return {name: Entry.from_json(name, e) for name, e in data["entries"].items()}


def save_manifest(root: Path, entries: dict[str, Entry]) -> None:
    data = {"version": 1, "entries": {n: e.to_json() for n, e in sorted(entries.items())}}
    path = root / MANIFEST
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def select(entries: dict[str, Entry], names: list[str]) -> list[Entry]:
    if not names:
        return list(entries.values())
    missing = [n for n in names if n not in entries]
    if missing:
        raise SyncError(f"unknown entries: {', '.join(missing)}")
    return [entries[n] for n in names]


def ls_remote(url: str, pattern: str) -> dict[str, str]:
    out = git("ls-remote", url, pattern)
    refs: dict[str, str] = {}
    for line in out.splitlines():
        sha, _, ref = line.partition("\t")
        refs[ref] = sha
    return refs


def resolve(url: str, ref: str) -> str:
    if SHA.match(ref):
        return ref
    for candidate in (f"refs/tags/{ref}", f"refs/heads/{ref}"):
        # An exact pattern hides the peeled `^{}` line, so match with a glob.
        refs = ls_remote(url, f"{candidate}*")
        peeled = refs.get(f"{candidate}^{{}}")
        if peeled:
            return peeled
        if candidate in refs:
            return refs[candidate]
    raise SyncError(f"{ref} not found in {url}")


def semver_key(tag: str) -> tuple[int, int, int] | None:
    match = SEMVER.match(tag)
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def newer_tags(url: str, pinned: str) -> list[str]:
    pinned_key = semver_key(pinned)
    if pinned_key is None:
        return []
    refs = ls_remote(url, "refs/tags/*")
    tags = [r.removeprefix("refs/tags/") for r in refs if not r.endswith("^{}")]
    newer = [t for t in tags if (semver_key(t) or (0, 0, 0)) > pinned_key]
    return sorted(newer, key=lambda t: semver_key(t) or (0, 0, 0))


def fetch(url: str, want: str, ref: str, paths: list[str], dest: Path) -> str:
    """Sparse-checkout `paths` at commit `want` into `dest`; return the sha."""
    git("init", "-q", str(dest))
    git("remote", "add", "origin", url, cwd=dest)
    git("sparse-checkout", "set", "--no-cone", *[f"/{p}" for p in paths], cwd=dest)
    try:
        git("fetch", "-q", "--depth", "1", "--filter=blob:none", "origin", want, cwd=dest)
    except SyncError:
        git("fetch", "-q", "--depth", "1", "--filter=blob:none", "origin", ref, cwd=dest)
    git("checkout", "-q", "FETCH_HEAD", cwd=dest)
    sha = git("rev-parse", "HEAD", cwd=dest).strip()
    if sha != want:
        raise SyncError(f"fetched {sha} but wanted {want}; the ref moved, run update again")
    return sha


def walk_files(base: Path, rel: str) -> list[tuple[str, bytes]]:
    target = base / rel
    if target.is_file():
        return [(rel, target.read_bytes())]
    if not target.is_dir():
        return []
    files = []
    for path in sorted(target.rglob("*")):
        if path.is_file() and ".git" not in path.parts:
            files.append((path.relative_to(base).as_posix(), path.read_bytes()))
    return files


def entry_files(base: Path, entry: Entry) -> list[tuple[str, bytes]]:
    files: list[tuple[str, bytes]] = []
    for rel in entry.paths:
        files.extend(walk_files(base, rel))
    return sorted(files)


def content_hash(files: list[tuple[str, bytes]]) -> str:
    digest = hashlib.sha256()
    for rel, data in files:
        digest.update(rel.encode())
        digest.update(b"\0")
        digest.update(data)
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def copy_paths(src: Path, dest: Path, paths: list[str]) -> None:
    for rel in paths:
        source = src / rel
        target = dest / rel
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        if source.is_dir():
            shutil.copytree(source, target, ignore=shutil.ignore_patterns(".git"))
        elif source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        else:
            raise SyncError(f"{rel} does not exist upstream")


def copy_license(src: Path, entry: Entry, root: Path) -> None:
    source = src / entry.license_path
    if not source.is_file():
        raise SyncError(f"{entry.name}: licensePath {entry.license_path} not found upstream")
    dest = entry.vendor_dir(root) / "LICENSE"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)


def notices_text(root: Path, entries: dict[str, Entry]) -> str:
    lines = [
        "# Third-party notices",
        "",
        "Files under `upstream/` are copied verbatim from the repositories below.",
        "`scripts/sync-upstream.py` generates this file; do not edit it by hand.",
        "",
    ]
    by_repo: dict[str, list[Entry]] = {}
    for entry in sorted(entries.values(), key=lambda e: e.name):
        by_repo.setdefault(entry.repo, []).append(entry)
    for repo, group in sorted(by_repo.items()):
        first = group[0]
        lines.append(f"## {repo}")
        lines.append("")
        lines.append(f"- URL: {first.url}")
        lines.append(f"- License: {first.license}")
        for entry in group:
            lines.append(f"- `{entry.name}` at `{entry.ref}` ({entry.resolved[:12]}): {entry.why}")
            for rel in entry.paths:
                lines.append(f"  - `{rel}`")
        lines.append("")
        license_file = first.vendor_dir(root) / "LICENSE"
        if license_file.is_file():
            lines.append("```text")
            lines.append(license_file.read_text().rstrip())
            lines.append("```")
            lines.append("")
    return "\n".join(lines)


def write_notices(root: Path, entries: dict[str, Entry]) -> None:
    (root / NOTICES).write_text(notices_text(root, entries))


def claimed_files(root: Path, entries: dict[str, Entry]) -> set[Path]:
    claimed = {root / MANIFEST}
    for entry in entries.values():
        base = entry.vendor_dir(root)
        claimed.add(base / "LICENSE")
        for rel, _ in entry_files(base, entry):
            claimed.add(base / rel)
    return claimed


def entry_problems(root: Path, entry: Entry) -> list[str]:
    base = entry.vendor_dir(root)
    problems = [
        f"{entry.name}: missing {base / rel}" for rel in entry.paths if not (base / rel).exists()
    ]
    if content_hash(entry_files(base, entry)) != entry.hash:
        problems.append(f"{entry.name}: content changed; vendored files are read-only")
    if not (base / "LICENSE").is_file():
        problems.append(f"{entry.name}: missing {base / 'LICENSE'}")
    return problems


def orphan_problems(root: Path, entries: dict[str, Entry]) -> list[str]:
    upstream_dir = root / "upstream"
    if not upstream_dir.is_dir():
        return []
    claimed = claimed_files(root, entries)
    files = (p for p in sorted(upstream_dir.rglob("*")) if p.is_file())
    return [f"orphan file not claimed by any entry: {p}" for p in files if p not in claimed]


def notices_problems(root: Path, entries: dict[str, Entry]) -> list[str]:
    notices = root / NOTICES
    if notices.is_file() and notices.read_text() == notices_text(root, entries):
        return []
    return [f"{NOTICES} is stale; run `sync-upstream.py notices`"]


def verify_problems(root: Path, entries: dict[str, Entry]) -> list[str]:
    problems: list[str] = []
    for entry in entries.values():
        problems.extend(entry_problems(root, entry))
    problems.extend(orphan_problems(root, entries))
    problems.extend(notices_problems(root, entries))
    return problems


def cmd_verify(root: Path, _args: argparse.Namespace) -> int:
    entries = load_manifest(root)
    problems = verify_problems(root, entries)
    for problem in problems:
        print(problem)
    if not problems:
        print(f"verify: {len(entries)} entries match the manifest")
    return 1 if problems else 0


def check_entry(entry: Entry) -> dict:
    head = resolve(entry.url, entry.ref)
    tags = newer_tags(entry.url, entry.ref)
    if head != entry.resolved:
        status = "behind"
    elif tags:
        status = "tag-available"
    else:
        status = "current"
    return {
        "entry": entry.name,
        "ref": entry.ref,
        "pinned": entry.resolved,
        "head": head,
        "newerTags": tags,
        "status": status,
    }


def cmd_check(root: Path, args: argparse.Namespace) -> int:
    entries = load_manifest(root)
    rows = [check_entry(e) for e in select(entries, args.entries)]
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        for row in rows:
            tags = f" newest tag {row['newerTags'][-1]}" if row["newerTags"] else ""
            print(
                f"{row['status']:<14} {row['entry']:<40} {row['ref']} {row['pinned'][:12]} -> {row['head'][:12]}{tags}"
            )
    behind = [r for r in rows if r["status"] != "current"]
    return 1 if args.fail_if_behind and behind else 0


def cmd_diff(root: Path, args: argparse.Namespace) -> int:
    entries = load_manifest(root)
    entry = select(entries, [args.entry])[0]
    target_ref = args.ref or entry.ref
    target = resolve(entry.url, target_ref)
    print(f"{entry.name}: {entry.resolved[:12]} ({entry.ref}) -> {target[:12]} ({target_ref})")
    if target == entry.resolved:
        print("no upstream change")
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        before = Path(tmp) / "a"
        after = Path(tmp) / "b"
        fetch(entry.url, entry.resolved, entry.ref, entry.paths, before)
        fetch(entry.url, target, target_ref, entry.paths, after)
        for rel in entry.paths:
            result = subprocess.run(
                ["git", "diff", "--no-index", "--", str(before / rel), str(after / rel)],
                capture_output=True,
                text=True,
                check=False,
            )
            sys.stdout.write(result.stdout.replace(tmp, "upstream"))
    return 0


def update_entry(root: Path, entry: Entry, ref: str | None) -> bool:
    target_ref = ref or entry.ref
    target = resolve(entry.url, target_ref)
    if target == entry.resolved and ref is None and entry.hash:
        print(f"{entry.name}: already at {target[:12]}")
        return False
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "src"
        fetch(entry.url, target, target_ref, entry.paths + [entry.license_path], src)
        base = entry.vendor_dir(root)
        copy_paths(src, base, entry.paths)
        copy_license(src, entry, root)
    entry.ref = target_ref
    entry.resolved = target
    entry.hash = content_hash(entry_files(base, entry))
    print(f"chore(upstream): bump {entry.name} to {target_ref} ({target[:12]})")
    return True


def cmd_update(root: Path, args: argparse.Namespace) -> int:
    entries = load_manifest(root)
    if not args.force:
        problems = [p for p in verify_problems(root, entries) if "stale" not in p]
        if problems:
            print("\n".join(problems))
            print("update refused: fix the problems above or pass --force")
            return 2
    changed = False
    for entry in select(entries, args.entries):
        changed |= update_entry(root, entry, args.ref)
    save_manifest(root, entries)
    write_notices(root, entries)
    if not changed:
        print("nothing to update")
    return 0


def cmd_notices(root: Path, _args: argparse.Namespace) -> int:
    write_notices(root, load_manifest(root))
    print(f"wrote {NOTICES}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="report entries whose ref moved upstream")
    check.add_argument("entries", nargs="*")
    check.add_argument("--json", action="store_true")
    check.add_argument("--fail-if-behind", action="store_true")
    check.set_defaults(func=cmd_check)

    diff = sub.add_parser("diff", help="show the upstream change since the pinned commit")
    diff.add_argument("entry")
    diff.add_argument("--ref")
    diff.set_defaults(func=cmd_diff)

    update = sub.add_parser("update", help="fetch upstream and replace the vendored copy")
    update.add_argument("entries", nargs="*")
    update.add_argument("--ref")
    update.add_argument("--force", action="store_true")
    update.set_defaults(func=cmd_update)

    verify = sub.add_parser("verify", help="fail if vendored files differ from the manifest")
    verify.set_defaults(func=cmd_verify)

    notices = sub.add_parser("notices", help="regenerate THIRD_PARTY_NOTICES.md")
    notices.set_defaults(func=cmd_notices)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args.root, args)
    except SyncError as error:
        print(f"sync-upstream: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
