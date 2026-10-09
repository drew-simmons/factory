---
title: Quickstart
description: Install the plugin, set up one repository, and run the loop once.
sidebar:
  order: 2
---

## Install

From the marketplace in the factory repository:

```bash
claude plugin marketplace add drew-simmons/factory
```

```bash
claude plugin install factory@drew-simmons
```

For local development, load a checkout in place:

```bash
claude --plugin-dir /path/to/factory
```

## Tools the skills call

The skills shell out to `git`, `jq`, `poly-crap`, `lawbook`, and one of
`gh`, `glab`, or `acli` for the tracker. `coderabbit` is optional and only
used by `review` and `pr --babysit` when it is authenticated.

The SessionStart hook prints which of these are present when a session
starts, so a missing tool shows up before a skill needs it.

## Set up a repository

Run this once per repository:

```text
/factory:setup
```

It detects the stack from marker files (`pnpm-lock.yaml`, `package.json`,
`pyproject.toml`, `uv.lock`, `Cargo.toml`, `go.mod`), the remote host, the
default branch, and an existing `lawbook.yaml`. It asks only for what it
cannot detect, recommends an answer with each question, shows the draft
`factory.toml`, and writes it after you accept. Only the user may start
this skill. See [factory.toml](./factory-toml) for every key.

## Run the loop once

Pick a medium-sized change: one feature or fix, a few files, worth
agreeing on first. Then run the skills in order.

```text
/factory:spec
```

Answer the open questions in one message. The spec flips to agreed.

```text
/factory:plan
```

Approve the slice breakdown. It publishes to the tracker and writes
`plan.md`.

```text
/factory:implement 01
```

The agent writes a failing test per acceptance check, makes it pass, and
runs verify until it exits 0. It never commits red.

```text
/factory:simplify
```

The diff gets smaller and plainer with the same behavior.

```text
/factory:pr
```

One PR against the base branch, with the verify evidence in the body.
Only the user may start this skill.

```text
/factory:review
```

Findings on the standards and spec axes, P0 to P3, without editing code.

## Next

- [When to reach for factory](./when-to-use) says which of those steps a
  small or a large change needs.
- [The loop](./workflow) names the artifact each step writes.
