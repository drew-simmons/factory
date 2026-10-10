---
title: plan
description: Break an agreed spec into vertical slices with blocking edges, stacked branch names, and parallel waves.
---

## What it does

`/factory:plan` turns `spec.md` into slices an implementer can take one at
a time, in parallel worktrees, each landing as one PR in a stack. It
fires when the user runs the skill, asks to plan a spec, asks to create
tickets or issues from a spec, or asks to split work into slices.

Publishing to a remote tracker happens only after the user approves the
breakdown.

## Reads

- `factory.toml` for `spec_dir`, `base`, and `[tracker]`. Without a
  tracker kind it defaults to `local` and says so.
- `spec.md`, which must have `Status: agreed`. A draft spec is refused
  with a pointer at `/factory:spec`.
- The code around the seams the spec names, looking for prefactoring that
  makes the slices smaller.

## Writes

`<spec_dir>/<slug>/plan.md`. Each slice is a tracer bullet: one narrow
path through every layer, demoable on its own, sized for one fresh
context window. A slice names its requirement ids, blockers, `Branch`,
`Parent`, what it delivers, observable acceptance checks, and its tracker
item. A `waves` block groups slices that can run in parallel.

Then, per `tracker.kind`: one issue file per slice for `local`, or a
tracking item and one item per slice on GitHub, GitLab, or Jira, blockers
before dependents, with the `Tracker:` lines filled in afterwards.

## Rules

- `Branch` is `<slug>/NN-<task>`. The root slice's parent is `base`. Each
  later slice's parent is the branch of the slice it is blocked by.
- Slices in one wave have disjoint write sets. Two slices that touch the
  same files go in different waves with one blocking the other.
- Prefactoring is scheduled as slice `01`.
- No file paths or code in slices; they go stale. A prototype snippet that
  encodes a decision is the one exception.
- Acceptance checks are observable: a test name, a command and its
  output, a screen state.
- `plan-check.py` in the skill's `scripts/` reads the plan and fails on a
  slice blocked by two independent chains, a `Parent` that is not `base` or
  another slice's branch, a parent slice missing from `Blocked by`, or
  waves that disagree with the blockers. The breakdown is shown only when
  it exits 0, and verify runs it again whenever a plan changes.
- After publishing, slice status lives in the tracker; `plan.md` is never
  edited to track progress, so the copy in every slice commit stays
  identical.

## Steps

1. Read the spec and the code around its seams.
2. Draft the slices and compute waves. Write the draft and run
   `plan-check.py` until it exits 0.
3. Present the breakdown as a numbered list and ask three questions:
   granularity, blocking edges, merge or split. Iterate until the user
   approves. Do not publish before approval.
4. Update `plan.md` with what the user changed; `plan-check.py` again.
5. Publish.
6. Reply with the plan path, the wave table, and the first frontier: the
   slices with no blockers, ready for `/factory:implement`.

## Done when

`plan.md` exists with every slice traced to requirement ids, a valid
`waves` block, and a `Tracker:` line per slice.

## Upstream

Wraps `mattpocock-skills/to-tickets` for tracer-bullet slices, blocking
edges, expand-contract for wide refactors, and the frontier;
`addyosmani-agent-skills/planning` for the dependency graph and
acceptance criteria per task; and the `cursor-plugins/pstack`
multi-phase plan playbook for one PR per section with its own evidence.
