---
title: setup
description: Write factory.toml once per repository so the other skills do not ask the same questions on every run.
---

## What it does

`/factory:setup` configures a repository for the factory skills by
writing `factory.toml`: the spec directory, the base branch, the issue
tracker, and the verify commands. It detects the stack and remote host
first and asks only what it cannot detect.

Only the user may start this skill. If the model reaches it on its own,
it stops and asks before writing anything.

## Reads

- Stack marker files: `pnpm-lock.yaml`, `package.json`, `pyproject.toml`,
  `uv.lock`, `Cargo.toml`, `go.mod`.
- The remote host from `git remote -v` and the default branch from
  `git symbolic-ref refs/remotes/origin/HEAD`.
- `lawbook.yaml`, an existing coverage file, `tsconfig.json`.
- An existing `factory.toml`, which it updates in place and keeps user
  edits in.

## Steps

1. Detect everything in the list above. Never ask for it.
2. Report the detected values in a few lines.
3. Ask, one question at a time, only for what detection left open: the
   tracker kind when the remote is ambiguous or local files or Jira might
   be preferred; the Jira site, project key, and work item type; a test
   command when no stack marker matched. Recommend an answer with every
   question.
4. Check the tracker tool is usable with `gh auth status`,
   `glab auth status`, or `acli jira auth status`. Report a failure; never
   run a login.
5. Show the draft `factory.toml`. Write it after the user accepts, with
   default-valued keys omitted.
6. Add `.verify/` and `.factory/` to `.gitignore` if they are not already
   ignored.

## Done when

`factory.toml` exists, every key in it was either detected or chosen by
the user, and the reply lists the verify commands the stack default will
run. See [factory.toml](../factory-toml) for the schema.

## Upstream

Wraps the explore-then-confirm pattern from `mattpocock-skills/setup`.
Upstream writes `docs/agents/*.md` and a CLAUDE.md block; factory writes
`factory.toml` only.
