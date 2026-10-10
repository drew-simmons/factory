---
title: run
description: Drive the whole loop for one change at a chosen size, stop only at the human gates, and resume from disk.
---

## What it does

`/factory:run <size> <request or spec path>` sequences the stages a
change of that size needs, as sized on
[When to reach for factory](../when-to-use): `small` is verify only;
`medium` is spec, plan, implement, simplify, review, the review fixes,
pr, and a review of the PR; `large` is the same with `implement --all`,
simplify, review, and fixes per slice, then `pr --stack`. Every stage is
an existing skill called through the Skill tool. The run skill adds no
method, only the order and a state file.

It runs only when the user starts it, because it reaches `/factory:pr`.
`/factory:run` with no arguments resumes the open run.

## Reads

- `factory.toml` for `spec_dir`.
- `<spec_dir>/<slug>/run.md`, the only state it keeps.
- Whatever each stage left on disk: `spec.md` status, `plan.md` and
  `plan-check --stack`, `.verify/green`, the `review-NN.md` boxes, the
  PR URLs. Nothing about the position lives in the conversation.

## Writes

`<spec_dir>/<slug>/run.md` with `Size`, `Stage`, `Slice`, `Waiting on`,
and one log line per stage with the evidence that proves it. The file is
committed with the spec directory.

## The human's gates

1. Spec answers. The run writes `Waiting on: spec answers`, asks, and
   ends the turn. Answer in that session or a later one; the spec skill
   applies the answers and the next `/factory:run` continues.
2. Plan approval. The same, with `Waiting on: plan approval`.
3. Starting the PRs. The same, with `Waiting on: pr`.

Everything between those gates is the agent's. A failed stage keeps its
`Stage` value and a log line saying what failed; the next `/factory:run`
retries it.

## Done when

`run.md` says `Stage: done`, every stage of the size has a log line with
evidence, and every PR of the stack is open against its parent. The
reply lists the spec path, the slices and their PRs, the review findings
left unchecked, and the evidence paths under `.verify/slices/`.

## Upstream

Wraps `mattpocock-skills/implement-spec` for the frontier and the sparse,
pointer-based handoff between stages, and the `cursor-plugins/pstack`
multi-phase plan playbook for one PR per unit with its own evidence.
Upstream's integration branch and merger agent become the stack that
`implement --all` builds and `pr --stack` publishes; upstream's single
review fix becomes `implement <NN> --from-review` per slice.
