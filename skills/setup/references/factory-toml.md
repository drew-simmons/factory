# factory.toml

`factory.toml` lives at the repository root. Every factory skill reads it
first and falls back to detection when a key is missing or the file is
absent. Keep it short; omit keys that match the defaults.

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

## Stack defaults

The verify script detects the stack from marker files, first match wins.

| Marker | Stack | typecheck | lint | format | test (writes lcov) |
|---|---|---|---|---|---|
| `pnpm-lock.yaml`, `package.json` | node | `pnpm exec tsc --noEmit` (if tsconfig) | `pnpm exec eslint <files>` | `pnpm exec prettier --check <files>` | `pnpm test` with lcov at `coverage/lcov.info` |
| `pyproject.toml`, `uv.lock` | python | `uv run python -m compileall -q <files>` | `uvx ruff check <files>` | `uvx ruff format --check <files>` | `uv run pytest --cov --cov-report=lcov:.verify/lcov.info` |
| `Cargo.toml` | rust | `cargo check` | `cargo clippy -- -D warnings` | `cargo fmt --check` | `cargo llvm-cov --lcov --output-path .verify/lcov.info` |
| `go.mod` | go | `go vet ./...` | `golangci-lint run` (if present) | `gofmt -l <files>` | `go test -coverprofile=.verify/coverage.out ./...` |

A repo with none of these markers needs `[verify.commands]` filled in, or the
verify script exits 2.

## Tracker kinds

- `local`: one file per slice at `<spec_dir>/<slug>/issues/NN-<task>.md`.
- `github`: `gh issue create` per slice plus one tracking issue.
- `gitlab`: `glab issue create` per slice plus one tracking issue.
- `jira`: `acli jira workitem create` per slice under a parent work item.

See `../../plan/references/trackers.md` for the exact commands.
