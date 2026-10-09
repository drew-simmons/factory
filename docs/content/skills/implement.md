---
title: implement
description: Build one planned slice with test-driven development, or walk the whole plan frontier with implementer agents in git worktrees.
---

## What it does

`/factory:implement <NN>` builds one slice from `plan.md` as a tracer
bullet: red test, green code, verify, commit. `/factory:implement --all`
does that for every slice on the frontier, each in its own worktree. It
fires when the user runs the skill, asks to implement a slice or ticket,
build the next slice, or work the plan.

Each slice ends with `/factory:verify` and is never committed red.

## Reads

- `factory.toml` for `base` and `[verify].max_iterations`.
- `plan.md` for the slice's blockers, `Branch`, `Parent`, and acceptance
  checks.
- `spec.md` for the requirements the slice cites and the seams.

## Single slice

1. Confirm every blocker of the slice is done and the current branch is
   the slice's `Branch`. If the branch does not exist, create it from
   `Parent`.
2. Mark the slice claimed in its tracker item or issue file.
3. For each acceptance check: write one failing test at the agreed seam,
   confirm it fails for the right reason, write the smallest code that
   passes, run the file. One behavior per cycle.
4. Run the full suite once. Write `.factory/loop.local.md` so the Stop
   hook backstops the loop, then run `/factory:verify`. On exit 1, fix
   only what it names and rerun, up to `max_iterations`.
5. Commit with a conventional message that cites the slice and
   requirement ids, for example `feat(auth): add session refresh (02, R3)`.
   Mark the slice done. Reply with the branch, the commit, the tests
   added, and the verify result.

## All frontier slices

1. Compute the frontier from `plan.md`: slices whose blockers are all
   done.
2. For each frontier slice, spawn one `factory:implementer` agent in a
   worktree with the slice id, spec path, plan path, branch, and parent.
   Two slices with overlapping write sets never run at once.
3. When an agent reports done, confirm its branch is green and pushed,
   mark the slice done, recompute the frontier, and spawn the next wave.
4. Reply with a table of slices, branches, and verify results, and point
   at `/factory:pr` for the stack.

The implementer agent completes exactly one slice. It stops and asks the
parent when a slice conflicts with the spec, has no verifiable outcome,
or needs a decision the spec does not make. It never opens a PR, merges,
or touches the parent branch.

## Rules

- Typecheck and run the single test file often; run the full suite once
  before verify. Use the project's package manager.
- Never commit a red tree. Never weaken a test, skip a test, or add a
  suppression to get green; verify treats those as failures.
- Refactoring stays out of the red-green loop. It belongs to
  `/factory:simplify`.

## Done when

The slice's acceptance checks each have a passing test, `/factory:verify`
exited 0, and the commit is on the slice branch.

## Upstream

Wraps `mattpocock-skills/tdd` for the red-green loop, seams, and
anti-patterns; `mattpocock-skills/implement` and `implement-spec` for the
single-ticket flow and frontier orchestration; and the `cursor-plugins/pstack`
prove-it-works principle. Upstream's single integration branch becomes a
stack of slice branches.
