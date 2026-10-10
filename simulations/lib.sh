# shellcheck shell=sh
# Sourced by runs/*.sh. Expects SIM (this directory), FACTORY (the plugin
# root), and RUN (the run name) in the environment; run.sh sets them.
#
# stage <name> <prompt> [budget]   one headless claude session in $WORK
# reply <name> <prompt> [budget]   one more turn in the session stage started
# check <stage> <text> <cmd...>    record pass or FAIL for a predicate
# snap <name>                      copy .verify and .factory out of $WORK
# summary                          print the stage and check tables
#
# Every session loads the plugin from $FACTORY, auto-accepts edits, and
# denies any tool a skill did not declare, so a denial is itself a finding.
RESULTS=$SIM/results/$RUN
mkdir -p "$RESULTS"
# The fixture checkout lives outside this repository: a path under .claude/
# (where the desktop app keeps worktrees) makes Claude Code treat every
# write as a sensitive config edit and deny it in headless mode.
WORK=${SIM_WORK_ROOT:-${TMPDIR:-/tmp}/factory-sim}/$RUN/repo
CHECKS=$RESULTS/checks.tsv
STAGES=$RESULTS/stages.tsv
# SIM_APPEND=1 keeps the records of an earlier attempt, for continuing a run
# by hand from a later stage.
if [ "${SIM_APPEND:-0}" != "1" ]; then
  : >"$CHECKS"
  : >"$STAGES"
fi
BUDGET=${SIM_BUDGET:-10}
MODEL=${SIM_MODEL:-}
ALLOWED='Bash(git *) Bash(gh *) Bash(sh *) Bash(uv *) Bash(uvx *) Bash(pnpm *) Bash(npx *) Bash(poly-crap *) Bash(lawbook *) Bash(coderabbit *) Bash(cr *) Bash(jq *) Bash(python3 *) Bash(node *) Bash(cat *) Bash(ls *) Bash(mkdir *) Bash(cp *) Bash(mv *) Bash(rm *) Bash(sed *) Bash(grep *) Bash(wc *) Bash(head *) Bash(tail *) Bash(diff *) Bash(echo *) Bash(printf *) Bash(test *) Bash(true) Read Edit Write Glob Grep Agent Skill TodoWrite'
SESSION=

new_id() { uuidgen | tr 'A-Z' 'a-z'; }

run_claude() {
  name=$1
  budget=$2
  shift 2
  out=$RESULTS/$name.json
  printf '\n== %s/%s\n' "$RUN" "$name"
  started=$(date +%s)
  (
    cd "$WORK" || exit 2
    # shellcheck disable=SC2086
    claude -p --plugin-dir "$FACTORY" --permission-mode acceptEdits --permission-prompts none \
      --allowedTools "$ALLOWED" --add-dir "$FACTORY" --output-format json --max-budget-usd "$budget" \
      ${MODEL:+--model "$MODEL"} "$@"
  ) >"$out" 2>"$RESULTS/$name.stderr"
  rc=$?
  took=$(($(date +%s) - started))
  if jq -e . "$out" >/dev/null 2>&1; then
    jq -r --arg name "$name" --arg rc "$rc" --arg took "$took" '
      [$name, $rc, (.is_error | tostring), (.num_turns | tostring),
       ((.total_cost_usd * 100 | round) / 100 | tostring), $took,
       (.permission_denials | length | tostring), (.subtype // "")] | @tsv' "$out" >>"$STAGES"
    jq -r '.result // ""' "$out" >"$RESULTS/$name.result.md"
    jq -c '.permission_denials[]?' "$out" >"$RESULTS/$name.denials.jsonl"
  else
    printf '%s\t%s\t-\t-\t-\t%s\t-\tno-json\n' "$name" "$rc" "$took" >>"$STAGES"
    : >"$RESULTS/$name.result.md"
  fi
  tail -n 12 "$RESULTS/$name.result.md"
  return "$rc"
}

stage() {
  SESSION=$(new_id)
  run_claude "$1" "${3:-$BUDGET}" --session-id "$SESSION" "$2"
}

reply() {
  run_claude "$1" "${3:-$BUDGET}" --resume "$SESSION" "$2"
}

check() {
  stage_name=$1
  text=$2
  shift 2
  if "$@" >/dev/null 2>&1; then status=pass; else status=FAIL; fi
  printf '%s\t%s\t%s\n' "$status" "$stage_name" "$text" | tee -a "$CHECKS"
}

snap() {
  rm -rf "$RESULTS/$1.verify" "$RESULTS/$1.factory"
  [ -d "$WORK/.verify" ] && cp -R "$WORK/.verify" "$RESULTS/$1.verify"
  [ -d "$WORK/.factory" ] && cp -R "$WORK/.factory" "$RESULTS/$1.factory"
  return 0
}

# Helpers for checks. All run in $WORK.
in_work() { (cd "$WORK" && "$@"); }
file_has() { grep -Eq "$2" "$WORK/$1"; }
file_lacks() { ! grep -Eq "$2" "$WORK/$1"; }
tree_clean() { [ -z "$(in_work git status --porcelain)" ]; }
tracked_clean() { [ -z "$(in_work git status --porcelain --untracked-files=no)" ]; }
on_branch() { [ "$(in_work git branch --show-current)" = "$1" ]; }
branch_exists() { in_work git rev-parse -q --verify "refs/heads/$1" >/dev/null; }
remote_branch_exists() { in_work git ls-remote --exit-code --heads origin "$1" >/dev/null; }
green_matches() {
  # The tree verifies clean. (The stamp alone is not enough: committing a
  # file that was untracked when the stage ran changes its hash.)
  in_work sh "$FACTORY/skills/verify/scripts/verify.sh" >/dev/null 2>&1
}
pr_count() { in_work gh pr list --state all --json number --jq length; }
# PRs opened since the run started; the throwaway repo may hold earlier runs.
PR0=0
baseline() { PR0=$(pr_count); }
pr_new() { echo $(($(pr_count) - PR0)); }
pr_field() { in_work gh pr list --head "$1" --state all --json "$2" --jq ".[0].$2"; }
issue_count() { in_work gh issue list --label factory --state all --json number --jq length; }
waves_valid() {
  sed -n '/^```json$/,/^```$/p' "$1" | sed '1d;$d' | jq -e '.waves | length > 0' >/dev/null
}
open_questions_empty() {
  ! sed -n '/^## Open questions/,$p' "$1" | grep -Eq '^ *([0-9]+[.)]|- |\* )'
}
spec_path() { ls "$WORK"/docs/specs/*/spec.md 2>/dev/null | head -n 1; }
plan_path() { ls "$WORK"/docs/specs/*/plan.md 2>/dev/null | head -n 1; }
slice_branch() { sed -n "/^### $1 /,/^### /{ s/^- Branch: *//p; }" "$(plan_path)" | head -n 1; }
slice_parent() { sed -n "/^### $1 /,/^### /{ s/^- Parent: *//p; }" "$(plan_path)" | head -n 1 | sed 's|^origin/||'; }

summary() {
  printf '\n== %s stages (name, exit, is_error, turns, usd, seconds, denials, subtype)\n' "$RUN"
  column -t -s "$(printf '\t')" "$STAGES"
  printf '\n== %s checks\n' "$RUN"
  column -t -s "$(printf '\t')" "$CHECKS"
  printf '\n%s pass, %s fail\n' "$(grep -c '^pass' "$CHECKS")" "$(grep -c '^FAIL' "$CHECKS")"
}

# disjoint_changes <base> <dir> <branch-a> <branch-b>: both branches changed
# something under <dir> and no file is in both diffs.
disjoint_changes() {
  in_work git diff --name-only "$1" "$3" -- "$2" | sort >"$RESULTS/.changed-a"
  in_work git diff --name-only "$1" "$4" -- "$2" | sort >"$RESULTS/.changed-b"
  [ -s "$RESULTS/.changed-a" ] && [ -s "$RESULTS/.changed-b" ] \
    && [ -z "$(comm -12 "$RESULTS/.changed-a" "$RESULTS/.changed-b")" ]
}

# release_worktrees: implementer agents leave their worktrees behind with the
# slice branches checked out, which blocks `git switch` in the main checkout.
release_worktrees() {
  in_work git worktree list --porcelain | sed -n 's/^worktree //p' | tail -n +2 | while IFS= read -r path; do
    in_work git worktree remove --force "$path"
  done
  in_work git worktree prune
}
