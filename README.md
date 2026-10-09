# factory

A Claude Code plugin that runs a software factory loop for coding agents:

```text
/factory:setup  (once per repo)
/factory:spec -> /factory:plan -> /factory:implement -> /factory:simplify
                                        ^                      |
                                        |                      v
                                        +---- /factory:verify --+--> /factory:pr -> /factory:review
```

The point is to cut the babysitting. The human agrees a spec and a plan,
then the agent works slices one at a time or in parallel worktrees, each
slice ending in a verification loop that it cannot talk its way out of, and
each landing as one PR in a stack.

The skills are thin, owned wrappers. The method inside them comes from
upstream skills by Matt Pocock, the Cursor pstack team, Addy Osmani, and
CodeRabbit, vendored verbatim under `upstream/` and pinned by content hash,
plus Drew's own tools: [poly-crap](https://github.com/drew-simmons/poly-crap),
[lawbook](https://github.com/drew-simmons/lawbook), and
[verify-loop](https://github.com/drew-simmons/verify-loop).

## Install

From the marketplace in this repo:

```bash
claude plugin marketplace add drew-simmons/factory
```

```bash
claude plugin install factory@drew-simmons
```

For local development, load the checkout in place:

```bash
claude --plugin-dir /path/to/factory
```

Tools the skills call: `git`, `jq`, `poly-crap`, `lawbook`, and one of
`gh`, `glab`, or `acli` for the tracker. `coderabbit` is optional. The
SessionStart hook prints which ones are present.

## Skills

| Skill | What it does | Writes |
|---|---|---|
| `setup` | Detects the stack and remote, asks what it cannot detect, writes `factory.toml`. | `factory.toml` |
| `spec` | Aligns human and agent on numbered requirements, test seams, and open questions. No tracker. | `docs/specs/<slug>/spec.md` |
| `plan` | Slices the spec into tracer bullets with blockers, stacked branch names, and parallel waves; publishes to GitHub, GitLab, Jira, or local files after approval. | `plan.md`, tracker items |
| `implement` | One slice with TDD, or the whole frontier with implementer agents in worktrees. Ends in verify. Never commits red. | commits on `<slug>/NN-<task>` |
| `simplify` | Removes slop and needless complexity from the diff without changing behavior. Ends in verify. | edits |
| `verify` | Floor, typecheck, lint, format, lawbook, tests with coverage, poly-crap, in that order. Fix only what it names until exit 0. | `.verify/` |
| `pr` | Opens one PR per slice against its parent branch with real evidence. Never draft, never merge. | a PR |
| `review` | Standards and spec axes in parallel read-only agents, plus CodeRabbit CLI when authenticated. | findings |
| `explain-diff` | Writes a rich, interactive HTML explanation of a change, diff, branch, or PR with background, intuition, code walkthrough, and quiz. Outside the loop. | `.temp/<date>-explanation-<slug>.html` |

Three skills say in their description that only the user may start them:
`setup`, `plan` (for publishing), and `pr`. The frontmatter stays within the
Agent Skills spec, so there is no `disable-model-invocation` key; the
description and the first step carry the rule.

## factory.toml

One file per repository, written by `/factory:setup`. Every key has a
default, so a short file is a correct file.

```toml
[factory]
spec_dir = "docs/specs"
base = "origin/main"

[tracker]
kind = "github"           # github | gitlab | jira | local

[verify]
crap_threshold = 5
max_iterations = 5
exclude = ["vendor/*"]

[verify.commands]
test = "pnpm test -- --coverage"
```

The full schema and the stack defaults are in
[skills/setup/references/factory-toml.md](skills/setup/references/factory-toml.md).

## The verify loop

`skills/verify/scripts/verify.sh` is one command with one exit code: 0
clean, 1 a gate failed, 2 the loop itself is broken. Stage 0 rejects any
change that lowers the bar (a new suppression, a skipped or deleted test, a
lowered threshold). Stages 1 to 6 run cheapest first and stop sending model
requests on a red tree. Findings land in `.verify/` and in a live
[Hunk](https://github.com/modem-dev/hunk) session when one is open.

`/factory:verify --loop` and `/factory:implement` write
`.factory/loop.local.md`. While it exists, the plugin's Stop hook reruns the
script when the turn tries to end and blocks on red with the findings, up
to `max_iterations`. Sessions without that file are never touched.

## Upstream skills

`upstream/upstream.json` lists every vendored entry with its repo, ref,
resolved commit, paths, license, and a content hash. Vendored files are
never edited by hand; a wrapper's Translate section adapts them.

```bash
uv run --script scripts/sync-upstream.py check
```

```bash
uv run --script scripts/sync-upstream.py diff mattpocock-skills/tdd
```

```bash
uv run --script scripts/sync-upstream.py update mattpocock-skills/tdd --ref v1.4.0
```

```bash
uv run --script scripts/sync-upstream.py verify
```

`check` reports entries behind their ref and newer tags. `diff` shows the
upstream change since the pinned commit. `update` replaces the copy,
re-pins, and regenerates `THIRD_PARTY_NOTICES.md`; it refuses to run over a
hand-edited copy. `verify` runs in CI. A weekly workflow opens a PR when
upstream moves, with the diff in the body.

## Development

```bash
uv run pytest
```

```bash
claude plugin validate skills --strict
```

```bash
claude plugin eval . --threshold 0.8
```

The eval case `verify-runs-on-fixture` needs `--scaffold` and Bash grants;
see the comment at the top of its `scaffold.sh`.

## License

MIT. Vendored files keep their own licenses; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
