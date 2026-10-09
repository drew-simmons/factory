---
name: poly-crap
description: Find functions that combine high complexity with low test coverage (the CRAP metric) in any repository — TypeScript, JavaScript, Python, Go, Rust, Java. Use when asked to find risky or untested code, find complex functions, check coverage quality, gate a change on complexity, review what a branch made riskier, or produce a SARIF or JSON code-quality report. Inside a poly-crap source checkout it also builds, runs, and smoke-tests poly-crap itself.
---

# poly-crap

Poly-crap scores every function by complexity against its test coverage. A high
score means tangled control flow, thin tests, or both.

One script, `poly_crap.py`, drives everything. It picks its mode from the
repository you are standing in, never from where the script is installed:

| Mode | When | Subcommands |
| --- | --- | --- |
| **scan** | any repository | `check` `scan` `baseline` `install` `self-install` |
| **dev** | inside a poly-crap source checkout | the above plus `build` `fixture` `smoke` `dev-run` |

Dev mode requires a `Cargo.toml` whose package is named `poly-crap` **and** a
`src/score.rs`. Another Rust project with a coincidental `src/score.rs` gets
scan mode, not a wrong build.

Layout follows the Agent Skills convention, at `skills/poly-crap` in the
poly-crap repository:

```text
poly-crap/
├── SKILL.md
└── scripts/
    └── poly_crap.py
```

## Install

The script is standalone — Python 3.9+, standard library only, no Rust
toolchain, no poly-crap source needed for scan mode. Verified running under
macOS system Python 3.9.6 as well as 3.13.

The [skills CLI](https://skills.sh) installs the skill into the agent
directories it finds, `.claude/skills/` among them:

```sh
npx skills add drew-simmons/poly-crap --skill poly-crap
```

From a checkout, the script installs itself:

```sh
# Into your global skills directory:
python3 skills/poly-crap/scripts/poly_crap.py self-install

# Into one repository instead:
python3 skills/poly-crap/scripts/poly_crap.py self-install --dest .claude/skills/poly-crap
```

`self-install` copies the whole skill directory and refuses to clobber an
existing one without `--force`:

```text
installed ['SKILL.md', 'scripts'] to /Users/you/.claude/skills/poly-crap
use it with:  python3 /Users/you/.claude/skills/poly-crap/scripts/poly_crap.py check
```

Without a checkout or Node.js, fetch the two files directly. The same
`raw.githubusercontent.com/drew-simmons/poly-crap/main/<path>` pattern already
serves `schemas/report-v1.json`:

```sh
mkdir -p ~/.claude/skills/poly-crap/scripts
base=https://raw.githubusercontent.com/drew-simmons/poly-crap/main/skills/poly-crap
curl -fsSL "$base/scripts/poly_crap.py" -o ~/.claude/skills/poly-crap/scripts/poly_crap.py
curl -fsSL "$base/SKILL.md"     -o ~/.claude/skills/poly-crap/SKILL.md
```

## Where the script lives

Every command below runs `$PC`. Set it once to match your install — the script
does not care, but the path you type does:

```sh
PC=~/.claude/skills/poly-crap/scripts/poly_crap.py      # global install
PC=.claude/skills/poly-crap/scripts/poly_crap.py        # installed into a project
PC=skills/poly-crap/scripts/poly_crap.py                # inside a poly-crap checkout
```

Run commands from inside the repository you want to work on. That working
directory, not `$PC`, is what selects the target and the mode.

## Start here: check

```sh
python3 "$PC" check
```

Reports the mode, the binary, the stack, and any coverage reports it found.
Verified in an unrelated Rust repo:

```text
repository: /private/tmp/rustother
mode:       scan
poly-crap:  /Users/you/.cargo/bin/poly-crap (poly-crap 0.3.0)
stack:      Rust  (found Cargo.toml)
            coverage: cargo llvm-cov --lcov --output-path coverage.lcov  -> coverage.lcov
coverage:   none found — the scan will treat every function as 0% covered
```

`check` exits 1 if the binary is missing. To get it:

```sh
python3 "$PC" install
```

That downloads and pipes the official cargo-dist installer to `sh`, prompting
first (`--yes` skips it). The URL was confirmed to serve the real installer
script, but the install itself was **not executed** during authoring — the
binary was already present, and reinstalling over someone's copy is not a thing
to do unasked. Equivalent by hand:

```sh
curl --proto '=https' --tlsv1.2 -LsSf \
  https://github.com/drew-simmons/poly-crap/releases/latest/download/poly-crap-installer.sh \
  | sh
```

## Scan mode

Start with the changed functions. That answers "did this branch make things
worse", which is the question worth asking before a merge:

```sh
python3 "$PC" scan --diff-base main
```

This narrows twice. Only files touched since the merge base with `main` are
parsed, and within those, only functions whose lines overlap a changed hunk. An
untouched `risky()` next to the function you edited stays out of the report.
Working-tree edits count, not just commits.

Scan the whole repository when you want the full picture — a first audit of an
unfamiliar codebase, or a report on the repo as it stands:

```sh
python3 "$PC" scan
```

Either way the script finds coverage reports on its own, and newer binaries
search the same default locations themselves when none are passed (opt out
with `--no-auto-coverage`). The script runs the scan and explains the exit
code. Flags this script does not model itself are forwarded to poly-crap
unchanged:

```sh
# Fail the run (exit 1) when a function is over the threshold.
python3 "$PC" scan --diff-base main --gate

# Machine-readable output.
python3 "$PC" scan --format json --output report.json
python3 "$PC" scan --format sarif --output report.sarif

# Explicit report, repeatable; plus any poly-crap flag.
python3 "$PC" scan --coverage coverage/lcov.info --jobs 4 --top 20
```

Verified gate behaviour in a repo with one over-threshold function:

```text
1 of 1 function exceeds CRAP threshold 5.0.

exit 1: gate failed — a function is over the threshold, or a score regressed
```

### Track regressions against a baseline

```sh
python3 "$PC" baseline --out poly-crap-baseline.json     # on main
python3 "$PC" scan --baseline poly-crap-baseline.json --gate   # on a branch
```

With `--baseline`, `--gate` means `--fail-regression` — it fails when a score
rises, not when it is merely high.

This is the whole-repo answer to the same pre-merge question, and the two are
mutually exclusive. `--diff-base` asks what you changed; `--baseline` asks what
got worse, including code you did not touch — a new uncovered path through an
old function, say, after your tests moved.

## Dev mode (poly-crap checkout only)

```sh
python3 "$PC" smoke
```

Builds the binary, generates a six-language fixture repo with hand-written
coverage and real Git history, then runs 51 assertions across every mode the
CLI has, ending in `51/51 checks passed`. Exit 1 if any check failed. Run this
after touching `src/analysis.rs`, `src/merge.rs`, `src/report.rs`,
`src/baseline.rs`, `src/coverage.rs`, or `src/git_diff.rs`.

The smoke suite always exercises the **freshly built** `target/debug/poly-crap`,
never whatever is on PATH.

| # | Scenario | Guards |
| --- | --- | --- |
| 1 | Six languages parse, complexity per language is exact | `src/analysis.rs` |
| 2 | Coverage merges by absolute path and by path suffix | `src/merge.rs`, `src/coverage.rs` |
| 3 | `--missing pessimistic/optimistic/skip` | `src/merge.rs`, `src/score.rs` |
| 4 | Default excludes and `--allow` globs | `src/config.rs`, `src/report.rs` |
| 5 | human / json / sarif output, default-threshold drift | `src/report.rs`, `src/score.rs` |
| 6 | JSON validates against `schemas/*.json` | `src/report.rs`, schemas |
| 7 | `--diff-base` narrows to changed functions | `src/git_diff.rs` |
| 8 | `--baseline` regression detection | `src/baseline.rs` |
| 9 | Exit codes 0/1/2 and rejected flag pairs | `src/main.rs` |
| 10 | Coverage auto-discovery and `--no-auto-coverage` | `src/coverage.rs`, `src/main.rs` |

Scenario 1 pins exact complexity numbers — python `risky` 9.0, java 8.0, the
other four 7.0 — so a change to the tree-sitter decision rules shows up as a
one-language drift rather than a vague failure. Scenario 5 cross-checks
`DEFAULT_THRESHOLD` in `src/score.rs` against the README and the running
binary, so code and docs cannot drift apart silently.

Other dev subcommands:

```sh
python3 "$PC" build                              # cargo build --locked
python3 "$PC" fixture                            # rebuild the fixture only
python3 "$PC" dev-run -- --format json --top 2   # built binary vs the fixture
```

The fixture lands at `/tmp/poly-crap-fixture` (override with
`POLY_CRAP_FIXTURE`). It is a real Git repo: `main` holds the baseline and the
checked-out `feature` branch complicates `simple` in `src/e.rs` from CC 1 to
CC 4, which is what scenarios 7 and 8 detect.

Outside a poly-crap checkout these refuse to run:

```text
this subcommand needs a poly-crap source checkout (no Cargo.toml naming poly-crap + src/score.rs under /private/tmp/rustother).
From another repository, use: check | scan | baseline | install
```

### Direct library invocation

Most PRs here touch library internals, not the CLI surface. To call
`analyze_tree` / `merge` / `score` directly, drop a scratch example in
`examples/`:

```sh
mkdir -p examples && cat > examples/scratch.rs <<'RS'
use poly_crap::model::{Language, MissingCoveragePolicy};
use poly_crap::{analyze_tree, merge, parse_coverage_files};
use std::path::{Path, PathBuf};

fn main() -> anyhow::Result<()> {
    let root = Path::new("/tmp/poly-crap-fixture");
    let analysis = analyze_tree(root, &[Language::Python], &[])?;
    println!("parsed {}/{}", analysis.parsed_files, analysis.candidate_files);
    let coverage = parse_coverage_files(&[PathBuf::from("/tmp/poly-crap-fixture/cov.lcov")])?;
    let merged = merge(analysis, &coverage, MissingCoveragePolicy::Pessimistic);
    for e in &merged.entries {
        println!("{} cc={} cov={:?} crap={}", e.symbol, e.complexity, e.coverage, e.score);
    }
    Ok(())
}
RS
cargo run --locked --example scratch
```

Verified output:

```text
parsed 1/1
risky cc=9 cov=Some(36.36363636363637) crap=29.87377911344853
simple cc=1 cov=Some(100.0) crap=1
```

Delete `examples/` afterwards — it is scratch space, not a tracked directory.

### Test suite

```sh
cargo test --locked --all-targets
cargo fmt --all --check
cargo clippy --locked --all-targets --all-features -- -D warnings
```

## Making a coverage report

Poly-crap reads reports; it never runs your tests. Without one, every function
counts as 0% covered and the scores are meaningless. Both the script and newer
binaries look for reports on their own — at the locations in the Report column
below, plus `lcov.info` and `coverage/coverage.lcov` (`COVERAGE_CANDIDATES` in
the script, `DEFAULT_REPORT_LOCATIONS` in `src/coverage.rs`). The docs site's
[Coverage reports](https://drew-simmons.github.io/poly-crap/coverage) pages
are the reference for these commands and for how report paths are matched to
source; `check` prints the right one for your stack:

| Marker | Stack | Command | Report |
| --- | --- | --- | --- |
| `Cargo.toml` | Rust | `cargo llvm-cov --lcov --output-path coverage.lcov` | `coverage.lcov` |
| `package.json` | JS / TS | `npx c8 --reporter=lcov npm test` | `coverage/lcov.info` |
| `pyproject.toml` | Python | `coverage run -m pytest && coverage lcov -o coverage.lcov` | `coverage.lcov` |
| `go.mod` | Go | `go test -coverprofile=coverage.out ./...` | `coverage.out` |
| `pom.xml` | Java (Maven) | `mvn verify` | `target/site/jacoco/jacoco.xml` |
| `build.gradle[.kts]` | Java (Gradle) | `gradle test jacocoTestReport` | `build/reports/jacoco/test/jacocoTestReport.xml` |
| `setup.py` | Python | `coverage run -m pytest && coverage lcov -o coverage.lcov` | `coverage.lcov` |

Only the Rust one was executed while writing this skill:

```sh
cargo llvm-cov --locked --lcov --output-path coverage.lcov
```

The rest come from poly-crap's docs and are printed as suggestions. Neither
`scan` nor `check` runs your test suite.

## Gotchas

- **No coverage report means every function scores as 0% covered.** The scan
  still succeeds and the numbers look alarming for no reason. Both `scan` and
  newer binaries print a `warning: no coverage report` line to stderr when
  they find none — do not read a report past that warning as a real result.
  When the binary discovers a report itself it says so with
  `note: using discovered coverage report(s)` on stderr;
  `--no-auto-coverage` turns that search off.
- **Exit 0 does not mean clean.** Poly-crap only fails a run when you ask for a
  gate. A scan reporting `1 of 2 functions exceeds CRAP threshold 5.0` still
  exits 0 without `--gate`; `scan` appends `(no gate requested — add --gate to
  fail on violations)` to keep that honest.
- **Warnings go to stderr and will corrupt piped JSON.** `poly-crap --format
  json 2>&1 | jq` dies with `Invalid numeric literal` as soon as a coverage
  scope mismatch fires. Use `2>/dev/null`. The script keeps the streams apart.
- **SARIF carries only threshold violations; JSON carries every function.** An
  empty SARIF `results` array does not mean the scan found nothing. Newer
  binaries print the same subset in human output, with an `N more functions
  not shown` line under the table; `--min 0` lists every function, and the last
  column names the uncovered line ranges.
- **`tests/`, `node_modules/`, and `*_test.go` are excluded by default**, along
  with hidden directories. `skills/` is not, so `poly_crap.py` stays out of
  this repo's own gate only because CI scans `--language rust`.
  `DEFAULT_EXCLUDES` lives at `src/config.rs:9`; `--no-default-excludes`
  widens the scan.
- **Calling the library directly bypasses those defaults.** The excludes are a
  const that `main.rs` passes in, not something `analyze_tree` applies. Pass
  `&[]` in a scratch example and you will scan `node_modules/` and `target/`.
- **`--allow` takes symbol globs and root-relative path globs in one flag**, and
  suppresses what it matches. `--allow 'src/**'` clears the entire report. Java
  symbols carry their signature (`D.risky(int,int)`), so `--allow 'D.risky'`
  matches nothing — use a glob. Matching is case sensitive.
- **`--diff-base` needs a Git repo and cannot combine with `--baseline`.** The
  script rejects both up front rather than letting poly-crap exit 2.
- **Fixture commits force `commit.gpgsign=false`.** With signing on globally,
  a throwaway repo has no key and git refuses to write the commit object.
- Documented but not exercised here: poly-crap does not read JavaScript source
  maps, so a TypeScript project must have its coverage producer emit original
  `.ts` paths or nothing will match.

## Troubleshooting

**`poly-crap not found on PATH`** — run `install`. `scan` also falls back to
`target/release/poly-crap` or `target/debug/poly-crap` in the current repo.

**`this subcommand needs a poly-crap source checkout`** — you ran a dev
subcommand elsewhere. Use `check`, `scan`, or `baseline`.

**Everything reports `N/A` coverage and huge scores** — the report was not
found or its paths do not line up. Run `check`, then pass `--coverage`
explicitly. Poly-crap matches absolute paths first, then the longest unique
path suffix, and warns `coverage scope mismatch: N source-only files` on
stderr when the scopes disagree.

**`jq: parse error: Invalid numeric literal at line 1, column 8`** — you merged
stderr into stdout. See the third gotcha.

**Smoke fails only on `src/score.rs, README, and the running binary agree`** —
the default threshold was changed in one place but not the other two.

**Scan is slow on a large repo** — pass `--jobs N`. Note `--jobs 0` exits 2.
