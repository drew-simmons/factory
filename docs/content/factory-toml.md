---
title: factory.toml
description: One file per repository, written by /factory:setup. Every key has a default, so a short file is a correct file.
sidebar:
  order: 5
---

## Schema

```toml
[factory]
spec_dir = "docs/specs"   # <spec_dir>/<slug>/{spec.md,plan.md,issues/}
base = "origin/main"      # branch every diff and stack is measured against

[tracker]
kind = "github"           # github | gitlab | jira | local
jira_site = ""            # mysite.atlassian.net (jira only)
jira_project = ""         # project key such as ENG (jira only)
jira_type = "Task"        # work item type for slices (jira only)

[verify]
crap_threshold = 5        # poly-crap --threshold
coverage = ""             # lcov path when auto-detection fails
llm = false               # run lawbook model-judged standards on a green tree
max_iterations = 5        # cap for the implement <-> verify loop
exclude = []              # shell globs left out of every stage, e.g. ["upstream/*"]

[verify.commands]         # each key overrides the stack default; "" keeps it
typecheck = ""
lint = ""
format = ""
test = ""                 # must write the lcov file named in [verify].coverage
```

`factory.toml` lives at the repository root. Every skill reads it first
and falls back to detection when a key is missing or the file is absent.
Omit keys that match the defaults.

## Stack defaults

The verify script detects the stack from marker files. First match wins.

| Marker | Stack | typecheck | lint | format | test (writes lcov) |
|---|---|---|---|---|---|
| `pnpm-lock.yaml`, `package.json` | node | `<pm> exec tsc --noEmit` (if tsconfig), else `node --check` | `<pm> exec eslint <files>` (if config) | `<pm> exec prettier --check <files>` (if config) | `<pm> test`; lcov at `coverage/lcov.info` or `lcov.info` |
| `pyproject.toml`, `uv.lock` | python | `uv run python -m compileall -q <files>` | `uvx ruff check <files>` | `uvx ruff format --check <files>` | `uv run pytest --cov --cov-report=lcov:.verify/lcov.info` |
| `Cargo.toml` | rust | `cargo check` | `cargo clippy -- -D warnings` | `cargo fmt --check` | `cargo llvm-cov --lcov --output-path .verify/lcov.info` |
| `go.mod` | go | `go vet ./...` | `golangci-lint run` (if present) | `gofmt -l <files>` | `go test -coverprofile=.verify/coverage.out ./...` |

For node, `<pm>` follows the lockfile: `pnpm` with `pnpm-lock.yaml`,
`yarn` with `yarn.lock`, otherwise `npm`. A repo with none of these
markers needs `[verify.commands]` filled in, or the verify script exits 2.

## Tracker kinds

- `local`: one file per slice at `<spec_dir>/<slug>/issues/NN-<task>.md`.
- `github`: `gh issue create` per slice plus one tracking issue.
- `gitlab`: `glab issue create` per slice plus one tracking issue.
- `jira`: `acli jira workitem create` per slice under a parent work item.

`/factory:plan` publishes only after the user approves the breakdown. The
exact commands live in the plan skill's `references/trackers.md`.
