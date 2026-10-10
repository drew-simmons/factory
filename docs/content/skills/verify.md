---
title: verify
description: Run the verification loop on the current change, then fix only what it names until it exits 0.
---

## What it does

`/factory:verify` runs the factory verification script on the current
change: floor, typecheck, lint, format, lawbook rules, tests with
coverage, and poly-crap on changed functions. It fires when the user runs
the skill, asks to verify, check, or gate a change, or before any commit
or PR. With `--loop` it arms the Stop hook so the turn cannot end red.

The script owns the stage order. The skill owns the fixes. The full stage
table, the floor rules, and the exit codes are on
[The verify loop](../verify-loop).

## Reads

- `factory.toml` `[factory].base` and the whole `[verify]` table.
- `lawbook.yaml` when it exists.
- The merge base of `base` and `HEAD` against the working tree.

## Writes

`.verify/summary.txt`, `.verify/crap.json`, `.verify/lawbook.json`,
`.verify/notes.json`, and `.verify/green` on a clean run. With `--loop`,
`.factory/loop.local.md`.

## The loop

1. Run the script. `BASE=<ref>` overrides the base from `factory.toml`.
2. Read the exit code. 0: clean, stop. 1: a gate failed; read the summary
   and the JSON findings, fix only what they name, run again. 2: the loop
   is broken, not the code; fix the setup or `factory.toml` and leave the
   code alone.
3. Repeat until 0 or until `max_iterations` (default 5). At the cap, stop
   and report what is still red.

## Rules

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

## Done when

The script exited 0 and `.verify/green` matches the current change.

## Upstream

Wraps the `poly-crap` and `lawbook` skills for interpreting findings, and
the Floor section of `addyosmani-agent-skills/constraints` for the five
moves that lower the bar. Upstream's `CONSTRAINTS.md` is `factory.toml`
`[verify]` here; the floor guard script is folded into stage 0.
