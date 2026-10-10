---
title: The verify loop
description: One command, one exit code. The script owns the stage order; the skill owns the fixes.
sidebar:
  order: 6
---

## Exit codes

`skills/verify/scripts/verify.sh` is one command with one exit code.

| Code | Meaning | What to do |
|---|---|---|
| 0 | Clean. The script wrote `.verify/green`. | Commit. |
| 1 | A gate failed. | Read `.verify/summary.txt`, `crap.json`, and `lawbook.json`. Fix only what they name. Run again. |
| 2 | The loop itself is broken: a tool or stage command is not installed, the base ref or a slice's Parent does not exist, `factory.toml` does not parse, coverage was not produced, the stack is unknown. | Fix the setup or `factory.toml`, not the code. |

Every stage scopes to the same change: the merge base of `base` and
`HEAD` against the working tree, including uncommitted and untracked
files. On a planned slice branch `base` is the slice's `Parent` from
`plan.md`. A change that already passed is not verified twice; the stamp
covers the tracked diff, every untracked file git does not ignore, and
the settings that decide the verdict (base, threshold, `llm`, request
cap), so changing one of them is a new run.

## Stages

Cheapest first. The model-judged stage runs only on a green tree.

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
| 7 | lawbook model standards, only on a green tree with `llm = true`; `warn`-level findings are advisory | 1 | skip |
| 8 | findings to `.verify/notes.json` and a live Hunk session | - | skip |

Stage commands come from `factory.toml` `[verify.commands]` or the stack
defaults in [factory.toml](./factory-toml). A stage with no command for
the stack is skipped; a command that is not installed exits 2, so the
agent fixes the setup and not the code. `BASE=<ref>` on the command line
overrides `base`.

## The floor

Stage 0 rejects any change that lowers the bar, before a single test
runs. It looks at added lines in changed source files for:

- a new suppression (`@ts-ignore`, `eslint-disable`, `# noqa`,
  `# type: ignore`, `#[allow(`, `//nolint`, `# pragma: no cover`);
- a skipped or focused test (`.skip(`, `.only(`, `@pytest.mark.skip`,
  `#[ignore]`, `t.Skip(`, `xit`, `fit`);
- a deleted test file, or fewer test definitions than before in a test
  file that was kept;
- a raised `crap_threshold` in `factory.toml` or `threshold` in
  `.poly-crap.toml` (lowering it is fine);
- a lawbook rule in `lawbook.yaml` demoted from `level: error` or deleted.

The agent never edits any of those to make a stage pass. It reports the
finding instead.

## CRAP scores

A function fails stage 6 when its CRAP score is above `crap_threshold`.
At full coverage the score equals the cyclomatic complexity, so a complex
function fails even when fully tested. The fix is tests for the uncovered
branches, a split, or both. Only functions the change touched can fail
the gate, so a slice never inherits debt it did not write. When test
files changed, every function is scored as well and the ones outside the
diff are listed as advisory. `[verify].exclude` is passed to poly-crap;
lawbook keeps its own `ignore` list in `lawbook.yaml`.

## --loop and the Stop hook

`/factory:verify --loop` writes `.factory/loop.local.md` with the session
id, `iteration: 0`, and `max_iterations`, then runs the loop. While that
file exists, the plugin's Stop hook reruns the script every time the turn
tries to end, blocks on exit 1 or 2 with the findings, bumps the
iteration, and deletes the file on exit 0 or at the cap. The bound is
`max_iterations` within one loop: a stop the hook itself forced is gated
again, so a red change cannot end the turn by trying twice.
`/factory:implement` arms it the same way.

The same hook runs on SubagentStop and reads the repository from the
payload's working directory, so an implementer agent in a git worktree is
gated on its worktree. Without `jq` the hook still blocks, with a reason
that points at `.verify/stop.tail`.

Sessions without that file are never touched. The hook is opt-in per
loop, not per session.

## Rules the skill follows

- Do not run the stages by hand. The script skips model requests on a
  red tree and remembers the last green change.
- Fix only what the summary names. Repeat until 0 or until
  `max_iterations` (default 5). At the cap, stop and report what is
  still red.
- Never edit `lawbook.yaml`, `factory.toml` thresholds, or test files to
  make a stage pass.
- Do not launch `hunk diff`; the human owns the TUI. Findings go to a
  live Hunk session when one is open, otherwise to `.verify/notes.json`.
