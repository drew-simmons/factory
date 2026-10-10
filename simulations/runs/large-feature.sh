#!/usr/bin/env sh
# large-feature: a monthly statement for the python ledger fixture, planned
# as four slices in three waves and built with /factory:implement --all, so
# implementer agents work wave 0 in parallel worktrees. One PR per slice,
# each on its parent branch.
set -u
. "$SIM/lib.sh"
REPO=${SIM_REPO:-drew-simmons/factory-sim-large-feature}

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
check plan "every slice has a Tracker line" tracker_lines_filled "${PLAN:-/dev/null}"
check plan "plan-check accepts the plan (no diamond)" plan_checks_out "${PLAN:-/dev/null}"
check plan "the plan was published to the tracker" tracker_published "${PLAN:-/dev/null}" "$(($(slice_count) + 1))"
SLICES=$(slice_ids)
WAVE0=$(sed -n '/^```json$/,/^```$/p' "$PLAN" | sed '1d;$d' | jq -r '.waves[0].slices[]')

stage implement-all "/factory:implement --all" 60
snap implement-all
cp -R "$WORK/docs" "$RESULTS/parent-docs" 2>/dev/null
DONE=$(committed_slices | wc -l)
# A worktree may stay only for a slice that is not committed (kept red on purpose).
check implement-all "implement released the worktree of every committed slice" test "$(($(git worktree list --porcelain | grep -c '^worktree ') - 1))" -le "$(($(slice_count) - DONE))"
check implement-all "implement kept per-slice verify evidence" test "$(ls "$WORK"/.verify/slices/*/summary.txt 2>/dev/null | wc -l)" -ge "$DONE"
if [ "$DONE" -eq "$(slice_count)" ]; then
  check implement-all "implement cleaned the untracked spec copy" test -z "$(git status --porcelain --untracked-files=all -- docs)"
fi
check implement-all "every slice has a commit" test "$DONE" -eq "$(slice_count)"
release_worktrees
git clean -fdq -- docs
for id in $SLICES; do
  b=$(slice_branch "$id")
  p=$(slice_parent "$id")
  check implement-all "slice $id branch $b exists" branch_exists "$b"
  committed_slices | grep -qx "$id" || { check implement-all "slice $id was committed (kept red by the implementer otherwise)" false; continue; }
  check implement-all "slice $id branch descends from its parent $p" sh -c "git merge-base --is-ancestor '$p' '$b'"
  check implement-all "slice $id has its own commit" test "$(git rev-parse "$b" 2>/dev/null)" != "$(git rev-parse "$p" 2>/dev/null)"
  check implement-all "slice $id commit cites the slice" sh -c "git log -1 --format=%s '$b' | grep -Eq '\($id, R[0-9]'"
done
# shellcheck disable=SC2086
set -- $WAVE0
if [ $# -ge 2 ]; then
  check implement-all "wave 0 slices changed disjoint source files" disjoint_changes "$BASE_SHA" src "$(slice_branch "$1")" "$(slice_branch "$2")"
else
  check implement-all "wave 0 holds two slices to compare" false
fi
check implement-all "implementer agents were spawned" sh -c "jq -e '.subagent_stats.spawned >= 2' '$RESULTS/implement-all.json'"
check implement-all "every committed slice has a verify summary in .verify/slices" test "$(ls "$RESULTS"/implement-all.verify/slices/*/summary.txt 2>/dev/null | wc -l)" -ge "$DONE"
LAST=$(committed_slices | tail -n 1)
[ -n "$LAST" ] || LAST=$(printf '%s\n' $SLICES | head -n 1)
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
check simplify "simplify committed its own change" tracked_clean

forge_stage pr-stack "/factory:pr --stack. I invoked this on purpose; open one PR per slice of the plan, each against its parent." 30
forge_check pr-stack "one PR per slice exists" test "$(pr_new)" = "$(slice_count)"
for id in $SLICES; do
  b=$(slice_branch "$id")
  p=$(slice_parent "$id")
  forge_check pr-stack "PR $id targets its parent $p" test "$(pr_field "$b" baseRefName)" = "$p"
  forge_check pr-stack "PR $id is not a draft" test "$(pr_field "$b" isDraft)" = false
  forge_check pr-stack "PR $id body carries the stack table" sh -c "gh pr list --head '$b' --state all --json body --jq '.[0].body' | grep -q '## Stack'"
  forge_check pr-stack "slice $id branch is on the remote" remote_branch_exists "$b"
done
[ "$FORGE" = 1 ] && gh pr list --state all --json number,url,baseRefName,headRefName,isDraft,title,body >"$RESULTS/prs.json"
git switch -q "$LAST_BRANCH"
HEAD_BEFORE=$(git rev-parse HEAD)

stage review "/factory:review" 15
check review "review wrote the handoff file" test -f "$(review_path "$LAST")"
check review "review file has the Standards axis" review_has "$LAST" Standards
check review "review file has the Spec axis" review_has "$LAST" Spec
check review "review edited nothing but its file" sh -c "[ -z \"\$(git status --porcelain | grep -v 'review-$LAST.md')\" ]"
HEAD_BEFORE=$(git rev-parse HEAD)

stage fix "/factory:implement $LAST --from-review" 18
check fix "review fixes landed as a commit when there was a P0 to P2 finding" sh -c "! grep -Eq '^- \[ \] \[P[012]\]' '$(review_path "$LAST")' || [ \"\$(git rev-parse HEAD)\" != '$HEAD_BEFORE' ]"
check fix "no unchecked P0 to P2 finding remains" sh -c "! grep -Eq '^- \[ \] \[P[012]\]' '$(review_path "$LAST")'"
check fix "tree is clean after the fix" tree_clean
check fix "verify is green after the fix" green_matches
check review "review committed nothing" test "$(git rev-parse HEAD)" = "$HEAD_BEFORE"

summary
