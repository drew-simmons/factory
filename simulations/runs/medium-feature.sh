#!/usr/bin/env sh
# medium-feature: a --json flag for the status command on the typescript
# fixture, planned as two stacked slices with one PR each. Proves the node
# stack path of verify.sh, the github tracker, and a stacked PR whose base is
# the first slice's branch.
set -u
. "$SIM/lib.sh"
REPO=${SIM_REPO:-drew-simmons/factory-sim-medium-feature}

sh "$SIM/fixtures/status/scaffold.sh" "$WORK" "$REPO" || exit 2
cd "$WORK" || exit 2
BASE_SHA=$(git rev-parse HEAD)
baseline

stage setup "/factory:setup. I invoked this on purpose. Keep every value already in factory.toml; for anything you would otherwise ask me, take your own recommended answer and continue."
check setup "factory.toml keeps the github tracker" file_has factory.toml '^kind = "github"'
check setup "factory.toml keeps llm = true" file_has factory.toml '^llm = true'
check setup "setup committed nothing" test "$(git rev-parse HEAD)" = "$BASE_SHA"

stage spec "/factory:spec Feature: scripts want to parse the status command, so add a --json flag to it: \`status-cli status --json\` prints the same report as one JSON object on one line. Text output stays the default and must not change. An unknown flag keeps exiting 2 with usage."
reply spec-agree "Take your recommended answer for every open question, update the spec file accordingly, clear the open questions section, and set Status: agreed."
SPEC=$(spec_path)
check spec "spec.md exists under docs/specs" test -n "$SPEC"
check spec "spec is agreed" grep -q '^Status: agreed' "${SPEC:-/dev/null}"
check spec "spec has numbered requirements" grep -Eq '^- R2\.' "${SPEC:-/dev/null}"
check spec "spec has no open questions left" open_questions_empty "${SPEC:-/dev/null}"

stage plan "/factory:plan. Aim for two slices: the JSON rendering of a status report first, then the CLI flag stacked on it."
reply plan-publish "Approved as drafted: granularity, blocking edges, and the merge or split are all fine. Publish to the tracker now."
PLAN=$(plan_path)
check plan "plan.md exists beside the spec" test -n "$PLAN"
check plan "plan has a valid waves block" waves_valid "${PLAN:-/dev/null}"
check plan "plan has two slices" test "$(grep -c '^### 0[0-9] ' "${PLAN:-/dev/null}")" = 2
check plan "slice 02 is blocked by 01" sh -c "sed -n '/^### 02 /,/^### /p' '$PLAN' | grep -Eq '^- Blocked by: *01'"
check plan "slice 02 stacks on slice 01's branch" test "$(slice_parent 02)" = "$(slice_branch 01)"
check plan "every slice has a Tracker line" tracker_lines_filled "${PLAN:-/dev/null}"
check plan "plan-check accepts the plan" plan_checks_out "${PLAN:-/dev/null}"
check plan "the plan was published to the tracker" tracker_published "${PLAN:-/dev/null}" 3
B1=$(slice_branch 01)
B2=$(slice_branch 02)
P1=$(slice_parent 01)

stage implement-01 "/factory:implement 01" 18
snap implement-01
check implement-01 "slice 01 branch is checked out" on_branch "$B1"
check implement-01 "a commit landed on slice 01" test "$(git rev-parse HEAD)" != "$BASE_SHA"
check implement-01 "commit message cites the slice" sh -c "git log -1 --format=%s | grep -Eq '\(01, R[0-9]'"
check implement-01 "tree is clean" tree_clean
check implement-01 "a test file changed" sh -c "git diff --name-only '$BASE_SHA' -- test | grep -q ."
check implement-01 "verify stamped the tree green" green_matches
check implement-01 "the Stop hook ran and disarmed the loop" sh -c "test -f '$WORK/.verify/stop.log' && test ! -f '$WORK/.factory/loop.local.md'"
check implement-01 "typecheck stage ran tsc" grep -q 'tsc --noEmit' "$WORK/.verify/summary.txt"
check implement-01 "test stage ran pnpm test" grep -q 'pnpm test' "$WORK/.verify/summary.txt"
check implement-01 "poly-crap found the vitest lcov" grep -q 'no changed function scores above' "$WORK/.verify/summary.txt"
S1=$(git rev-parse HEAD)

forge_stage pr-01 "/factory:pr. I invoked this on purpose; open the PR for slice 01." 12
forge_check pr-01 "one PR exists" test "$(pr_new)" = 1
forge_check pr-01 "PR 01 targets main" test "$(pr_field "$B1" baseRefName)" = "$P1"
forge_check pr-01 "PR 01 is not a draft" test "$(pr_field "$B1" isDraft)" = false
forge_check pr-01 "PR 01 body carries verify evidence" sh -c "gh pr list --head '$B1' --state all --json body --jq '.[0].body' | grep -Eq 'exit 0|Verification'"

stage implement-02 "/factory:implement 02" 18
snap implement-02
check implement-02 "slice 02 branch is checked out" on_branch "$B2"
check implement-02 "slice 02 starts at the tip of slice 01" test "$(git merge-base "$B1" "$B2")" = "$S1"
check implement-02 "a commit landed on slice 02" test "$(git rev-parse HEAD)" != "$S1"
check implement-02 "commit message cites the slice" sh -c "git log -1 --format=%s | grep -Eq '\(02, R[0-9]'"
check implement-02 "tree is clean" tree_clean
check implement-02 "the flag works end to end" sh -c "cd '$WORK' && pnpm --silent run status status --json | node -e 'let s=\"\";process.stdin.on(\"data\",d=>s+=d).on(\"end\",()=>{const o=JSON.parse(s);if(!(\"version\" in o))process.exit(1)})'"
check implement-02 "text output is unchanged" sh -c "cd '$WORK' && pnpm --silent run status status | grep -Eq '^version +0.1.0$'"
check implement-02 "verify stamped the tree green" green_matches
TESTS_BEFORE=$(git rev-parse HEAD:test)

stage simplify "/factory:simplify" 12
snap simplify
check simplify "tests are untouched by simplify" sh -c "[ -z \"\$(git status --porcelain -- test)\" ] && [ \"\$(git rev-parse HEAD:test)\" = '$TESTS_BEFORE' ]"
check simplify "verify is green after simplify" green_matches
check simplify "simplify committed its own change" tracked_clean

forge_stage pr-02 "/factory:pr. I invoked this on purpose; open the PR for slice 02." 12
forge_check pr-02 "two PRs exist" test "$(pr_new)" = 2
forge_check pr-02 "PR 02 targets slice 01's branch" test "$(pr_field "$B2" baseRefName)" = "$B1"
forge_check pr-02 "PR 02 is not a draft" test "$(pr_field "$B2" isDraft)" = false
forge_check pr-02 "PR 02 body names its parent PR or branch" sh -c "gh pr list --head '$B2' --state all --json body --jq '.[0].body' | grep -q '$B1'"
[ "$FORGE" = 1 ] && gh pr list --state all --json number,url,baseRefName,headRefName,isDraft,title,body >"$RESULTS/prs.json"
HEAD_BEFORE=$(git rev-parse HEAD)

stage review "/factory:review" 12
check review "review wrote the handoff file" test -f "$(review_path 02)"
check review "review file has the Standards axis" review_has 02 Standards
check review "review file has the Spec axis" review_has 02 Spec
check review "review edited nothing but its file" sh -c "[ -z \"\$(git status --porcelain | grep -v 'review-02.md')\" ]"
check review "review committed nothing" test "$(git rev-parse HEAD)" = "$HEAD_BEFORE"

summary
