---
title: When to reach for factory
description: Not every change needs a spec, a plan, and a stack of pull requests. Size is about agreement and blocking edges, not line count. This page sizes a change as small, medium, or large and says which skills each size needs.
sidebar:
  order: 3
---

## What each stage costs

Every stage of the loop buys something and costs something. Knowing the
price is what lets you skip a stage on purpose instead of by accident.

| Stage | Buys | Costs |
|---|---|---|
| `spec` | Agreement on what done means, and the seams tests will run against | One round trip with the human, sometimes two |
| `plan` | Slices with blockers, branch names, acceptance checks, tracker items | One approval from the human before anything is published |
| `implement` | A red test, green code, and a verified commit per slice | Nothing extra; this is the work |
| `simplify` | A smaller, plainer diff with the same behavior | One verify run |
| `verify` | Proof the change did not lower the bar | One run per attempt, bounded by `max_iterations` |
| `pr` | A PR with real evidence, on the right parent branch | The human has to start it |
| `review` | Findings on two axes that never mask each other | Two read-only agents, plus CodeRabbit when it is logged in |

Three questions decide how much of the loop a change needs:

1. **Could two people disagree about what done means?** If yes, write a
   spec. If the request already says what the test is, skip it.
2. **Does it land as one PR, or do parts block each other?** If parts
   block each other, plan it. A plan with one slice is still worth
   writing when you want the branch name and the tracker item; a plan
   with one slice and nothing to block is a sign the change is medium,
   not large.
3. **Could the agent talk itself into green?** Always. That is why
   `verify` runs for every size, including a one-line fix.

## Three sizes

| | Small | Medium | Large |
|---|---|---|---|
| Looks like | One behavior in one or two files. The test is obvious or already exists. | One feature or fix across a few files. One seam. Lands as one PR. The behavior is worth agreeing first. | Several seams. Slices that block each other. More than one PR, or more than one context window. |
| Examples | A typo. A config default. A rename. A bug with a one-line fix and a regression test. A docs page. | A CLI flag. An endpoint with its test. A fix that touches a model and its callers. | A new subsystem. An expand-contract migration. A feature that spans packages. |
| Agree | Say it in the prompt. | `/factory:spec`, at most one grilling round. | `/factory:spec`. |
| Plan | None. | `/factory:plan` with one or two slices. | `/factory:plan` with waves. |
| Build | Edit directly. Use TDD when a seam exists. | `/factory:implement 01`. | `/factory:implement --all` in worktrees. |
| Clean | `/factory:simplify`, optional. | `/factory:simplify`. | `/factory:simplify` per slice, before its PR. |
| Gate | `/factory:verify`. | Built into implement; `--loop` arms the Stop hook. | Per slice, by the implementer agent. |
| Ship | Commit on a branch. `/factory:pr` is optional. | `/factory:pr`. | `/factory:pr` per slice, stacked. `--babysit` is optional. |
| Review | Optional. | `/factory:review`. | `/factory:review` per PR. |

Line count is a weak signal. A hundred-line change that adds one well
understood endpoint is medium. A ten-line change to a shared type that
every package imports is large, because the slices that follow it block
on it.

## Small

A small change needs no agreement and no plan. It still needs the gate.

```text
/factory:verify
```

Make the change on a branch. If there is a seam, write the failing test
first. Then run `/factory:verify`. It runs the floor check, typecheck,
lint, format, lawbook, tests with coverage, and poly-crap on the changed
functions, and exits 0, 1, or 2. Fix only what it names.

Open the PR however you normally would. `/factory:pr` works for a small
change too and writes a body from the verify evidence, but it reads
`plan.md` for the branch and tracker item, so expect it to ask when there
is no plan.

What the human sees: nothing until the diff is ready.

## Medium

A medium change is one slice that is worth agreeing on first.

```text
/factory:spec
```

```text
/factory:plan
```

```text
/factory:implement 01
```

```text
/factory:simplify
```

```text
/factory:pr
```

```text
/factory:review
```

`/factory:spec` gathers evidence from the repo, drafts numbered
requirements and the seams tests will run against, and asks at most one
round of questions, each with a recommended answer. Answer them in one
message and the spec flips to agreed.

`/factory:plan` on a medium change produces one or two slices. That looks
like overhead, but it is cheap once the spec is agreed and it earns three
things the later skills read: the slice branch name, the acceptance
checks, and the tracker item. Approve the breakdown and it publishes.

`/factory:implement 01` writes a failing test per acceptance check, makes
it pass, runs the full suite once, then runs verify until it exits 0 or
hits `max_iterations`. It never commits red. `/factory:simplify` shrinks
the diff without changing behavior and ends in verify again.

`/factory:pr` opens the PR against `base` with the verify numbers in the
body. `/factory:review` reads the diff on the standards and spec axes and
hands back findings with P0 to P3 priorities.

What the human sees: the spec's open questions, the slice breakdown, and
the PR.

## Large

A large change is several slices with blocking edges between them.

```text
/factory:spec
```

```text
/factory:plan
```

```text
/factory:implement --all
```

```text
/factory:pr
```

```text
/factory:review
```

The spec is the same. The plan is where the size shows: slices have
blockers, each slice names a `Branch` and a `Parent`, and the waves block
groups slices that share no blockers and no write set. Prefactoring that
makes the slices smaller is scheduled as slice `01`.

`/factory:implement --all` computes the frontier, the slices whose
blockers are all done, and spawns one implementer agent per frontier
slice in its own git worktree. Each agent runs the single-slice loop,
verifies, commits on its branch, and pushes. When a wave finishes, the
frontier is recomputed and the next wave starts. Two slices with
overlapping write sets never run at once.

`/factory:pr` opens one PR per slice, each against its parent branch, so
the stack reads bottom up. `--babysit` works the lowest unmerged PR first
through conflicts, review threads, and CI, and stops at merge-ready.
`/factory:review` runs per PR.

What the human sees: the spec's open questions, the slice breakdown and
wave table, a table of branches and verify results, and a stack of PRs.

## Signals you sized it wrong

Too small, and the loop will tell you mid-edit:

- The agent asks a design question while implementing. That question
  belongs in a spec's open questions, answered once.
- The diff reaches a third area of the codebase that the request never
  mentioned.
- A test needs a seam that does not exist yet.

Stop, run `/factory:spec` with what was learned, and continue from there.
The partial change is evidence, not waste.

Too large, and the artifacts will look thin:

- A plan with one slice and no blockers is a medium change. Skip the
  waves and run `/factory:implement 01`.
- A spec where every section is one sentence and the open questions list
  is empty from the start is a small change. Make the edit and run
  `/factory:verify`.

## When not to use factory

- **Throwaway spikes.** A prototype with nothing to gate gains nothing
  from verify. Write the spike, learn from it, then size the real change.
- **A repo verify cannot run in.** When the stack is not one verify
  detects and `[verify.commands]` is empty, verify exits 2 and says so.
  Run `/factory:setup` first.
- **When the human wants to drive every edit.** The loop is built to cut
  babysitting. If you want to watch every keystroke, the gates are
  friction rather than help.

`/factory:explain-diff` sits outside the loop. It explains a change, diff,
branch, or PR as an interactive HTML page and is useful at any size,
including on someone else's change.

## Growing a change

Start small when you are not sure. If the change grows, the path up is
cheap: write the spec from what you have learned, plan the rest, and keep
the work already done as slice `01`. The spec directory under
`<spec_dir>/<slug>/` is reusable, so a later request that continues the
same work extends the same spec instead of starting a new one.
