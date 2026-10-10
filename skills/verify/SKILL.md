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

1. Run `sh ${CLAUDE_SKILL_DIR}/scripts/verify.sh` as the whole command:
   nothing piped to `tail`, no `; echo $?` after it. The tool result
   carries the exit code and the output. `BASE=<ref>` before the command
   overrides the base from `factory.toml`.
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

Cheapest first, all scoped to the merge base against the working tree, untracked
files included. On a planned slice branch the base is the slice's `Parent` from
`plan.md`, so the stack above it is not re-judged; otherwise it is `base` from
`factory.toml`. A base or Parent that does not resolve is exit 2, never a
silent fallback. Stack commands come from `factory.toml` `[verify.commands]` or
the defaults in `${CLAUDE_PLUGIN_ROOT}/skills/setup/references/factory-toml.md`;
a stage with no command for the stack is skipped, a command that is not
installed is exit 2.

| # | Stage | Fail | Missing tool |
|---|---|---|---|
| 0 | floor: new suppressions, skipped or deleted tests, removed test definitions, a raised CRAP threshold, a demoted or deleted lawbook rule | 1 | - |
| 0b | plan: a changed `plan.md` still describes a linear stack whose waves agree with its blockers | 1 | - |
| 1 | typecheck or syntax on changed files | 1 | 2 |
| 2 | lint on changed files | 1 | 2 |
| 3 | format check on changed files | 1 | 2 |
| 4 | `lawbook check --no-llm --changed --since <base>` when `lawbook.yaml` exists | 1 | 2 |
| 5 | tests with coverage | 1 | 2 |
| 6 | `poly-crap --diff-base <base> --fail-above` on changed functions; the full scan after a test change is advisory | 1 | 2 |
| 7 | lawbook model standards, only on a green tree with `llm = true`, on the changed lines when the installed lawbook has `--changed-lines`; `warn`-level findings are advisory | 1 | skip |
| 8 | findings to `.verify/notes.json` and a live Hunk session | - | skip |

## --loop

`/factory:verify --loop` runs `sh ${CLAUDE_SKILL_DIR}/scripts/verify.sh
--loop`. The script writes `.factory/loop.local.md` (blank `session_id`,
so the hook acts for any session, `iteration: 0`, and `max_iterations`)
before the first stage, then runs the loop. While that file exists the
plugin's Stop and SubagentStop hooks rerun the script every time the turn
tries to end, block on red with the findings, and delete the file on exit 0
or at the cap. The bound is `max_iterations` within one loop, not one
forced continuation. `/factory:implement` arms it the same way. Do not
write the file by hand.

## Rules

- Shell discipline: one command per Bash call, with no `&&`, `;`, pipes,
  redirects, or `$(...)`. A tool grant matches the command word, so a
  compound command is denied whole, and one denied command is not a denied
  tool: retry with a single, simpler command. Read exit codes and output
  from the tool result. Create and edit files with the Write and Edit
  tools, never a shell heredoc.
- A function fails when its CRAP score is above the threshold. At full
  coverage the score equals the complexity, so a complex function fails
  even when fully tested. Fix with tests for uncovered branches, a split,
  or both.
- Do not run the stages by hand. The script skips model requests on a red
  tree and remembers the last green change.
- Never edit `lawbook.yaml`, `factory.toml` thresholds, or test files to
  make a stage pass. Report the finding instead.
- A standard finding on a line the change did not touch is not the
  change's to fix. lawbook 0.4 and later drops it; with an older lawbook,
  report it and leave the line alone.
- Do not launch `hunk diff`; the human owns the TUI.
