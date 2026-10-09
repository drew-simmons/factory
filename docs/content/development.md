---
title: Development
description: Tests, validation, evals, and how to run this documentation site.
sidebar:
  order: 8
---

## Tests

The maintenance tooling (the upstream sync script and the verify script)
is tested with pytest:

```bash
uv run pytest
```

## Validation

Every skill directory must satisfy the Agent Skills spec and Claude
Code's plugin validator:

```bash
claude plugin validate skills --strict
```

The lawbook rules in `lawbook.yaml` enforce the repository's own
conventions: every loop skill loads an upstream file, `SKILL.md` stays
under 150 lines, only the portable frontmatter keys are used, and owned
prose uses plain punctuation.

```bash
lawbook check . --no-llm
```

## Evals

```bash
claude plugin eval . --threshold 0.8
```

The eval cases under `evals/` check that `spec` fires on a feature
request, that `pr` does not fire on its own, and that the verify script
runs on a fixture repository. The last one needs `--scaffold` and Bash
grants; see the comment at the top of its `scaffold.sh`.

## This site

The documentation is a [Blume](https://useblume.dev) site under `docs/`,
with pages in `docs/content/`. It lives in a subdirectory on purpose: a
`package.json` at the repository root would make the verify script treat
the repository as a Node stack.

```bash
pnpm -C docs install
```

```bash
pnpm -C docs dev
```

```bash
pnpm -C docs validate
```

```bash
pnpm -C docs build
```

`validate` checks internal links and fails on warnings. `build` writes
`docs/dist/`. A GitHub Actions workflow runs both on every pull request
that touches `docs/` and deploys to GitHub Pages on push to `main`.

Pages are plain Markdown so `rumdl` can lint them with the rest of the
repository:

```bash
uvx rumdl check --fix docs/content
```

`factory.toml` points specs at `docs/specs/`, a sibling of `content/`
outside the site's content root, so specs never become pages.
