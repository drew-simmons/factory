# shellcheck shell=sh
# Sourced by runs/*.sh. Expects SIM (this directory), FACTORY (the plugin
# root), and RUN (the run name) in the environment; run.sh sets them.
#
# stage <name> <prompt> [budget]   one headless claude session in $WORK
# reply <name> <prompt> [budget]   one more turn in the session stage started
# check <stage> <text> <cmd...>    record pass or FAIL for a predicate
# snap <name>                      copy .verify and .factory out of $WORK
# summary                          print the tables; exit 1 when a check failed
#
# Every session loads the plugin from $FACTORY, auto-accepts edits, and
# denies any tool a skill did not declare, so a denial is itself a finding.
# The grants match the command word only: a compound command (&&, ;, a
# pipe, $(...)) is denied whole, which is what the skills' shell discipline
# rule exists for.
# Every stage also gets three checks for free: it did not error, it was not
# denied a tool, and it did not run out of budget or time.
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
  rm -rf "$RESULTS/parent-docs"
fi
BUDGET=${SIM_BUDGET:-10}
MODEL=${SIM_MODEL:-}
# SIM_FORGE=0: no GitHub. Stages and checks that need the forge are recorded
# as skipped, so a run still exits 0 when everything it could test passed.
FORGE=${SIM_FORGE:-1}
STAGE_TIMEOUT=${SIM_STAGE_TIMEOUT:-1800}
ALLOWED='Bash(git *) Bash(gh *) Bash(sh *) Bash(uv *) Bash(uvx *) Bash(pnpm *) Bash(npx *) Bash(poly-crap *) Bash(lawbook *) Bash(coderabbit *) Bash(cr *) Bash(jq *) Bash(python3 *) Bash(node *) Bash(cat *) Bash(ls *) Bash(mkdir *) Bash(cp *) Bash(mv *) Bash(rm *) Bash(sed *) Bash(grep *) Bash(wc *) Bash(head *) Bash(tail *) Bash(diff *) Bash(echo *) Bash(printf *) Bash(test *) Bash(true) Bash(ls) Bash(pwd) Bash(python *) Bash(pytest *) Bash(find *) Bash(awk *) Bash(sort *) Bash(tr *) Bash(cut *) Bash(touch *) Bash(date *) Bash(timeout *) Read Edit Write Glob Grep Agent Skill TodoWrite'
SESSION=

# The sessions must not inherit the user's global CLAUDE.md or settings (a
# global "never push" once overrode an agent's push step), so they run with a
# config directory that holds only the credentials. SIM_ISOLATE=0 opts out.
if [ "${SIM_ISOLATE:-1}" = "1" ]; then
  SOURCE_CONFIG=${CLAUDE_CONFIG_DIR:-$HOME/.claude}
  if [ -f "$SOURCE_CONFIG/.credentials.json" ]; then
    mkdir -p "$RESULTS/claude-config"
    cp "$SOURCE_CONFIG/.credentials.json" "$RESULTS/claude-config/"
    CLAUDE_CONFIG_DIR=$RESULTS/claude-config
    export CLAUDE_CONFIG_DIR
  else
    echo "lib: no $SOURCE_CONFIG/.credentials.json to copy; sessions inherit the user's config (SIM_ISOLATE=0 to silence)" >&2
  fi
fi

new_id() { uuidgen | tr '[:upper:]' '[:lower:]'; }

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
    timeout "$STAGE_TIMEOUT" claude -p --plugin-dir "$FACTORY" --permission-mode acceptEdits --permission-prompts none \
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
    check "$name" "session ended without error" jq -e '.is_error == false' "$out"
    check "$name" "no tool call was denied" jq -e '(.permission_denials | length) == 0' "$out"
    check "$name" "session finished on its own (not budget or turn cap)" jq -e '.subtype == "success"' "$out"
  else
    printf '%s\t%s\t-\t-\t-\t%s\t-\tno-json\n' "$name" "$rc" "$took" >>"$STAGES"
    : >"$RESULTS/$name.result.md"
    if [ "$rc" -eq 124 ]; then
      check "$name" "session finished within $STAGE_TIMEOUT s" false
    else
      check "$name" "session produced a result (exit $rc)" false
    fi
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

# forge_check and forge_stage: as check and stage with the forge, skipped without.
forge_check() {
  if [ "$FORGE" = 1 ]; then check "$@"; else printf 'skip\t%s\t%s (no forge)\n' "$1" "$2" | tee -a "$CHECKS"; fi
}
forge_stage() {
  if [ "$FORGE" = 1 ]; then stage "$@"; return $?; fi
  printf '\n== %s/%s skipped (no forge)\n' "$RUN" "$1"
  printf '%s\tskip\t-\t-\t-\t0\t-\tno-forge\n' "$1" >>"$STAGES"
  return 0
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
issue_count() { in_work gh issue list --label factory --state all --json number --jq length; }
# PRs and issues opened since the run started; the throwaway repo may hold
# earlier runs. Call baseline once, after the scaffold.
PR0=0
ISSUE0=0
baseline() { [ "$FORGE" = 1 ] || return 0; PR0=$(pr_count); ISSUE0=$(issue_count); }
pr_new() { echo $(($(pr_count) - PR0)); }
issue_new() { echo $(($(issue_count) - ISSUE0)); }
pr_field() { in_work gh pr list --head "$1" --state all --json "$2" --jq ".[0].$2"; }
waves_valid() {
  sed -n '/^```json$/,/^```$/p' "$1" | sed '1d;$d' | jq -e '.waves | length > 0' >/dev/null
}
plan_checks_out() { python3 -I "$FACTORY/skills/plan/scripts/plan-check.py" "$1" >/dev/null; }
open_questions_empty() {
  ! sed -n '/^## Open questions/,$p' "$1" | grep -Eq '^ *([0-9]+[.)]|- |\* )'
}
# spec_path and plan_path: the files in the checkout, else the copy a run saved
# under $RESULTS/parent-docs before cleaning the untracked spec directory.
first_of() { for f in "$@"; do [ -f "$f" ] && { echo "$f"; return 0; }; done; return 1; }
spec_path() { first_of "$WORK"/docs/specs/*/spec.md "$RESULTS"/parent-docs/specs/*/spec.md; }
plan_path() { first_of "$WORK"/docs/specs/*/plan.md "$RESULTS"/parent-docs/specs/*/plan.md; }
# committed_slices: ids whose branch has a commit past its parent.
committed_slices() {
  for id in $(slice_ids); do
    b=$(slice_branch "$id"); p=$(slice_parent "$id")
    [ "$(in_work git rev-parse "$b" 2>/dev/null)" != "$(in_work git rev-parse "$p" 2>/dev/null)" ] && echo "$id"
  done
}
review_path() { echo "$(dirname "$(plan_path)")/review-$1.md"; }
slice_count() { grep -Ec '^### [0-9][0-9] ' "$(plan_path)"; }
slice_ids() { grep -E '^### [0-9][0-9] ' "$(plan_path)" | awk '{print $2}'; }
slice_branch() { sed -n "/^### $1 /,/^### /{ s/^- Branch: *//p; }" "$(plan_path)" | head -n 1; }
# tracker_kind: what the fixture's factory.toml should say after setup.
tracker_kind() { if [ "$FORGE" = 1 ]; then echo github; else echo local; fi; }
slice_parent() { sed -n "/^### $1 /,/^### /{ s/^- Parent: *//p; }" "$(plan_path)" | head -n 1 | sed 's|^origin/||'; }
# tracker_lines_filled: every slice has a Tracker line, a URL with the forge, a path without.
tracker_lines_filled() {
  if [ "$FORGE" = 1 ]; then pattern='^- Tracker: <?https://'; else pattern='^- Tracker: \S'; fi
  [ "$(grep -Ec "$pattern" "$1")" -eq "$(grep -Ec '^### [0-9][0-9] ' "$1")" ]
}
# issue_files_published: without the forge, the plan wrote one issue file per slice.
issue_files_published() {
  [ "$(ls "$(dirname "$1")"/issues/*.md 2>/dev/null | wc -l)" -ge "$(grep -Ec '^### [0-9][0-9] ' "$1")" ]
}
# tracker_published: issues on the forge, or issue files without it.
tracker_published() {
  if [ "$FORGE" = 1 ]; then [ "$(issue_new)" -ge "$2" ]; else issue_files_published "$1"; fi
}
# review_has <NN> <section>: the review handoff file has that axis section.
review_has() { grep -q "^## $2" "$(review_path "$1")"; }

summary() {
  printf '\n== %s stages (name, exit, is_error, turns, usd, seconds, denials, subtype)\n' "$RUN"
  column -t -s "$(printf '\t')" "$STAGES"
  printf '\n== %s checks\n' "$RUN"
  column -t -s "$(printf '\t')" "$CHECKS"
  failed=$(grep -c '^FAIL' "$CHECKS")
  printf '\n%s pass, %s fail, %s skipped\n' "$(grep -c '^pass' "$CHECKS")" "$failed" "$(grep -c '^skip' "$CHECKS")"
  [ "$failed" -eq 0 ]
}

# disjoint_changes <base> <dir> <branch-a> <branch-b>: both branches changed
# something under <dir> and no file is in both diffs.
disjoint_changes() {
  in_work git diff --name-only "$1" "$3" -- "$2" | sort >"$RESULTS/.changed-a"
  in_work git diff --name-only "$1" "$4" -- "$2" | sort >"$RESULTS/.changed-b"
  [ -s "$RESULTS/.changed-a" ] && [ -s "$RESULTS/.changed-b" ] \
    && [ -z "$(comm -12 "$RESULTS/.changed-a" "$RESULTS/.changed-b")" ]
}

# release_worktrees: any worktree an implementer agent left behind is released
# through the plugin's own script, so its verify evidence lands in
# .verify/slices/<NN>/ of the main checkout. A worktree the script refuses
# (no commit, dirty) is removed anyway so the run can go on, and recorded.
release_worktrees() {
  in_work git worktree list --porcelain | sed -n 's/^worktree //p' | tail -n +2 | while IFS= read -r path; do
    branch=$(git -C "$path" branch --show-current)
    id=$(printf '%s' "$branch" | sed -n 's|.*/\([0-9][0-9]\)-.*|\1|p')
    if ! in_work sh "$FACTORY/skills/implement/scripts/release-worktree.sh" "$path" "${id:-unknown}"; then
      printf 'FAIL\timplement-all\trelease-worktree accepted %s (%s)\n' "$path" "$branch" | tee -a "$CHECKS"
      in_work git worktree remove --force "$path"
    fi
  done
  in_work git worktree prune
}
