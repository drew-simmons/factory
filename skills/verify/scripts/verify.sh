#!/usr/bin/env sh
# verify: one command, one exit code.
#
#   0  clean. Commit.
#   1  a gate failed. Read .verify/summary.txt, .verify/crap.json and
#      .verify/lawbook.json, fix only what they name, run again.
#   2  the loop itself is broken: a tool is missing, the base ref does not
#      exist, coverage was not produced, the stack is unknown. Fix the
#      setup or factory.toml, not the code.
#
# Every stage scopes to the same change: the merge base of $BASE and HEAD
# against the working tree, including uncommitted and untracked files.
# Stages run cheapest first, and the model-judged stage only on a green tree.
#
# Adapted from drew-simmons/verify-loop and generalized over stacks. Stack
# defaults live in detect_stack; factory.toml [verify.commands] overrides them.
set -u

HERE=$(cd "$(dirname "$0")" && pwd)
# The repository under test: CLAUDE_PROJECT_DIR when a hook or skill sets it,
# otherwise the git work tree that contains the current directory.
ROOT=${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}
[ -n "$ROOT" ] || { echo "verify: not inside a git repository (set CLAUDE_PROJECT_DIR)" >&2; exit 2; }
cd "$ROOT" || exit 2

OUT=.verify
mkdir -p "$OUT"

# Configuration: factory.toml, then environment overrides.
CONFIG_PY="$HERE/factory-config.py"
if command -v python3 >/dev/null 2>&1; then
  eval "$(python3 -I "$CONFIG_PY" factory.toml)"
else
  FACTORY_SPEC_DIR=docs/specs; FACTORY_BASE=origin/main; VERIFY_THRESHOLD=5; VERIFY_COVERAGE=; VERIFY_LLM=0
  VERIFY_EXCLUDE=; VERIFY_MAX_REQUESTS=50; VERIFY_MAX_ITERATIONS=5
  VERIFY_CMD_TYPECHECK=; VERIFY_CMD_LINT=; VERIFY_CMD_FORMAT=; VERIFY_CMD_TEST=
fi
# A planned slice is measured against its Parent from plan.md, so every
# stage sees the slice alone and not the whole stack. BASE=<ref> still wins.
slice_parent() {
  branch=$(git branch --show-current 2>/dev/null)
  [ -n "$branch" ] || return 1
  for plan in "$FACTORY_SPEC_DIR"/*/plan.md; do
    [ -f "$plan" ] || continue
    parent=$(awk -v b="$branch" '
      /^### / { inslice = 0 }
      $0 == "- Branch: " b { inslice = 1 }
      inslice && /^- Parent: / { sub(/^- Parent: */, ""); print; exit }
    ' "$plan")
    [ -n "$parent" ] && { printf '%s\n' "$parent"; return 0; }
  done
  return 1
}
if [ -z "${BASE:-}" ]; then
  PARENT=$(slice_parent) && git rev-parse -q --verify "$PARENT^{commit}" >/dev/null 2>&1 && FACTORY_BASE=$PARENT
fi
BASE=${BASE:-$FACTORY_BASE}
THRESHOLD=${THRESHOLD:-$VERIFY_THRESHOLD}
VERIFY_LLM=${VERIFY_LLM_OVERRIDE:-$VERIFY_LLM}
MAX_REQUESTS=${MAX_REQUESTS:-$VERIFY_MAX_REQUESTS}
LAWBOOK_CONFIG=${LAWBOOK_CONFIG:-lawbook.yaml}

# --loop arms the Stop hook: while .factory/loop.local.md exists, a red
# change cannot end the turn. An existing file keeps its iteration count.
if [ "${1:-}" = "--loop" ]; then
  mkdir -p .factory
  [ -f .factory/loop.local.md ] || printf -- '---\nsession_id: %s\niteration: 0\nmax_iterations: %s\n---\n' \
    "${CLAUDE_SESSION_ID:-}" "$VERIFY_MAX_ITERATIONS" >.factory/loop.local.md
fi

git rev-parse -q --verify "$BASE^{commit}" >/dev/null 2>&1 || BASE=main
MERGE_BASE=$(git merge-base "$BASE" HEAD 2>/dev/null) \
  || { echo "verify: no merge base between $BASE and HEAD (set [factory].base or BASE=<ref>)" >&2; exit 2; }

# A change that already passed is not verified twice. The stamp covers the
# tracked diff and every untracked file git does not ignore.
stamp() {
  {
    git diff "$MERGE_BASE" --
    git ls-files --others --exclude-standard -z | xargs -0 cat 2>/dev/null
  } | sha256 | cut -c1-16
}
sha256() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum; else shasum -a 256; fi
}
STAMP=$(stamp)
if [ "$STAMP" = "$(cat "$OUT/green" 2>/dev/null)" ]; then
  echo "verify: unchanged since the last green run ($STAMP)"
  exit 0
fi
rm -f "$OUT/crap.json" "$OUT/lawbook.json" "$OUT/comments.json" "$OUT/notes.json" "$OUT/summary.txt"

# The worst stage decides: 0 stays, 2 means broken, anything else is a failed gate.
status=0
record() {
  rc=$1
  [ "$rc" -eq 0 ] && return 0
  [ "$rc" -ne 2 ] && rc=1
  [ "$rc" -gt "$status" ] && status=$rc
  return 0
}
note() { printf '%s\n' "$*" | tee -a "$OUT/summary.txt"; }
now_ms() {
  ns=$(date +%s%N 2>/dev/null)
  case $ns in *N*|"") echo "$(($(date +%s) * 1000))" ;; *) echo "$((ns / 1000000))" ;; esac
}
T0=$(now_ms)
STAGE_T=
stage() {
  took
  printf '\n%s %s\n' '>' "$1" | tee -a "$OUT/summary.txt"
  STAGE_T=$(now_ms)
}
took() {
  [ -n "${STAGE_T:-}" ] && printf '  took %s ms\n' "$(($(now_ms) - STAGE_T))"
}
skip() { note "  skipped: $1"; }
missing() { note "  $1 is not installed"; record 2; }
run_stage() {
  # Run a stage command through sh so factory.toml commands may contain
  # arguments, pipes, or globs. The tail of its output goes to the summary.
  note "  \$ $1"
  sh -c "$1" >"$OUT/stage.log" 2>&1
  rc=$?
  tail -n 40 "$OUT/stage.log" | tee -a "$OUT/summary.txt"
  rm -f "$OUT/stage.log"
  return "$rc"
}

# Changed files: tracked changes since the merge base plus untracked files,
# minus [verify].exclude globs (shell patterns such as upstream/* or vendor/*).
excluded() {
  set -f  # keep the globs as patterns; do not expand them against the tree
  for pattern in $VERIFY_EXCLUDE; do
    # shellcheck disable=SC2254
    case $1 in $pattern) set +f; return 0 ;; esac
  done
  set +f
  return 1
}
changed_files() {
  { git diff --name-only --diff-filter=d "$MERGE_BASE" -- "$@"
    git ls-files --others --exclude-standard -- "$@"; } | sort -u | while IFS= read -r f; do
    excluded "$f" || printf '%s\n' "$f"
  done
}

# Stack detection: first marker wins; factory.toml overrides any command.
detect_stack() {
  if [ -f pnpm-lock.yaml ] || [ -f package.json ]; then echo node
  elif [ -f pyproject.toml ] || [ -f uv.lock ]; then echo python
  elif [ -f Cargo.toml ]; then echo rust
  elif [ -f go.mod ]; then echo go
  else echo unknown
  fi
}
STACK=$(detect_stack)
# Node: follow the lockfile. PM runs scripts, PM_EXEC runs a package binary.
if [ -f pnpm-lock.yaml ]; then PM=pnpm; PM_EXEC="pnpm exec"
elif [ -f yarn.lock ]; then PM=yarn; PM_EXEC="yarn"
else PM=npm; PM_EXEC="npx --no-install"
fi
SRC_GLOB=
case $STACK in
  node)   SRC_GLOB='*.js *.jsx *.ts *.tsx *.mjs *.cjs' ;;
  python) SRC_GLOB='*.py' ;;
  rust)   SRC_GLOB='*.rs' ;;
  go)     SRC_GLOB='*.go' ;;
esac
# Globbing stays off while the patterns are split: at the repository root a
# bare *.ts or *.py would otherwise expand to the files that happen to sit
# there (vitest.config.ts, conftest.py) and hide every change under src/.
set -f
# shellcheck disable=SC2086
CHANGED_SRC=$(changed_files $SRC_GLOB)
set +f
CHANGED_SRC_LINE=$(printf '%s' "$CHANGED_SRC" | tr '\n' ' ')

default_typecheck() {
  case $STACK in
    node)   if [ -f tsconfig.json ]; then echo "$PM_EXEC tsc --noEmit"; else echo "for f in $CHANGED_SRC_LINE; do node --check \"\$f\" || exit 1; done"; fi ;;
    python) echo "uv run python -m compileall -q $CHANGED_SRC_LINE" ;;
    rust)   echo "cargo check --quiet" ;;
    go)     echo "go vet ./..." ;;
  esac
}
default_lint() {
  case $STACK in
    node)   [ -n "$(ls eslint.config.* .eslintrc* 2>/dev/null)" ] && echo "$PM_EXEC eslint $CHANGED_SRC_LINE" ;;
    python) echo "uvx ruff check $CHANGED_SRC_LINE" ;;
    rust)   echo "cargo clippy --quiet -- -D warnings" ;;
    go)     command -v golangci-lint >/dev/null 2>&1 && echo "golangci-lint run" ;;
  esac
}
default_format() {
  case $STACK in
    node)   [ -n "$(ls .prettierrc* prettier.config.* 2>/dev/null)" ] && echo "$PM_EXEC prettier --check $CHANGED_SRC_LINE" ;;
    python) echo "uvx ruff format --check $CHANGED_SRC_LINE" ;;
    rust)   echo "cargo fmt --check" ;;
    go)     echo "test -z \"\$(gofmt -l $CHANGED_SRC_LINE)\"" ;;
  esac
}
default_test() {
  case $STACK in
    node)   echo "$PM test" ;;
    python) echo "uv run pytest -q --cov --cov-report=lcov:$OUT/lcov.info" ;;
    rust)   echo "cargo llvm-cov --lcov --output-path $OUT/lcov.info" ;;
    go)     echo "go test -coverprofile=$OUT/coverage.out ./..." ;;
  esac
}
default_coverage() {
  case $STACK in
    node)   if [ -f lcov.info ] && [ ! -f coverage/lcov.info ]; then echo lcov.info; else echo coverage/lcov.info; fi ;;
    python) echo "$OUT/lcov.info" ;;
    rust)   echo "$OUT/lcov.info" ;;
    go)     echo "$OUT/coverage.out" ;;
  esac
}
CMD_TYPECHECK=${VERIFY_CMD_TYPECHECK:-$(default_typecheck)}
CMD_LINT=${VERIFY_CMD_LINT:-$(default_lint)}
CMD_FORMAT=${VERIFY_CMD_FORMAT:-$(default_format)}
CMD_TEST=${VERIFY_CMD_TEST:-$(default_test)}
COVERAGE=${VERIFY_COVERAGE:-$(default_coverage)}

tests_changed() {
  [ -n "$(changed_files 'test/*' 'tests/*' '*_test.go' '*.test.*' '*_test.py' 'test_*.py' '*.spec.*')" ]
}

hunk_session_open() {
  [ "${HUNK:-1}" != "0" ] || return 1
  command -v hunk >/dev/null 2>&1 || return 1
  if command -v pgrep >/dev/null 2>&1; then
    pgrep -f 'hunk (diff|show|gh|patch|log)' >/dev/null 2>&1 || return 1
  fi
  hunk session get --repo . >/dev/null 2>&1
}

lawbook_summary() {
  jq -r '
    .results[]
    | select(.status == "fail" or .status == "warn" or .status == "error")
    | .id as $id | .status as $status
    | .findings[]
    | "  \($status | ascii_upcase) [\($id)] \(.path // "-")\(if .line then ":\(.line)" else "" end): \(.message)"
  ' "$OUT/lawbook.json" 2>/dev/null | tee -a "$OUT/summary.txt"
  jq -r '.summary | "  \(.passed) passed, \(.failed) failed, \(.warned) warned, \(.errored) errored, \(.skipped) skipped"' \
    "$OUT/lawbook.json" 2>/dev/null | tee -a "$OUT/summary.txt"
}

echo "verify: $BASE..working tree (merge base ${MERGE_BASE%"${MERGE_BASE#???????}"}), stack $STACK" | tee "$OUT/summary.txt"
if [ "$STACK" = unknown ] && [ -z "$VERIFY_CMD_TEST" ]; then
  note "verify: unknown stack and no [verify.commands] in factory.toml; run /factory:setup"
  exit 2
fi
if [ -z "$CHANGED_SRC" ] && [ -z "$(changed_files)" ]; then
  echo "verify: nothing changed against $BASE"
  printf '%s' "$STAMP" >"$OUT/green"
  exit 0
fi

stage "0  floor: the diff must not lower the bar"
# Added lines in changed source files only, each prefixed with its path.
added_lines() {
  for f in $CHANGED_SRC; do
    if git ls-files --error-unmatch -- "$f" >/dev/null 2>&1; then
      git diff "$MERGE_BASE" -- "$f" | grep -E '^\+[^+]' | sed "s|^+|$f: |"
    else
      sed "s|^|$f: |" "$f"
    fi
  done
}
DIFF_ADDED=$(added_lines)
floor_hit() {
  pattern=$1; label=$2
  hits=$(printf '%s\n' "$DIFF_ADDED" | grep -E "$pattern" | head -n 5)
  if [ -n "$hits" ]; then
    note "  FLOOR $label:"
    printf '%s\n' "$hits" | sed 's/^/    /' | tee -a "$OUT/summary.txt"
    record 1
  fi
}
floor_hit '@ts-ignore|@ts-expect-error|eslint-disable|# *noqa|# *type: *ignore|#\[allow\(|//nolint|# pragma: no cover' "new suppression"
floor_hit '\.skip\(|\.only\(|@pytest\.mark\.skip|#\[ignore\]|t\.Skip\(|(^|[^a-zA-Z0-9_.])(xit|xdescribe|fit|fdescribe)\(' "skipped or focused test"
DELETED_TESTS=$(git diff --name-only --diff-filter=D "$MERGE_BASE" -- 'test/*' 'tests/*' '*_test.go' '*.test.*' '*_test.py' 'test_*.py' '*.spec.*')
if [ -n "$DELETED_TESTS" ]; then
  note "  FLOOR deleted test files:"
  printf '%s\n' "$DELETED_TESTS" | sed 's/^/    /' | tee -a "$OUT/summary.txt"
  record 1
fi
if git diff "$MERGE_BASE" -- factory.toml lawbook.yaml .poly-crap.toml | grep -Eq '^-.*(crap_threshold|threshold|level: *error)'; then
  note "  FLOOR a threshold or rule level in factory.toml, lawbook.yaml, or .poly-crap.toml was edited; review by hand"
  record 1
fi
[ "$status" -eq 0 ] && note "  clean"

stage "1  typecheck or syntax on changed files"
if [ -z "$CHANGED_SRC" ]; then skip "no changed source files"
elif [ -z "$CMD_TYPECHECK" ]; then skip "no typecheck command for stack $STACK"
else run_stage "$CMD_TYPECHECK" || record $?
fi

stage "2  lint on changed files"
if [ -z "$CHANGED_SRC" ]; then skip "no changed source files"
elif [ -z "$CMD_LINT" ]; then skip "no lint command for stack $STACK"
else run_stage "$CMD_LINT" || record $?
fi

stage "3  format check on changed files"
if [ -z "$CHANGED_SRC" ]; then skip "no changed source files"
elif [ -z "$CMD_FORMAT" ]; then skip "no format command for stack $STACK"
else run_stage "$CMD_FORMAT" || record $?
fi

stage "4  lawbook, deterministic rules on changed files"
if [ ! -f "$LAWBOOK_CONFIG" ]; then skip "no $LAWBOOK_CONFIG"
elif ! command -v lawbook >/dev/null 2>&1; then missing lawbook
else
  lawbook check . --config "$LAWBOOK_CONFIG" --no-llm --changed --since "$BASE" --format json >"$OUT/lawbook.json"
  record $?
  lawbook_summary
fi

stage "5  tests with coverage"
rm -f "$COVERAGE"
if [ -z "$CMD_TEST" ]; then note "  no test command for stack $STACK"; record 2
else run_stage "$CMD_TEST" || record $?
fi

stage "6  poly-crap on changed functions (threshold $THRESHOLD)"
if ! command -v poly-crap >/dev/null 2>&1; then missing poly-crap
elif [ ! -f "$COVERAGE" ]; then
  note "  no coverage file at $COVERAGE; the test run did not produce coverage (set [verify].coverage)"
  record 2
else
  if tests_changed; then
    note "  full scan: test files changed, so every function is scored"
    set -- --path .
  else
    set -- --diff-base "$BASE"
  fi
  poly-crap "$@" --coverage "$COVERAGE" --threshold "$THRESHOLD" --fail-above \
    --format json --output "$OUT/crap.json" 2>"$OUT/crap.err"
  record $?
  grep -v '^$' "$OUT/crap.err" | head -n 5; rm -f "$OUT/crap.err"
  jq -r --argjson t "$THRESHOLD" '
    [.entries[] | select(.score > $t)]
    | if length == 0 then "  no changed function scores above \($t)"
      else .[] | "  \(.file | ltrimstr("./")):\(.start_line) \(.symbol)  CRAP \((.score * 10 | round) / 10)  CC \(.complexity | round)  coverage \(if .coverage == null then "none" else "\(.coverage | round)%" end)"
      end
  ' "$OUT/crap.json" 2>/dev/null | tee -a "$OUT/summary.txt"
fi

stage "7  lawbook, model-judged standards"
# The dry run sees the whole config, extends included, so it is the only
# reliable way to know whether a standard rule selects a changed file.
lawbook_plan() { lawbook check . --config "$LAWBOOK_CONFIG" --changed --since "$BASE" --dry-run 2>/dev/null; }
if [ "$status" -ne 0 ]; then skip "an earlier stage failed; no model requests on a red tree"
elif [ ! -f "$LAWBOOK_CONFIG" ]; then skip "no $LAWBOOK_CONFIG"
elif ! command -v lawbook >/dev/null 2>&1; then skip "lawbook is not installed"
elif ! lawbook_plan | grep -Eq '\(standard, [1-9]'; then skip "no standard rule selects a changed file"
elif [ "$VERIFY_LLM" != "1" ]; then skip "set [verify].llm = true (or VERIFY_LLM_OVERRIDE=1) to judge prose standards"
else
  note "  plan: $(lawbook_plan | tail -n 1), cap $MAX_REQUESTS"
  lawbook check . --config "$LAWBOOK_CONFIG" --changed --since "$BASE" --max-requests "$MAX_REQUESTS" --format json >"$OUT/lawbook.json"
  rc=$?
  record "$rc"
  lawbook_summary
  [ "$rc" -eq 1 ] && note "  a fail-level standard failed; warn-level findings above are advisory"
fi

stage "8  findings to Hunk"
for f in crap lawbook; do
  [ -s "$OUT/$f.json" ] || echo null >"$OUT/$f.json"
done
COUNT=0
if command -v jq >/dev/null 2>&1; then
  jq -s --argjson t "$THRESHOLD" --arg format session -f "$HERE/to-hunk.jq" \
    "$OUT/crap.json" "$OUT/lawbook.json" >"$OUT/comments.json"
  jq -s --argjson t "$THRESHOLD" --arg format sidecar -f "$HERE/to-hunk.jq" \
    "$OUT/crap.json" "$OUT/lawbook.json" >"$OUT/notes.json"
  COUNT=$(jq '.comments | length' "$OUT/comments.json")
  if hunk_session_open; then
    hunk session comment clear --repo . --yes >/dev/null 2>&1
    [ "$COUNT" -gt 0 ] && hunk session comment apply --repo . --stdin <"$OUT/comments.json" >/dev/null
    echo "  $COUNT comment(s) in the live Hunk session"
  else
    echo "  no live Hunk session; wrote $OUT/notes.json ($COUNT annotation(s))"
  fi
else
  skip "jq is not installed"
fi

took
TOTAL=$(($(now_ms) - T0))
echo
# Stamp again at the end: a test run may create untracked files (a lockfile,
# a snapshot), and a rerun on that tree should still count as unchanged.
case $status in
  0) STAMP=$(stamp); printf '%s' "$STAMP" >"$OUT/green"; note "verify: clean ($STAMP) in $TOTAL ms" ;;
  1) note "verify: gate failed in $TOTAL ms. Fix only what is named above, then run again." ;;
  *) note "verify: could not run (exit 2) in $TOTAL ms. Fix the setup, not the code." ;;
esac
exit "$status"
