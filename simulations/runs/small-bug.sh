#!/usr/bin/env sh
# small-bug: one-function bug fix on the python ledger fixture.
#
# round_cents uses banker's rounding; the README promises half up. One slice,
# one PR. Also probes verify.sh directly: the stamp short-circuit, the floor
# on a new suppression, and poly-crap on an untested complex function.
set -u
. "$SIM/lib.sh"
REPO=${SIM_REPO:-drew-simmons/factory-sim-small-bug}
VERIFY="$FACTORY/skills/verify/scripts/verify.sh"

sh "$SIM/fixtures/ledger/scaffold.sh" "$WORK" "$REPO" || exit 2
cd "$WORK" || exit 2
BASE_SHA=$(git rev-parse HEAD)
baseline

stage setup "/factory:setup. I invoked this on purpose. Keep every value already in factory.toml; for anything you would otherwise ask me, take your own recommended answer and continue."
check setup "factory.toml keeps the github tracker" file_has factory.toml '^kind = "github"'
check setup "factory.toml keeps llm = true" file_has factory.toml '^llm = true'
check setup ".verify/ and .factory/ are ignored" sh -c "grep -q '^\.verify/' '$WORK/.gitignore' && grep -q '^\.factory/' '$WORK/.gitignore'"
check setup "setup committed nothing" test "$(git rev-parse HEAD)" = "$BASE_SHA"

stage spec "/factory:spec Bug: round_cents(Decimal(\"0.125\")) returns 0.12. The README says every printed amount is rounded half up, so finance expects 0.13. Fix the rounding and add a regression test."
reply spec-agree "Take your recommended answer for every open question, update the spec file accordingly, clear the open questions section, and set Status: agreed."
SPEC=$(spec_path)
check spec "spec.md exists under docs/specs" test -n "$SPEC"
check spec "spec is agreed" grep -q '^Status: agreed' "${SPEC:-/dev/null}"
check spec "spec has numbered requirements" grep -Eq '^- R1\.' "${SPEC:-/dev/null}"
check spec "spec names a seam" grep -Eiq 'seam' "${SPEC:-/dev/null}"
check spec "spec has no open questions left" open_questions_empty "${SPEC:-/dev/null}"
check spec "spec committed nothing" test "$(git rev-parse HEAD)" = "$BASE_SHA"

stage plan "/factory:plan"
reply plan-publish "Approved as drafted: granularity, blocking edges, and the merge or split are all fine. Publish to the tracker now."
PLAN=$(plan_path)
check plan "plan.md exists beside the spec" test -n "$PLAN"
check plan "plan has a valid waves block" waves_valid "${PLAN:-/dev/null}"
check plan "every slice has a Branch and a Parent" sh -c "[ \$(grep -c '^- Branch: ' '$PLAN') -ge 1 ] && [ \$(grep -c '^- Branch: ' '$PLAN') -eq \$(grep -c '^- Parent: ' '$PLAN') ]"
check plan "every slice has a Tracker line" tracker_lines_filled "${PLAN:-/dev/null}"
check plan "plan-check accepts the plan" plan_checks_out "${PLAN:-/dev/null}"
check plan "the plan was published to the tracker" tracker_published "${PLAN:-/dev/null}" 2
forge_check plan "no PR was opened by planning" test "$(pr_new)" = 0
BRANCH=$(slice_branch 01)
PARENT=$(slice_parent 01)

stage implement "/factory:implement 01" 18
snap implement
check implement "slice branch is checked out" on_branch "$BRANCH"
check implement "slice branch starts at main" test "$(git merge-base main "$BRANCH")" = "$BASE_SHA"
check implement "a commit landed on the slice branch" test "$(git rev-parse HEAD)" != "$BASE_SHA"
check implement "commit message cites the slice and a requirement" sh -c "git log -1 --format=%s | grep -Eq '\(01, R[0-9]'"
check implement "tree is clean after implement" tree_clean
check implement "a test file changed" sh -c "git diff --name-only '$BASE_SHA' -- tests | grep -q ."
check implement "the fix landed in money.py" sh -c "git diff '$BASE_SHA' -- src/ledger/money.py | grep -q '^+.*ROUND_HALF_UP'"
check implement "verify stamped the tree green" green_matches
check implement "the Stop hook ran and disarmed the loop" sh -c "test -f '$WORK/.verify/stop.log' && test ! -f '$WORK/.factory/loop.local.md'"
forge_check implement "no PR was opened by implement" test "$(pr_new)" = 0
TESTS_BEFORE=$(git rev-parse HEAD:tests)
HEAD_BEFORE=$(git rev-parse HEAD)

stage simplify "/factory:simplify" 12
snap simplify
check simplify "tests are untouched by simplify" sh -c "[ -z \"\$(git status --porcelain -- tests)\" ] && [ \"\$(git rev-parse HEAD:tests)\" = '$TESTS_BEFORE' ]"
check simplify "verify is green after simplify" green_matches
check simplify "simplify committed its own change" tracked_clean
check simplify "the commit kept the tests" test "$(git rev-parse HEAD:tests)" = "$TESTS_BEFORE"

printf '\n== %s/verify-probes\n' "$RUN"
rm -f .verify/green
sh "$VERIFY" >"$RESULTS/verify-green.log" 2>&1
check verify "verify.sh exits 0 on the green slice" test $? = 0
sh "$VERIFY" >"$RESULTS/verify-again.log" 2>&1
check verify "a second run short-circuits on the stamp" grep -q 'unchanged since the last green run' "$RESULTS/verify-again.log"
check verify "lawbook deterministic stage passed" grep -q 'lawbook, deterministic' "$RESULTS/verify-green.log"
check verify "poly-crap scored the change under the threshold" grep -q 'no changed function scores above' "$RESULTS/verify-green.log"
check verify "lawbook model stage ran on the green tree" sh -c "grep -A3 'model-judged' '$RESULTS/verify-green.log' | grep -Eq 'passed|plan:'"
cp "$WORK/.verify/summary.txt" "$RESULTS/verify-green.summary.txt" 2>/dev/null

git switch -q -c probe-floor
printf '\nimport os  # noqa\n' >>src/ledger/money.py
sh "$VERIFY" >"$RESULTS/verify-floor.log" 2>&1
rc=$?
check verify "a new suppression trips the floor with exit 1" sh -c "[ $rc -eq 1 ] && grep -q 'FLOOR new suppression' '$RESULTS/verify-floor.log'"
git checkout -q -- src
git switch -q "$BRANCH"
git branch -q -D probe-floor

git switch -q -c probe-crap
cat >>src/ledger/report.py <<'EOF'


def classify(amount: Decimal) -> str:
    if amount < -1000:
        return "large debit"
    if amount < 0:
        return "debit"
    if amount == 0:
        return "nothing"
    if amount < 100:
        return "credit"
    if amount < 1000:
        return "large credit"
    return "windfall"
EOF
sh "$VERIFY" >"$RESULTS/verify-crap.log" 2>&1
rc=$?
check verify "an untested complex function fails poly-crap with exit 1" sh -c "[ $rc -eq 1 ] && grep -q 'classify' '$RESULTS/verify-crap.log'"
check verify "the model stage is skipped on a red tree" grep -q 'no model requests on a red tree' "$RESULTS/verify-crap.log"
git checkout -q -- src
git switch -q "$BRANCH"
git branch -q -D probe-crap
rm -rf .verify
sh "$VERIFY" >/dev/null 2>&1

forge_stage pr "/factory:pr. I invoked this on purpose; open the PR for the current slice." 12
forge_check pr "exactly one PR exists" test "$(pr_new)" = 1
forge_check pr "PR targets the slice parent" test "$(pr_field "$BRANCH" baseRefName)" = "$PARENT"
forge_check pr "PR is not a draft" test "$(pr_field "$BRANCH" isDraft)" = false
forge_check pr "PR body carries verify evidence" sh -c "gh pr list --head '$BRANCH' --state all --json body --jq '.[0].body' | grep -Eq 'exit 0|Verification'"
forge_check pr "PR body mentions the tracker item" sh -c "gh pr list --head '$BRANCH' --state all --json body --jq '.[0].body' | grep -Eq '#[0-9]+|issues/[0-9]+'"
forge_check pr "slice branch is on the remote" remote_branch_exists "$BRANCH"
[ "$FORGE" = 1 ] && gh pr list --head "$BRANCH" --state all --json number,url,baseRefName,isDraft,title,body >"$RESULTS/prs.json"
HEAD_BEFORE=$(git rev-parse HEAD)

stage review "/factory:review" 12
check review "review wrote the handoff file" test -f "$(review_path 01)"
check review "review file has the Standards axis" review_has 01 Standards
check review "review file has the Spec axis" review_has 01 Spec
check review "review file has the CodeRabbit axis" review_has 01 CodeRabbit
check review "review edited nothing but its file" sh -c "[ -z \"\$(git status --porcelain | grep -v 'review-01.md')\" ]"
check review "review committed nothing" test "$(git rev-parse HEAD)" = "$HEAD_BEFORE"
forge_check review "review posted no PR comment" sh -c "[ \$(gh pr view '$BRANCH' --json comments --jq '.comments | length') -eq 0 ]"

summary
