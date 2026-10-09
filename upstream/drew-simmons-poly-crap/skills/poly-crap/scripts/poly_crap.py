#!/usr/bin/env python3
"""poly-crap: scan any repository, or develop poly-crap itself.

Works in two modes, chosen automatically from the repository you are standing
in. Nothing is derived from where this file lives, so the skill behaves the
same installed per-project or globally.

  scan mode (any repository)
    check         report the binary, the detected stack, and coverage reports
    install       install the poly-crap binary (network; asks first)
    scan          run the scan, optionally gated
    baseline      write a baseline JSON to compare later runs against
    self-install  copy this skill into your global skills directory

  dev mode (only inside a poly-crap source checkout)
    build         cargo build --locked
    fixture       build the six-language fixture repo
    smoke         build, then run every scenario and assert the results
    dev-run       run the freshly built binary against the fixture

Only the standard library is used. Schema checks shell out to
`uvx check-jsonschema` and are skipped when uvx is missing.
"""

from __future__ import annotations

import argparse
import functools
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

INSTALLER = (
    "https://github.com/drew-simmons/poly-crap/releases/latest/download/"
    "poly-crap-installer.sh"
)

FIXTURE = Path(os.environ.get("POLY_CRAP_FIXTURE", "/tmp/poly-crap-fixture"))

# Marker file -> (label, command that writes the coverage report, report path).
# poly-crap reads reports; it never runs tests or converters, so these are
# printed as suggestions and never executed.
STACKS = [
    (
        "Cargo.toml",
        "Rust",
        "cargo llvm-cov --lcov --output-path coverage.lcov",
        "coverage.lcov",
    ),
    ("go.mod", "Go", "go test -coverprofile=coverage.out ./...", "coverage.out"),
    ("pom.xml", "Java (Maven)", "mvn verify", "target/site/jacoco/jacoco.xml"),
    (
        "build.gradle",
        "Java (Gradle)",
        "gradle test jacocoTestReport",
        "build/reports/jacoco/test/jacocoTestReport.xml",
    ),
    (
        "build.gradle.kts",
        "Java (Gradle)",
        "gradle test jacocoTestReport",
        "build/reports/jacoco/test/jacocoTestReport.xml",
    ),
    (
        "pyproject.toml",
        "Python",
        "coverage run -m pytest && coverage lcov -o coverage.lcov",
        "coverage.lcov",
    ),
    (
        "setup.py",
        "Python",
        "coverage run -m pytest && coverage lcov -o coverage.lcov",
        "coverage.lcov",
    ),
    (
        "package.json",
        "JavaScript / TypeScript",
        "npx c8 --reporter=lcov npm test",
        "coverage/lcov.info",
    ),
]

# Where coverage reports usually land. Checked in order; all hits are passed to
# poly-crap, which merges repeated --coverage flags and sniffs each format.
# Newer binaries search the same list themselves when no --coverage is given
# (DEFAULT_REPORT_LOCATIONS in src/coverage.rs — keep the two lists matching);
# passing explicit flags here keeps older binaries behaving the same.
COVERAGE_CANDIDATES = [
    "coverage.lcov",
    "lcov.info",
    "coverage/lcov.info",
    "coverage/coverage.lcov",
    "coverage.out",
    "coverage.xml",
    "coverage/cobertura-coverage.xml",
    "target/site/jacoco/jacoco.xml",
    "build/reports/jacoco/test/jacocoTestReport.xml",
]

EXIT_MEANING = {
    0: "the scan ran and no requested gate failed",
    1: "gate failed — a function is over the threshold, or a score regressed",
    2: "error — usage, input, parsing, coverage, or output failed",
}


def sh(cmd, **kw):
    # check=False throughout: every caller inspects returncode itself, and a
    # non-zero exit is usually the thing being asserted, not an error.
    return subprocess.run(cmd, capture_output=True, text=True, check=False, **kw)


@functools.cache
def git_toplevel() -> Path | None:
    """The git worktree root, or None when we are not inside one.

    Cached: the working directory cannot change mid-run, and this was being
    re-spawned three or four times per command. functools.cache sets the
    floor for this script at Python 3.9.
    """
    out = sh(["git", "rev-parse", "--show-toplevel"])
    return Path(out.stdout.strip()) if out.returncode == 0 else None


def repo_root() -> Path:
    """Repository root from git, falling back to the working directory.

    Deliberately not derived from __file__: the repo being worked on is the one
    you are standing in, however deep this script is installed.
    """
    return git_toplevel() or Path.cwd()


@functools.cache
def source_root() -> Path | None:
    """The repo root if it is a poly-crap source checkout, else None.

    Both markers are required. A repo that merely has a Cargo.toml is somebody
    else's Rust project, and dev mode there would build the wrong binary.
    """
    root = repo_root()
    cargo = root / "Cargo.toml"
    if not cargo.is_file() or not (root / "src" / "score.rs").is_file():
        return None
    if re.search(r'^name\s*=\s*"poly-crap"', cargo.read_text(), re.MULTILINE):
        return root
    return None


def find_binary() -> str | None:
    """Prefer poly-crap on PATH; fall back to a local debug/release build."""
    found = shutil.which("poly-crap")
    if found:
        return found
    root = repo_root()
    for candidate in ("target/release/poly-crap", "target/debug/poly-crap"):
        path = root / candidate
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    return None


def require_binary() -> str:
    binary = find_binary()
    if binary is None:
        sys.exit(
            "poly-crap not found on PATH.\n"
            "Install it with:  python3 <this-script> install\n"
            f"or by hand:      curl --proto '=https' --tlsv1.2 -LsSf {INSTALLER} | sh"
        )
    return binary


def detect_stacks(root: Path):
    return [s for s in STACKS if (root / s[0]).is_file()]


def detect_coverage(root: Path) -> list[Path]:
    return [root / c for c in COVERAGE_CANDIDATES if (root / c).is_file()]


def coverage_args(ns, root: Path) -> list[str]:
    """Flattened --coverage flags: explicit paths if given, else auto-detected.

    One spelling of the rule for both `scan` and `baseline`, which previously
    each carried their own copy with the condition inverted.
    """
    reports = [Path(c) for c in ns.coverage] if ns.coverage else detect_coverage(root)
    return [arg for r in reports for arg in ("--coverage", str(r))]


# ---------------------------------------------------------------- scan mode


def cmd_check(ns) -> int:
    root = repo_root()
    print(f"repository: {root}")
    # Not named `source`: that would shadow the source() accessor.
    checkout = source_root()
    print(f"mode:       {'dev (poly-crap source checkout)' if checkout else 'scan'}")

    binary = find_binary()
    if binary is None:
        print("poly-crap:  NOT FOUND — run the `install` subcommand")
    else:
        version = sh([binary, "--version"]).stdout.strip()
        print(f"poly-crap:  {binary} ({version})")

    stacks = detect_stacks(root)
    if not stacks:
        print("stack:      none recognised (poly-crap still scans by extension)")
    for marker, label, command, report in stacks:
        print(f"stack:      {label}  (found {marker})")
        print(f"            coverage: {command}  -> {report}")

    reports = detect_coverage(root)
    if reports:
        for r in reports:
            print(f"coverage:   {r.relative_to(root)}")
    else:
        print(
            "coverage:   none found — the scan will treat every function as 0% covered"
        )
    if checkout:
        print("dev:        `smoke` available (build + 51 assertions)")
    return 0 if binary else 1


def cmd_install(ns) -> int:
    binary = find_binary()
    if binary and not ns.force:
        print(f"poly-crap already installed at {binary}")
        return 0
    print(f"This downloads and runs the installer from:\n  {INSTALLER}")
    if not ns.yes:
        reply = input("Proceed? [y/N] ").strip().lower()
        if reply not in ("y", "yes"):
            print("aborted")
            return 1
    script = sh(["curl", "--proto", "=https", "--tlsv1.2", "-LsSf", INSTALLER])
    if script.returncode != 0:
        sys.exit(f"download failed: {script.stderr.strip()}")
    out = subprocess.run(["sh"], input=script.stdout, text=True, check=False)
    return out.returncode


def skill_root() -> Path:
    """The nearest ancestor directory holding SKILL.md.

    __file__ is the right basis here — we are locating the skill itself, not
    the repository under analysis. One invariant rather than a list of accepted
    layouts: `scripts/` and a flat install both satisfy it, and anything else
    fails loudly instead of installing a tree with no SKILL.md in it.
    """
    here = Path(__file__).resolve().parent
    for candidate in (here, *here.parents):
        if (candidate / "SKILL.md").is_file():
            return candidate
    sys.exit(f"no SKILL.md found in {here} or its parents; cannot locate the skill")


def cmd_self_install(ns) -> int:
    """Copy this skill directory to the global skills directory."""
    src = skill_root()
    dest = Path(ns.dest).expanduser()
    if dest.exists() and not ns.force:
        sys.exit(f"{dest} already exists; pass --force to overwrite")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.rmtree(dest)
    # Tool caches (rumdl, pytest, mypy) land inside the skill dir if anything
    # has ever run there; none of it belongs in an install.
    shutil.copytree(
        src,
        dest,
        ignore=shutil.ignore_patterns("__pycache__", ".*_cache", ".git", "*.pyc"),
    )
    rel = Path(__file__).resolve().relative_to(src)
    print(f"installed {sorted(p.name for p in dest.iterdir())} to {dest}")
    print(f"use it with:  python3 {dest / rel} check")
    return 0


def build_args(ns, root: Path) -> list[str]:
    args = ["--path", str(root)] + coverage_args(ns, root)
    for flag, value in (
        ("--diff-base", ns.diff_base),
        ("--baseline", ns.baseline),
        ("--format", ns.format),
        ("--output", ns.output),
    ):
        if value:
            args += [flag, value]
    # Separate from the loop above: 0.0 is a legal threshold but falsy.
    if ns.threshold is not None:
        args += ["--threshold", str(ns.threshold)]
    if ns.gate:
        args.append("--fail-regression" if ns.baseline else "--fail-above")
    return args + ns.extra


def cmd_scan(ns) -> int:
    root = repo_root()
    binary = require_binary()

    # poly-crap rejects these pairs itself with exit 2; catching them here gives
    # a clearer message than clap's.
    if ns.diff_base and ns.baseline:
        sys.exit("--diff-base cannot be combined with --baseline")
    if ns.diff_base and git_toplevel() is None:
        sys.exit("--diff-base needs a Git repository")

    args = build_args(ns, root)
    if "--coverage" not in args:
        print(
            "warning: no coverage report — every function counts as 0% "
            "covered (pass --coverage, or see the `check` subcommand)",
            file=sys.stderr,
        )

    print(f"$ {Path(binary).name} {' '.join(args)}\n", file=sys.stderr)
    # stdout is left attached so JSON stays clean and pipeable; poly-crap puts
    # its warnings on stderr, which must not be merged into the document.
    out = subprocess.run([binary, *args], check=False)
    note = EXIT_MEANING.get(out.returncode, "unknown")
    # Exit 0 without --gate says nothing about whether the report is clean:
    # poly-crap only fails the run when a gate was asked for.
    if out.returncode == 0 and not ns.gate:
        note += " (no gate requested — add --gate to fail on violations)"
    print(f"\nexit {out.returncode}: {note}", file=sys.stderr)
    return out.returncode


def cmd_baseline(ns) -> int:
    root = repo_root()
    binary = require_binary()
    args = [
        "--path",
        str(root),
        "--format",
        "json",
        "--output",
        ns.out,
    ] + coverage_args(ns, root)
    out = subprocess.run([binary, *args], check=False)
    if out.returncode == 2:
        return 2
    entries = json.loads(Path(ns.out).read_text())["entries"]
    print(f"wrote {ns.out} ({len(entries)} functions)")
    print(f"compare later with:  --baseline {ns.out} --gate")
    return 0


# ----------------------------------------------------------------- dev mode

# Fixture sources. Each language gets one high-complexity `risky` and one
# trivial `simple`, so a change to the tree-sitter rules in src/analysis.rs
# shows up as a complexity drift in exactly one row.
SOURCES = {
    "src/a.ts": """export function risky(a: number, b: number): string {
  if (a > 0) { if (b > 0) { return "both"; } }
  for (let i = 0; i < a; i++) { if (i % 2 === 0 && b > i) { return "loop"; } }
  return a > b ? "a" : "b";
}
export const simple = (x: number) => x + 1;
""",
    "src/b.py": """def risky(a, b):
    if a > 0:
        if b > 0:
            return "both"
    for i in range(a):
        if i % 2 == 0 and b > i:
            return "loop"
    try:
        return [x for x in range(a) if x > b]
    except ValueError:
        return None
def simple(x):
    return x + 1
""",
    "src/c.go": """package main
func Risky(a int, b int) string {
\tif a > 0 {
\t\tif b > 0 {
\t\t\treturn "both"
\t\t}
\t}
\tfor i := 0; i < a; i++ {
\t\tif i%2 == 0 && b > i {
\t\t\treturn "loop"
\t\t}
\t}
\tswitch a {
\tcase 1:
\t\treturn "one"
\tdefault:
\t\treturn "other"
\t}
}
func Simple(x int) int { return x + 1 }
""",
    "src/D.java": """public class D {
  public String risky(int a, int b) {
    if (a > 0) { if (b > 0) { return "both"; } }
    for (int i = 0; i < a; i++) { if (i % 2 == 0 && b > i) { return "loop"; } }
    try { return a > b ? "a" : "b"; } catch (Exception e) { return null; }
  }
  public int simple(int x) { return x + 1; }
}
""",
    "src/e.rs": """pub fn risky(a: i32, b: i32) -> String {
    if a > 0 { if b > 0 { return "both".to_string(); } }
    for i in 0..a { if i % 2 == 0 && b > i { return "loop".to_string(); } }
    match a { 1 => "one".to_string(), _ => "other".to_string() }
}
pub fn simple(x: i32) -> i32 { x + 1 }
""",
    "src/f.js": """export function risky(a, b) {
  if (a > 0) { if (b > 0) { return "both"; } }
  while (a-- > 0) { if (a % 2 === 0 || b > a) { return "loop"; } }
  return a > b ? "a" : "b";
}
""",
}

# The feature-branch edit: turns e.rs `simple` from CC=1 into CC=4. Used by both
# the --diff-base and the --baseline scenarios.
COMPLICATED_RS_SIMPLE = """pub fn simple(x: i32) -> i32 {
    if x > 0 { if x > 5 { return 5; } }
    if x < -1 { return -1; }
    x + 1
}
"""

# Set by dev_setup(), read through source() and bin_path() below.
_SOURCE: Path | None = None


def source() -> Path:
    """The poly-crap checkout root. Dev mode only; raises otherwise.

    An accessor rather than a bare Optional global because the two ways this
    leaks are both silent: `cwd=None` means "inherit the cwd", and `str(None)`
    is the literal path "None". Narrowing here turns a wrong-directory build or
    an exec of a file called None into a loud failure, and satisfies type
    checkers at the five call sites that would otherwise each need a guard.
    """
    if _SOURCE is None:
        raise RuntimeError(
            "dev_setup() has not run — a dev-mode path was reached in scan mode"
        )
    return _SOURCE


def bin_path() -> Path:
    """The freshly built binary, never whatever poly-crap is on PATH."""
    return source() / "target" / "debug" / "poly-crap"


def dev_setup() -> None:
    """Resolve the dev-mode root, or exit with the friendly message.

    Called once from main() for any subcommand registered with dev=True, rather
    than as a remembered first line in each handler.
    """
    global _SOURCE
    resolved = source_root()
    if resolved is None:
        sys.exit(
            "this subcommand needs a poly-crap source checkout "
            f"(no Cargo.toml naming poly-crap + src/score.rs under {repo_root()}).\n"
            "From another repository, use: check | scan | baseline | install"
        )
    _SOURCE = resolved


def git(*args):
    """Run git in the fixture with signing and identity forced off.

    Fixture commits must not inherit the user's commit.gpgsign — signing fails
    in a throwaway repo and git then refuses to write the commit object.
    """
    base = [
        "git",
        "-C",
        str(FIXTURE),
        "-c",
        "user.email=fixture@example.com",
        "-c",
        "user.name=fixture",
        "-c",
        "commit.gpgsign=false",
    ]
    return sh(base + list(args))


def lcov_text() -> str:
    py = FIXTURE / "src" / "b.py"
    # A fixed LCOV record, so a literal rather than a runtime join.
    rel = "SF:src/a.ts\nDA:1,1\nDA:2,1\nDA:3,0\nDA:4,0\nDA:5,1\nend_of_record"
    absolute = "\n".join(
        [f"SF:{py}"]
        + [
            f"DA:{n},{h}"
            for n, h in [
                (1, 1),
                (2, 1),
                (3, 0),
                (4, 0),
                (5, 0),
                (6, 0),
                (7, 0),
                (8, 1),
                (9, 1),
                (10, 0),
                (11, 0),
                (12, 1),
                (13, 1),
            ]
        ]
        + ["end_of_record"]
    )
    return rel + "\n" + absolute + "\n"


def write_fixture() -> None:
    if FIXTURE.exists():
        shutil.rmtree(FIXTURE)
    (FIXTURE / "src").mkdir(parents=True)
    for rel, text in SOURCES.items():
        (FIXTURE / rel).write_text(text)
    # src/a.ts gets a repo-relative SF: path and src/b.py an absolute one, so
    # both arms of the path matcher in src/merge.rs get exercised.
    (FIXTURE / "cov.lcov").write_text(lcov_text())

    git("init", "-q", "-b", "main", ".")
    git("add", "-A")
    out = git("commit", "-qm", "init")
    if out.returncode != 0:
        sys.exit(f"fixture commit failed:\n{out.stderr}")
    git("checkout", "-qb", "feature")
    rs = FIXTURE / "src" / "e.rs"
    rs.write_text(
        rs.read_text().replace(
            "pub fn simple(x: i32) -> i32 { x + 1 }\n", COMPLICATED_RS_SIMPLE
        )
    )
    git("commit", "-qam", "complicate simple")
    print(f"fixture ready at {FIXTURE} (branch feature, base main)")


def build() -> None:
    out = sh(["cargo", "build", "--locked"], cwd=source())
    if out.returncode != 0:
        sys.exit(f"cargo build failed:\n{out.stdout}\n{out.stderr}")


def crap(*args):
    """Run the built binary against the fixture. Returns (code, stdout, stderr).

    stdout and stderr are kept apart on purpose: warnings ("coverage scope
    mismatch") go to stderr and will corrupt stdout JSON if merged.
    """
    out = sh([str(bin_path()), "--path", str(FIXTURE), *map(str, args)])
    return out.returncode, out.stdout, out.stderr


def crap_json(*args, fmt="json"):
    """Run the binary and decode its structured output.

    fmt="sarif" is here so the SARIF assertions get the same exit-2 guard; they
    used to call json.loads(crap(...)[1]) directly and skip it.
    """
    code, stdout, stderr = crap("--format", fmt, *args)
    if code == 2:
        raise AssertionError(f"poly-crap failed: {stderr.strip()}")
    return json.loads(stdout)


class Checks:
    def __init__(self):
        self.failures = []
        self.count = 0

    def eq(self, label, got, want):
        self.count += 1
        if got != want:
            # Built once: the inline line and the end-of-run summary printed
            # the same text from two format strings and could drift apart.
            message = f"{label}: got {got!r}, want {want!r}"
            self.failures.append(message)
            print(f"  FAIL {message}")
        else:
            print(f"  ok   {label}")

    def holds(self, label, needle, collection, *, present):
        """Assert membership while keeping the collection in the failure text.

        `eq(label, x in coll, False)` reports only 'got True, want False' and
        throws away the one value you need to debug it.
        """
        self.eq(
            label,
            (needle in collection, sorted(collection)),
            (present, sorted(collection)),
        )


def documented_default() -> tuple[float | None, float | None]:
    """Parse the default threshold out of src/score.rs and out of the README.

    Deliberately not a constant in this file. Hardcoding the number here would
    make this script a third copy to hand-update, and drift between the code and
    the docs is precisely what the caller is checking for. Returns None for
    either side whose declaration has moved, which fails the check loudly
    rather than silently passing.
    """
    src = re.search(
        r"DEFAULT_THRESHOLD: f64 = (\d+(?:\.\d+)?)",
        (source() / "src" / "score.rs").read_text(),
    )
    doc = re.search(
        r"default threshold is `(\d+(?:\.\d+)?)`", (source() / "README.md").read_text()
    )
    return (float(src.group(1)) if src else None, float(doc.group(1)) if doc else None)


def validate(instance: Path, schema: str) -> bool:
    out = sh(
        [
            "uvx",
            "--quiet",
            "check-jsonschema",
            "--schemafile",
            str(source() / "schemas" / schema),
            str(instance),
        ]
    )
    if out.returncode != 0:
        print(f"       {out.stdout.strip()} {out.stderr.strip()}")
    return out.returncode == 0


def scenario_languages(c: Checks) -> None:
    print("\n[1] all six languages parse, complexity is stable")
    report = crap_json()
    c.eq(
        "parsed == candidate files",
        (
            report["diagnostics"]["parsed_files"],
            report["diagnostics"]["candidate_files"],
        ),
        (6, 6),
    )
    risky = {
        e["language"]: e["complexity"]
        for e in report["entries"]
        if e["symbol"].startswith(("risky", "Risky", "D.risky"))
    }
    c.eq(
        "complexity per language",
        risky,
        {
            "python": 9.0,
            "java": 8.0,
            "typescript": 7.0,
            "go": 7.0,
            "rust": 7.0,
            "javascript": 7.0,
        },
    )
    # Java symbols carry their parameter signature; the others do not.
    java = sorted(e["symbol"] for e in report["entries"] if e["language"] == "java")
    c.eq("java symbols keep signatures", java, ["D.risky(int,int)", "D.simple(int)"])


def scenario_coverage(c: Checks) -> None:
    print("\n[2] coverage merges by absolute path and by path suffix")
    report = crap_json("--coverage", FIXTURE / "cov.lcov")
    cov = {(e["language"], e["symbol"]): e["coverage"] for e in report["entries"]}
    c.eq(
        "relative SF: path matched (a.ts)", round(cov[("typescript", "risky")], 1), 60.0
    )
    c.eq("absolute SF: path matched (b.py)", round(cov[("python", "risky")], 2), 36.36)
    c.eq("unmatched file has null coverage", cov[("go", "Risky")], None)
    c.eq("scope mismatch counted", report["diagnostics"]["source_only_count"], 4)

    print("\n[3] --missing policies change the score of unmatched functions")
    for policy, want in [("pessimistic", 56.0), ("optimistic", 7.0)]:
        r = crap_json("--coverage", FIXTURE / "cov.lcov", "--missing", policy)
        got = next(e["score"] for e in r["entries"] if e["symbol"] == "Risky")
        c.eq(f"--missing {policy} -> Risky score", got, want)
    r = crap_json("--coverage", FIXTURE / "cov.lcov", "--missing", "skip")
    c.eq(
        "--missing skip drops unmatched functions",
        [e for e in r["entries"] if e["language"] == "go"],
        [],
    )


def scenario_filters(c: Checks) -> None:
    print("\n[4] default excludes, --allow globs")
    (FIXTURE / "node_modules").mkdir(exist_ok=True)
    (FIXTURE / "tests").mkdir(exist_ok=True)
    (FIXTURE / "node_modules" / "dep.js").write_text(SOURCES["src/f.js"])
    (FIXTURE / "tests" / "t.rs").write_text(SOURCES["src/e.rs"])
    (FIXTURE / "src" / "c_test.go").write_text(SOURCES["src/c.go"])
    try:
        default = {Path(e["file"]).name for e in crap_json()["entries"]}
        c.eq(
            "node_modules/tests/_test.go excluded by default",
            default & {"dep.js", "t.rs", "c_test.go"},
            set(),
        )
        opened = {
            Path(e["file"]).name for e in crap_json("--no-default-excludes")["entries"]
        }
        c.eq(
            "--no-default-excludes brings them back",
            opened >= {"dep.js", "t.rs", "c_test.go"},
            True,
        )
    finally:
        shutil.rmtree(FIXTURE / "node_modules")
        shutil.rmtree(FIXTURE / "tests")
        (FIXTURE / "src" / "c_test.go").unlink()

    # --allow suppresses what it matches, so a matched symbol is one that is
    # ABSENT from the report. Labels below describe presence/absence directly:
    # reading them as "did it match?" inverts the meaning.
    syms = {e["symbol"] for e in crap_json("--allow", "risky")["entries"]}
    c.holds(
        "--allow 'risky' suppresses that exact symbol", "risky", syms, present=False
    )
    c.holds(
        "--allow is case sensitive, so Go's 'Risky' survives",
        "Risky",
        syms,
        present=True,
    )
    c.holds(
        "bare 'D.risky' misses the java signature, which survives",
        "D.risky(int,int)",
        syms,
        present=True,
    )
    globbed = {e["symbol"] for e in crap_json("--allow", "D.risky*")["entries"]}
    c.holds(
        "--allow 'D.risky*' suppresses the java signature",
        "D.risky(int,int)",
        globbed,
        present=False,
    )
    files = {Path(e["file"]).name for e in crap_json("--allow", "src/b.py")["entries"]}
    c.holds(
        "--allow 'src/b.py' suppresses by root-relative path glob",
        "b.py",
        files,
        present=False,
    )
    c.eq(
        "--allow 'src/**' clears everything",
        crap_json("--allow", "src/**")["entries"],
        [],
    )


def scenario_formats(c: Checks) -> None:
    print("\n[5] output formats")
    code, stdout, _ = crap()
    c.eq("human output exits 0", code, 0)
    c.eq("human output has a header", stdout.splitlines()[0], "CRAP results")

    sarif = crap_json(fmt="sarif")
    c.eq("sarif version", sarif["version"], "2.1.0")
    # SARIF carries only threshold violations, unlike JSON which carries every
    # entry. Raise the threshold past every score and the results array empties
    # while the JSON report still lists all 11 functions.
    high = crap_json("--threshold", "1000", fmt="sarif")
    c.eq("sarif drops everything below threshold", len(high["runs"][0]["results"]), 0)
    c.eq(
        "json keeps entries the same run omits from sarif",
        len(crap_json("--threshold", "1000")["entries"]),
        11,
    )

    # Read the threshold back out of the human summary rather than hardcoding
    # it, so changing DEFAULT_THRESHOLD in src/score.rs does not fail this
    # check for the wrong reason. The next assertion is the one that pins it.
    # \d+\.\d+ and not [\d.]+ — the summary line ends in a period, which a
    # greedy character class swallows into the number.
    match = re.search(r"exceeds? CRAP threshold (\d+\.\d+)", stdout)
    c.eq("human summary names the threshold", match is not None, True)
    threshold = float(match.group(1)) if match else -1.0
    over = [e for e in crap_json()["entries"] if e["score"] > threshold]
    c.eq(
        "sarif carries exactly the over-threshold functions",
        len(sarif["runs"][0]["results"]),
        len(over),
    )
    src_default, doc_default = documented_default()
    c.eq(
        "src/score.rs, README, and the running binary agree on the default",
        (src_default, doc_default),
        (threshold, threshold),
    )

    print("\n[6] JSON matches the published schemas")
    if shutil.which("uvx") is None:
        print("  skip  uvx not found")
        return
    report_path = FIXTURE / "report.json"
    delta_path = FIXTURE / "delta.json"
    try:
        crap("--format", "json", "--output", report_path)
        c.eq("report-v1 validates", validate(report_path, "report-v1.json"), True)
        crap("--format", "json", "--baseline", report_path, "--output", delta_path)
        c.eq("delta-v1 validates", validate(delta_path, "delta-v1.json"), True)
    finally:
        # Leave the fixture tree clean. Scenario 8 switches branches, and stray
        # untracked files there would either block the checkout or have to be
        # stashed away.
        report_path.unlink(missing_ok=True)
        delta_path.unlink(missing_ok=True)


def scenario_diff(c: Checks) -> None:
    print("\n[7] --diff-base narrows to changed functions")
    report = crap_json("--diff-base", "main")
    syms = [(e["symbol"], e["complexity"]) for e in report["entries"]]
    # e.rs changed, but only `simple` moved. `risky` sits in the same file and
    # must not be pulled in.
    c.eq("only the changed function is reported", syms, [("simple", 4.0)])
    code, stdout, _ = crap("--diff-base", "main")
    c.eq(
        "human diff output names the merge base",
        stdout.startswith("Git diff against main from"),
        True,
    )
    c.eq("diff mode below threshold exits 0", code, 0)
    code, _, _ = crap("--diff-base", "main", "--threshold", "10", "--fail-above")
    c.eq("--fail-above exits 1 over threshold", code, 1)


def scenario_baseline(c: Checks) -> None:
    print("\n[8] --baseline detects regressions")
    # No stash: scenario 6 cleans up after itself, so the tree is clean here.
    # A bare `git stash` on a clean tree is a silent no-op, which made the old
    # pairing unrestorable.
    base = FIXTURE / "baseline.json"
    dirty = git("status", "--porcelain").stdout.strip()
    c.eq("fixture tree is clean before switching branches", dirty, "")
    git("checkout", "-q", "main")
    try:
        crap("--format", "json", "--output", base)
        git("checkout", "-q", "feature")
        delta = crap_json("--baseline", base)
        moved = [e for e in delta["entries"] if e.get("status") != "unchanged"]
        c.eq(
            "one function regressed",
            [(e["symbol"], e["status"]) for e in moved],
            [("simple", "regressed")],
        )
        c.eq(
            "regression records both scores",
            (moved[0]["baseline_score"], moved[0]["score"]),
            (2.0, 20.0),
        )
        code, _, _ = crap("--baseline", base, "--fail-regression")
        c.eq("--fail-regression exits 1", code, 1)
    finally:
        base.unlink(missing_ok=True)
        # Always land back on feature, even if an assertion above raised, so
        # scenario 9 does not silently run against main.
        git("checkout", "-q", "feature")


def ts_risky_coverage(*args):
    """Coverage of the TypeScript `risky` fixture function under the given flags."""
    report = crap_json(*args)
    return next(
        e["coverage"]
        for e in report["entries"]
        if e["language"] == "typescript" and e["symbol"] == "risky"
    )


def scenario_auto_discovery(c: Checks) -> None:
    print("\n[10] the binary auto-discovers coverage reports")
    # cov.lcov is deliberately not a default location, so a bare run warns.
    _, _, stderr = crap()
    c.eq(
        "no report at a default location -> stderr warning",
        "warning: no coverage report found" in stderr,
        True,
    )
    # A report at a default location, fully covering src/a.ts — unlike
    # cov.lcov's 60%, so the assertions can tell which report was read.
    (FIXTURE / "coverage.lcov").write_text(
        "SF:src/a.ts\nDA:1,1\nDA:2,1\nDA:3,1\nDA:4,1\nDA:5,1\nend_of_record\n"
    )
    try:
        _, _, stderr = crap()
        c.eq(
            "discovery is noted on stderr",
            "note: using discovered coverage report" in stderr,
            True,
        )
        c.eq("the note names the report", "coverage.lcov" in stderr, True)
        c.eq("the discovered report is merged", ts_risky_coverage(), 100.0)
        c.eq(
            "explicit --coverage wins over discovery",
            round(ts_risky_coverage("--coverage", FIXTURE / "cov.lcov"), 1),
            60.0,
        )
        c.eq(
            "--no-auto-coverage ignores the report",
            ts_risky_coverage("--no-auto-coverage"),
            None,
        )
    finally:
        (FIXTURE / "coverage.lcov").unlink()


def scenario_exit_codes(c: Checks) -> None:
    print("\n[9] exit codes and rejected flag combinations")
    c.eq("clean run exits 0", crap()[0], 0)
    c.eq("negative --threshold exits 2", crap("--threshold", "-5")[0], 2)
    c.eq(
        "missing coverage file exits 2",
        crap("--coverage", "/nonexistent/none.lcov")[0],
        2,
    )
    c.eq("--jobs 0 exits 2", crap("--jobs", "0")[0], 2)
    c.eq("unknown flag exits 2", crap("--not-a-flag")[0], 2)
    c.eq(
        "--diff-base with --baseline exits 2",
        crap("--diff-base", "main", "--baseline", "/tmp/x.json")[0],
        2,
    )
    c.eq(
        "--fail-regression without --baseline exits 2", crap("--fail-regression")[0], 2
    )
    code, stdout, _ = crap("--help")
    c.eq("--help exits 0", code, 0)
    c.eq("--help lists --diff-base", "--diff-base" in stdout, True)


def cmd_smoke(ns) -> int:
    build()
    write_fixture()
    c = Checks()
    for fn in (
        scenario_languages,
        scenario_coverage,
        scenario_filters,
        scenario_formats,
        scenario_diff,
        scenario_baseline,
        scenario_exit_codes,
        scenario_auto_discovery,
    ):
        fn(c)
    print(f"\n{c.count - len(c.failures)}/{c.count} checks passed")
    for f in c.failures:
        print(f"  FAIL {f}")
    return 1 if c.failures else 0


def cmd_build(ns) -> int:
    build()
    print(f"built {bin_path()}")
    return 0


def cmd_fixture(ns) -> int:
    write_fixture()
    return 0


def cmd_dev_run(ns) -> int:
    build()
    if not FIXTURE.exists():
        write_fixture()
    args = ns.extra[1:] if ns.extra[:1] == ["--"] else ns.extra
    return subprocess.run(
        [str(bin_path()), "--path", str(FIXTURE), *args], check=False
    ).returncode


# --------------------------------------------------------------------- cli


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # Everything about a subcommand lives on its parser: the handler (func),
    # whether it needs a source checkout (dev), and whether unrecognised flags
    # are forwarded to the binary (forward). Previously those were spread over
    # a dispatch dict, a name test, and a remembered first line in each handler.
    sub.add_parser(
        "check", help="report mode, binary, stack, coverage reports"
    ).set_defaults(func=cmd_check)

    install = sub.add_parser("install", help="install the poly-crap binary")
    install.add_argument("--yes", action="store_true", help="skip the prompt")
    install.add_argument("--force", action="store_true", help="reinstall")
    install.set_defaults(func=cmd_install)

    selfi = sub.add_parser(
        "self-install", help="copy this skill to your global skills dir"
    )
    selfi.add_argument("--dest", default="~/.claude/skills/poly-crap")
    selfi.add_argument("--force", action="store_true", help="overwrite")
    selfi.set_defaults(func=cmd_self_install)

    scan = sub.add_parser("scan", help="scan this repository")
    scan.add_argument(
        "--coverage",
        action="append",
        help="coverage report; repeatable. Auto-detected if omitted",
    )
    scan.add_argument("--diff-base", help="only functions changed since this revision")
    scan.add_argument("--baseline", help="compare against a baseline JSON")
    scan.add_argument("--threshold", type=float)
    scan.add_argument("--format", choices=["human", "json", "sarif"])
    scan.add_argument("--output")
    scan.add_argument(
        "--gate",
        action="store_true",
        help="exit 1 on violation (--fail-above, or --fail-regression with --baseline)",
    )
    # No positional catch-all here on purpose. A positional with nargs="*"
    # competes with parse_known_args for bare values: `--jobs 4` splits into
    # extra=["4"] and unknown=["--jobs"], which then reassemble out of order.
    # Letting parse_known_args collect the lot keeps flags and values together.
    scan.set_defaults(func=cmd_scan, forward=True)

    base = sub.add_parser("baseline", help="write a baseline JSON")
    base.add_argument("--out", default="poly-crap-baseline.json")
    base.add_argument("--coverage", action="append")
    base.set_defaults(func=cmd_baseline)

    sub.add_parser("build", help="[dev] cargo build --locked").set_defaults(
        func=cmd_build, dev=True
    )
    sub.add_parser("fixture", help="[dev] rebuild the fixture repo").set_defaults(
        func=cmd_fixture, dev=True
    )
    sub.add_parser("smoke", help="[dev] build and run every scenario").set_defaults(
        func=cmd_smoke, dev=True
    )
    # Forwards through the same mechanism as `scan` rather than a REMAINDER
    # positional. The old shape rejected a bare `dev-run --summary`, so the
    # leading `--` was mandatory here and meaningless for `scan`; now both
    # accept flags directly, and a leading `--` is still tolerated below.
    sub.add_parser(
        "dev-run", help="[dev] run the built binary on the fixture"
    ).set_defaults(func=cmd_dev_run, dev=True, forward=True)

    parser.set_defaults(dev=False, forward=False)

    # parse_known_args, so poly-crap flags this script does not model itself
    # (--jobs, --min, --top, --exclude, --summary, ...) reach the binary instead
    # of being rejected by argparse. Only forwarding subcommands accept them;
    # the rest still reject anything they do not recognise.
    ns, unknown = parser.parse_known_args()
    if unknown and not ns.forward:
        parser.error(f"unrecognized arguments: {' '.join(unknown)}")
    ns.extra = unknown
    if ns.dev:
        dev_setup()
    return ns.func(ns)


if __name__ == "__main__":
    sys.exit(main())
