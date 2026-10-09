---
name: verify
description: Run the factory verification loop on the current change (typecheck, lint, format, lawbook rules, tests with coverage, and poly-crap on changed functions), then fix only what it names until it exits 0. Use when the user runs /factory:verify, asks to verify, check, or gate a change, or before any commit or PR. With --loop it arms the Stop hook so the turn cannot end red.
license: MIT
compatibility: Requires git, jq, and the stack's test runner. poly-crap and lawbook must be installed for stages 4 and 6.
metadata:
  upstream: "drew-simmons-poly-crap/skill, drew-simmons-lawbook/skill, addyosmani-agent-skills/constraints"
allowed-tools: Bash(sh ${CLAUDE_SKILL_DIR}/scripts/verify.sh *) Bash(jq:*) Bash(git:*) Read Edit Write
---

# verify

One command, one exit code. The script owns the stage order; this skill
owns the fixes.

## Load

- `${CLAUDE_PLUGIN_ROOT}/upstream/drew-simmons-poly-crap/skills/poly-crap/SKILL.md`
  when a CRAP finding needs interpreting.
- `${CLAUDE_PLUGIN_ROOT}/upstream/drew-simmons-lawbook/skills/lawbook/SKILL.md`
  when a lawbook finding or rule needs interpreting.
- `${CLAUDE_PLUGIN_ROOT}/upstream/addyosmani-agent-skills/skills/constraint-driven-development/SKILL.md`,
  section "Floor", for the five moves that lower the bar.

## Translate

- Upstream's `CONSTRAINTS.md` is `factory.toml` `[verify]` here. Do not
  create `CONSTRAINTS.md`.
- Upstream's floor guard script is folded into stage 0 of `verify.sh`.

## The loop

1. Run `sh ${CLAUDE_SKILL_DIR}/scripts/verify.sh`. `BASE=<ref>` overrides
   the base from `factory.toml`.
2. Read the exit code.
   - 0: clean. The script wrote `.verify/green`. Stop.
   - 1: a gate failed. Read `.verify/summary.txt`, `.verify/crap.json`, and
     `.verify/lawbook.json`. Fix only what they name, then run again.
   - 2: the loop is broken, not the code. The output names the missing
     tool, ref, coverage file, or command. Fix the setup or `factory.toml`
     and leave the code alone.
3. Repeat until 0 or until `max_iterations` from `factory.toml`
   (default 5). At the cap, stop and report what is still red; do not
   lower a threshold, skip a test, or add a suppression to get there.

## Stages

Cheapest first, all scoped to the merge base of `base` against the working
tree, untracked files included. Stack commands come from `factory.toml`
`[verify.commands]` or the defaults in
`${CLAUDE_PLUGIN_ROOT}/skills/setup/references/factory-toml.md`.

| # | Stage | Fail | Missing tool |
|---|---|---|---|
| 0 | floor: new suppressions, skipped or deleted tests, stripped assertions, lowered thresholds | 1 | - |
| 1 | typecheck or syntax on changed files | 1 | 2 |
| 2 | lint on changed files | 1 | skip |
| 3 | format check on changed files | 1 | skip |
| 4 | `lawbook check --no-llm --changed --since <base>` when `lawbook.yaml` exists | 1 | 2 |
| 5 | tests with coverage | 1 | 2 |
| 6 | `poly-crap --diff-base <base> --fail-above` (full scan when tests changed) | 1 | 2 |
| 7 | lawbook model standards, only on a green tree with `llm = true` | warn | skip |
| 8 | findings to `.verify/notes.json` and a live Hunk session | - | skip |

## --loop

`/factory:verify --loop` writes `.factory/loop.local.md` with the session
id, `iteration: 0`, and `max_iterations`, then runs the loop. While that
file exists the plugin's Stop hook reruns the script when the turn tries to
end, blocks on exit 1 with the findings, and deletes the file on exit 0 or
at the cap. `/factory:implement` arms it the same way.

## Rules

- A function fails when its CRAP score is above the threshold. At full
  coverage the score equals the complexity, so a complex function fails
  even when fully tested. Fix with tests for uncovered branches, a split,
  or both.
- Do not run the stages by hand. The script skips model requests on a red
  tree and remembers the last green change.
- Never edit `lawbook.yaml`, `factory.toml` thresholds, or test files to
  make a stage pass. Report the finding instead.
- Do not launch `hunk diff`; the human owns the TUI.
