---
name: simplify
description: Remove unneeded complexity and AI-generated slop from the current change without altering behavior. Use when the user runs /factory:simplify, asks to simplify, clean up, deslop, or reduce the diff before review. Scope is the diff against the base branch only; ends by running /factory:verify.
license: MIT
compatibility: Requires git and the repository's test runner.
metadata:
  upstream: "addyosmani-agent-skills/simplify, cursor-plugins/deslop, cursor-plugins/pstack-principles, mattpocock-skills/code-review"
allowed-tools: Bash(git:*) Read Edit Glob Grep
---

# simplify

Make the change smaller and plainer while every test keeps passing.

## Load

- `${CLAUDE_PLUGIN_ROOT}/upstream/addyosmani-agent-skills/skills/code-simplification/SKILL.md`:
  the five principles, Chesterton's fence, one change at a time with tests
  after each.
- `${CLAUDE_PLUGIN_ROOT}/upstream/cursor-plugins/cursor-team-kit/skills/deslop/SKILL.md`:
  the slop list: narrating comments, defensive try/catch, `any` casts,
  deep nesting.
- `${CLAUDE_PLUGIN_ROOT}/upstream/cursor-plugins/pstack/skills/principle-subtract-before-you-add/SKILL.md`
  and `principle-laziness-protocol/SKILL.md`: delete first, smallest diff,
  flat call hierarchy.
- The smell baseline in
  `${CLAUDE_PLUGIN_ROOT}/upstream/mattpocock-skills/skills/engineering/code-review/SKILL.md`
  (Speculative Generality, Middle Man, Data Clumps, and the rest).

## Translate

- "Diff against main" means the diff against `base` from `factory.toml`
  (merge base to working tree, untracked files included).
- Upstream's protected blocks use `simplify-ignore-start` and
  `simplify-ignore-end` markers. Leave anything between them untouched.
  The hook that hides them is not installed by this plugin; respect the
  markers by reading, not by tooling.

## Factory rules

- Behavior stays identical: same outputs, errors, side effects, and order.
  Existing tests pass without edits. When unsure, do not make the change.
- Touch only lines the change introduced. No drive-by refactors.
- Prefer deletion over rewriting. Prefer a clear name over a comment.
- Keep explicit code over compact code: no nested ternaries, no dense
  one-liners, no clever reduce chains.
- Do not remove a test, an assertion, or a type to make the diff smaller.

## Steps

1. List the changed files: `git diff --name-only <merge-base>` plus
   untracked files. Read each one in full before editing.
2. For each file, in this order: delete dead code and stub references; drop
   narrating comments and defensive guards the spec does not ask for; flatten
   nesting with early returns; replace abstractions with one caller by the
   call itself; name the smells left over from the baseline and fix the
   ones that are judgement-free.
3. After every edit run the file's tests. Revert an edit that changes a
   test result.
4. Run `/factory:verify`. Fix only what it names.
5. Reply in one to three sentences: what was removed, what was kept and
   why, and the verify result.

## Done when

The diff is smaller or plainer than before, every test passes unchanged,
and `/factory:verify` exited 0.
