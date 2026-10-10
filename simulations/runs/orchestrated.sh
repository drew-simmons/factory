#!/usr/bin/env sh
# orchestrated: the large-feature change driven by /factory:run large alone,
# with a scripted reply at each human gate. Proves that one skill sequences
# spec, plan, implement --all, simplify, review, the review fixes, and
# pr --stack, and that run.md carries the position between sessions: every
# gate is a fresh session that resumes from disk.
set -u
. "$SIM/lib.sh"
REPO=${SIM_REPO:-drew-simmons/factory-sim-orchestrated}

sh "$SIM/fixtures/ledger/scaffold.sh" "$WORK" "$REPO" || exit 2
cd "$WORK" || exit 2
baseline
run_md() { ls "$WORK"/docs/specs/*/run.md 2>/dev/null | head -n 1; }
run_field() { sed -n "s/^$1: *//p" "$(run_md)" | head -n 1; }

stage run-start "/factory:run large Feature: a monthly statement. \`ledger statement <file> --month 2026-09\` prints every transaction posted in that month grouped by category, each group with its subtotal, then the month's closing balance. \`ledger balance <file>\` gains --since and --until date filters (inclusive). Amounts keep the half-up cent rounding the README describes. Dates are ISO; a bad month or date is a usage error. I invoked this on purpose." 20
check run-start "run.md exists beside the spec" test -n "$(run_md)"
check run-start "run.md records the size" test "$(run_field Size)" = large
check run-start "run stopped at the spec gate" test "$(run_field "Waiting on")" = "spec answers"
check run-start "spec.md was drafted" test -n "$(spec_path)"

# Each gate is answered in a fresh session: the answer goes to the stage
# that asked, then /factory:run resumes from run.md.
stage spec-agree "Take your recommended answer for every open question in $(spec_path), update the file, clear the open questions section, and set Status: agreed. Then run /factory:run to continue; I invoked it on purpose." 25
check spec-agree "spec is agreed" grep -q '^Status: agreed' "$(spec_path)"
check spec-agree "run advanced past spec" test "$(run_field Stage)" != spec
check spec-agree "run stopped at the plan gate" test "$(run_field "Waiting on")" = "plan approval"
check spec-agree "plan-check accepts the draft plan" plan_checks_out "$(plan_path)"

stage plan-approve "The plan is approved as drafted: granularity, blocking edges, and the merge or split are all fine. Publish it, then run /factory:run to continue through implement, simplify, review, and the review fixes; I invoked it on purpose. Stop at the PR gate." 90
snap plan-approve
check plan-approve "issues were published" test "$(issue_new)" -gt "$(slice_count)"
check plan-approve "run stopped at the pr gate" test "$(run_field "Waiting on")" = pr
check plan-approve "every slice has a branch" sh -c "for id in \$(grep -E '^### [0-9][0-9] ' '$(plan_path)' | awk '{print \$2}'); do git rev-parse -q --verify \"refs/heads/\$(sed -n \"/^### \$id /,/^### /{ s/^- Branch: *//p; }\" '$(plan_path)' | head -n 1)\" >/dev/null || exit 1; done"
check plan-approve "every slice has a review file" test "$(ls "$WORK"/docs/specs/*/review-*.md 2>/dev/null | wc -l)" -ge "$(slice_count)"
check plan-approve "no unchecked P0 to P2 finding remains" sh -c "! grep -Eq '^- \\[ \\] \\[P[012]\\]' $WORK/docs/specs/*/review-*.md"
check plan-approve "implement released every worktree" test "$(git worktree list --porcelain | grep -c '^worktree ')" = 1
check plan-approve "no PR was opened before the gate" test "$(pr_new)" = 0

stage pr-go "Open the PRs now: run /factory:run to continue; I invoked it on purpose and I want the stack published." 40
check pr-go "one PR per slice exists" test "$(pr_new)" = "$(slice_count)"
check pr-go "run is done" test "$(run_field Stage)" = "done"
check pr-go "run.md has a log line per stage" test "$(grep -c '^- ' "$(run_md)")" -ge 8

summary
