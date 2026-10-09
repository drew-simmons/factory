---
title: Skills
description: One page per skill. Each skill is a portable SKILL.md wrapper over vendored upstream method files, with factory's own rules on top.
---

## At a glance

| Skill | What it does | Writes |
|---|---|---|
| [`setup`](./setup) | Detects the stack and remote, asks what it cannot detect, writes `factory.toml`. | `factory.toml` |
| [`spec`](./spec) | Aligns human and agent on numbered requirements, test seams, and open questions. No tracker. | `docs/specs/<slug>/spec.md` |
| [`plan`](./plan) | Slices the spec into tracer bullets with blockers, stacked branch names, and parallel waves; publishes to GitHub, GitLab, Jira, or local files after approval. | `plan.md`, tracker items |
| [`implement`](./implement) | One slice with TDD, or the whole frontier with implementer agents in worktrees. Ends in verify. Never commits red. | commits on `<slug>/NN-<task>` |
| [`simplify`](./simplify) | Removes slop and needless complexity from the diff without changing behavior. Ends in verify. | edits |
| [`verify`](./verify) | Floor, typecheck, lint, format, lawbook, tests with coverage, poly-crap, in that order. Fix only what it names until exit 0. | `.verify/` |
| [`pr`](./pr) | Opens one PR per slice against its parent branch with real evidence. Never draft, never merge. | a PR |
| [`review`](./review) | Standards and spec axes in parallel read-only agents, plus CodeRabbit CLI when authenticated. | findings |
| [`explain-diff`](./explain-diff) | Writes a rich, interactive HTML explanation of a change, diff, branch, or PR. Outside the loop. | `.temp/<date>-explanation-<slug>.html` |

## Who may start a skill

Three skills say in their description that only the user may start them:
`setup`, `plan` (for publishing), and `pr`. The frontmatter stays within
the Agent Skills spec, so there is no `disable-model-invocation` key; the
description and the first step carry the rule. Every other skill fires on
its own when the request matches its description.

## How a skill page is organized

Each page follows the SKILL.md it documents:

- **What it does** and when it fires.
- **Reads**: the `factory.toml` keys and files the skill depends on.
- **Rules**: the hard constraints factory adds on top of the upstream
  method.
- **Done when**: the observable end state.
- **Upstream**: the vendored method files the skill loads and what its
  Translate section changes.
