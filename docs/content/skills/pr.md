---
title: pr
description: Publish one green slice as one PR in a base-branch stack and hand it to the reviewer, human or bot.
---

## What it does

`/factory:pr` opens a pull request or merge request for the current slice
branch, targeting its parent branch in the stack, with a body built from
the verify evidence. It runs only when the user explicitly invokes it or
asks to open a PR. It never opens one on its own initiative, refuses on a
red tree, never opens drafts, and never merges.

## Reads

- `factory.toml` for `base`.
- `plan.md` for the slice's `Branch`, `Parent`, and tracker item.
- `.verify/green` and `.verify/summary.txt` for the evidence.
- `git remote -v` and `gh auth status` or `glab auth status`.

## Steps

1. Confirm the user invoked the skill. Resolve the forge and check auth.
   Stop on failure; never run a login.
2. Refuse when `.verify/green` does not match the current change or when
   there are uncommitted changes. Do not commit them.
3. Rebase the slice branch onto the tip of its parent when the parent
   moved, then rerun `/factory:verify`.
4. Push with `git push -u origin <branch>`.
5. Write the body from the PR template, with the verification numbers
   from `.verify/summary.txt` and a mention of the tracker item.
6. Create or update the PR with `--base <parent>` (the root slice targets
   `base`), read it back, and confirm base, head, title, and that it is
   not a draft. An open PR for the same head branch is reused.
7. If the repository has a CodeRabbit config or a GitHub app review will
   run, stop and post the URL. Otherwise say no bot review is configured
   and suggest `/factory:review`.

## --stack

`/factory:pr --stack` runs the steps above once per slice, bottom up, for
every slice in `plan.md` whose branch exists. Each body carries a stack
table (`NN | branch | parent | PR`); once the last PR is open the earlier
bodies are updated so every table is complete. The first slice that
refuses, red or dirty, stops the walk, and the reply says which PRs were
opened.

## After the PR

Driving the stack to merge-ready through conflicts, review threads, and
CI is [`steward`](./steward).

## Rules

- Never `--draft`. Never merge. Never force-push. Never push `base`.
- Plain words, short sentences, no em dashes in the body.

## Done when

The PR URL is posted, it targets the right parent, it is not a draft, and
the body carries real verify evidence.

## Upstream

Wraps the `cursor-plugins/pstack` opening-a-PR playbook for commits,
titles, descriptions, stacks, and readiness, and `mattpocock-skills/pr`
for the evidence and merge-danger sections. Upstream's Origin, Graphite,
and swarm tools do not exist here; only `gh` and `glab` are used.
