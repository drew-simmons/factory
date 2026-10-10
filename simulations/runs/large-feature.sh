#!/usr/bin/env sh
# large-feature: a monthly statement for the python ledger fixture, planned
# as four slices in three waves and built with /factory:implement --all, so
# implementer agents work wave 0 in parallel worktrees. One PR per slice,
# each on its parent branch.
set -u
. "$SIM/lib.sh"
REPO=${SIM_REPO:-drew-simmons/factory-sim-ledger}

sh "$SIM/fixtures/ledger/scaffold.sh" "$WORK" "$REPO" || exit 2
cd "$WORK" || exit 2
BASE_SHA=$(git rev-parse HEAD)
baseline

stage spec "/factory:spec Feature: a monthly statement. \`ledger statement <file> --month 2026-09\` prints every transaction posted in that month grouped by category, each group with its subtotal, then the month's closing balance. \`ledger balance <file>\` gains --since and --until date filters (inclusive) that limit which transactions count. Amounts keep the half-up cent rounding the README describes. Dates are ISO; a bad month or date is a usage error."
reply spec-agree "Take your recommended answer for every open question, update the spec file accordingly, clear the open questions section, and set Status: agreed."
SPEC=$(spec_path)
check spec "spec.md exists under docs/specs" test -n "$SPEC"
check spec "spec is agreed" grep -q '^Status: agreed' "${SPEC:-/dev/null}"
check spec "spec has at least four requirements" grep -Eq '^- R4\.' "${SPEC:-/dev/null}"
check spec "spec has no open questions left" open_questions_empty "${SPEC:-/dev/null}"

stage plan "/factory:plan. Slice it so at least two slices have no blockers and disjoint write sets, so they can run in parallel worktrees, and the CLI wiring comes last."
reply plan-publish "Approved as drafted: granularity, blocking edges, and the merge or split are all fine. Publish to the tracker now."
PLAN=$(plan_path)
check plan "plan.md exists beside the spec" test -n "$PLAN"
check plan "plan has a valid waves block" waves_valid "${PLAN:-/dev/null}"
check plan "plan has at least three slices" test "$(grep -c '^### 0[0-9] ' "${PLAN:-/dev/null}")" -ge 3
check plan "wave 0 holds at least two slices" sh -c "sed -n '/^\`\`\`json$/,/^\`\`\`$/p' '$PLAN' | sed '1d;\$d' | jq -e '.waves[0].slices | length >= 2'"
check plan "plan has at least two waves" sh -c "sed -n '/^\`\`\`json$/,/^\`\`\`$/p' '$PLAN' | sed '1d;\$d' | jq -e '.waves | length >= 2'"
check plan "every slice has a Tracker url" sh -c "[ \$(grep -Ec '^- Tracker: <?https://github.com/' '$PLAN') -eq \$(grep -c '^### 0[0-9] ' '$PLAN') ]"
check plan "a tracking issue and one issue per slice carry the factory label" sh -c "[ \$(cd '$WORK' && gh issue list --label factory --state all --json number --jq length) -gt \$(grep -c '^### 0[0-9] ' '$PLAN') ]"
SLICES=$(grep -E '^### 0[0-9] ' "$PLAN" | awk '{print $2}')
WAVE0=$(sed -n '/^```json$/,/^```$/p' "$PLAN" | sed '1d;$d' | jq -r '.waves[0].slices[]')

stage implement-all "/factory:implement --all" 60
snap implement-all
release_worktrees
# The parent wrote the plan in this checkout; every slice commit carries its
# own copy, and the untracked one blocks checking a slice branch out.
cp -R "$WORK/docs" "$RESULTS/parent-docs" 2>/dev/null
git clean -fdq -- docs
for id in $SLICES; do
  b=$(slice_branch "$id")
  p=$(slice_parent "$id")
  check implement-all "slice $id branch $b exists" branch_exists "$b"
  check implement-all "slice $id branch descends from its parent $p" sh -c "git merge-base --is-ancestor '$p' '$b'"
  check implement-all "slice $id has its own commit" test "$(git rev-parse "$b" 2>/dev/null)" != "$(git rev-parse "$p" 2>/dev/null)"
  check implement-all "slice $id commit cites the slice" sh -c "git log -1 --format=%s '$b' | grep -Eq '\($id, R[0-9]'"
done
set -- $WAVE0
check implement-all "wave 0 slices changed disjoint source files" disjoint_changes "$BASE_SHA" src "$(slice_branch "$1")" "$(slice_branch "$2")"
check implement-all "implementer agents were spawned" sh -c "jq -e '.subagent_stats.spawned >= 2' '$RESULTS/implement-all.json'"
check implement-all "the reply reports a verify result per slice" sh -c "[ \$(grep -Eic 'verify' '$RESULTS/implement-all.result.md') -ge 1 ]"
LAST=$(printf '%s\n' $SLICES | tail -n 1)
LAST_BRANCH=$(slice_branch "$LAST")
git switch -q "$LAST_BRANCH"
check implement-all "the last slice branch is checked out" on_branch "$LAST_BRANCH"
check implement-all "the statement command works end to end" sh -c "cd '$WORK' && printf '2026-09-03, groceries, market, -42.10\n2026-09-05, salary, september, 2500.00\n2026-10-01, groceries, bakery, -3.50\n' > $RESULTS/sample.csv && uv run ledger statement $RESULTS/sample.csv --month 2026-09 | grep -q '2457.90'"
check implement-all "the balance filters work end to end" sh -c "cd '$WORK' && uv run ledger balance $RESULTS/sample.csv --since 2026-10-01 | grep -q -- '-3.50'"
check implement-all "verify is green on the last slice" green_matches
TESTS_BEFORE=$(git rev-parse HEAD:tests)

stage simplify "/factory:simplify" 15
snap simplify
check simplify "tests are untouched by simplify" sh -c "[ -z \"\$(git status --porcelain -- tests)\" ] && [ \"\$(git rev-parse HEAD:tests)\" = '$TESTS_BEFORE' ]"
check simplify "verify is green after simplify" green_matches
if ! tracked_clean; then
  stage simplify-commit "Commit the simplification on the current branch with a conventional commit message. Do not touch tests."
  check simplify "simplification was committed" tracked_clean
fi

n=0
for id in $SLICES; do
  b=$(slice_branch "$id")
  p=$(slice_parent "$id")
  git switch -q "$b"
  stage "pr-$id" "/factory:pr. I invoked this on purpose; open the PR for slice $id, the current branch." 12
  n=$((n + 1))
  check "pr-$id" "PR $id exists" test "$(pr_new)" = "$n"
  check "pr-$id" "PR $id targets its parent $p" test "$(pr_field "$b" baseRefName)" = "$p"
  check "pr-$id" "PR $id is not a draft" test "$(pr_field "$b" isDraft)" = false
  check "pr-$id" "slice $id branch is on the remote" remote_branch_exists "$b"
done
gh pr list --state all --json number,url,baseRefName,headRefName,isDraft,title,body >"$RESULTS/prs.json"
git switch -q "$LAST_BRANCH"
HEAD_BEFORE=$(git rev-parse HEAD)

stage review "/factory:review" 15
check review "review reported the Standards axis" grep -q '## Standards' "$RESULTS/review.result.md"
check review "review reported the Spec axis" grep -q '## Spec' "$RESULTS/review.result.md"
check review "review edited nothing" tree_clean
check review "review committed nothing" test "$(git rev-parse HEAD)" = "$HEAD_BEFORE"

summary
