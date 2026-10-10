---
title: simplify
description: Make the change smaller and plainer while every test keeps passing.
---

## What it does

`/factory:simplify` removes unneeded complexity and AI-generated slop from
the current change without altering behavior. It fires when the user runs
the skill or asks to simplify, clean up, deslop, or reduce the diff before
review. Scope is the diff against `base` only. It ends by running
`/factory:verify`.

## Reads

- `factory.toml` for `base`.
- Every changed file in full, from the merge base to the working tree,
  untracked files included.

## Steps

1. List the changed files. Read each one in full before editing.
2. For each file, in this order: delete dead code and stub references;
   drop narrating comments and defensive guards the spec does not ask
   for; flatten nesting with early returns; replace abstractions with one
   caller by the call itself; name the smells left over from the baseline
   and fix the ones that are judgement-free.
3. After every edit, run the file's tests. Revert an edit that changes a
   test result.
4. Run `/factory:verify`. Fix only what it names.
5. When verify is green and the diff is not empty, commit as
   `refactor(<scope>): simplify slice NN`. Never amend. A red tree stays
   uncommitted and is reported.
6. Reply in one to three sentences: what was removed, what was kept and
   why, the verify result, and the commit.

## Rules

- Behavior stays identical: same outputs, errors, side effects, and
  order. Existing tests pass without edits. When unsure, do not make the
  change.
- Touch only lines the change introduced. No drive-by refactors.
- Prefer deletion over rewriting. Prefer a clear name over a comment.
- Keep explicit code over compact code: no nested ternaries, no dense
  one-liners, no clever reduce chains.
- Do not remove a test, an assertion, or a type to make the diff smaller.
- Leave anything between `simplify-ignore-start` and
  `simplify-ignore-end` markers untouched.

## Done when

The diff is smaller or plainer than before, every test passes unchanged,
`/factory:verify` exited 0, and the simplification is committed.

## Upstream

Wraps `addyosmani-agent-skills/simplify` for the five principles and
one change at a time with tests after each; `cursor-plugins/deslop` for
the slop list; the `cursor-plugins/pstack` subtract-before-you-add and
laziness principles; and the smell baseline from
`mattpocock-skills/code-review`.
