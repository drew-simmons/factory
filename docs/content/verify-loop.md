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
| 2 | The loop itself is broken: a tool is missing, the base ref does not exist, coverage was not produced, the stack is unknown. | Fix the setup or `factory.toml`, not the code. |

Every stage scopes to the same change: the merge base of `base` and
`HEAD` against the working tree, including uncommitted and untracked
files. A change that already passed is not verified twice; the stamp
covers the tracked diff and every untracked file git does not ignore.

## Stages

Cheapest first. The model-judged stage runs only on a green tree.

| # | Stage | Fail | Missing tool |
|---|---|---|---|
| 0 | Floor: new suppressions, skipped or focused tests, deleted test files, lowered thresholds | 1 | - |
| 1 | Typecheck or syntax on changed files | 1 | 2 |
| 2 | Lint on changed files | 1 | skip |
| 3 | Format check on changed files | 1 | skip |
| 4 | `lawbook check --no-llm --changed --since <base>` when `lawbook.yaml` exists | 1 | 2 |
| 5 | Tests with coverage | 1 | 2 |
| 6 | `poly-crap --diff-base <base> --fail-above` (full scan when tests changed) | 1 | 2 |
| 7 | Lawbook model standards, only on a green tree with `llm = true` | warn | skip |
| 8 | Findings to `.verify/notes.json` and a live Hunk session | - | skip |

Stage commands come from `factory.toml` `[verify.commands]` or the stack
defaults in [factory.toml](./factory-toml). `BASE=<ref>` on the command
line overrides `base`.

## The floor

Stage 0 rejects any change that lowers the bar, before a single test
runs. It looks at added lines in changed source files for:

- a new suppression (`@ts-ignore`, `eslint-disable`, `# noqa`,
  `# type: ignore`, `#[allow(`, `//nolint`, `# pragma: no cover`);
- a skipped or focused test (`.skip(`, `.only(`, `@pytest.mark.skip`,
  `#[ignore]`, `t.Skip(`, `xit`, `fit`);
- a deleted test file;
- a lowered threshold or rule level in `factory.toml`, `lawbook.yaml`, or
  `.poly-crap.toml`.

The agent never edits any of those to make a stage pass. It reports the
finding instead.

## CRAP scores

A function fails stage 6 when its CRAP score is above `crap_threshold`.
At full coverage the score equals the cyclomatic complexity, so a complex
function fails even when fully tested. The fix is tests for the uncovered
branches, a split, or both. When test files changed, every function is
scored, not only the changed ones.

## --loop and the Stop hook

`/factory:verify --loop` writes `.factory/loop.local.md` with the session
id, `iteration: 0`, and `max_iterations`, then runs the loop. While that
file exists, the plugin's Stop hook reruns the script when the turn tries
to end, blocks on exit 1 with the findings, and deletes the file on exit
0 or at the cap. `/factory:implement` arms it the same way.

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
