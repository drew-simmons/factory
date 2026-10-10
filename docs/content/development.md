---
title: Development
description: Tests, validation, evals, and how to run this documentation site.
sidebar:
  order: 8
---

## Tests

The scripts are tested with pytest: the verify script end to end on a
fixture repository, the Stop and SessionStart hooks against a stub verify,
`factory-config.py`, `release.py`, and `sync-upstream.py`. Shell is
covered by test count rather than by line coverage, so a new branch in a
shell script wants a new test.

```bash
uv run pytest
```

CI also runs the verify script itself on this repository, with the same
`factory.toml` a user would have, and shellcheck over every shell script.
Tool versions are pinned at the top of `.github/workflows/ci.yml`.

## Two manifests

`.claude-plugin/plugin.json` is the Claude Code manifest. `plugin.json` at
the root follows the agent-plugins.org schema so other agent hosts can
read the same plugin. A test keeps their shared fields identical and the
release job bumps both versions.

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
request, that `pr` does not fire on its own, that the verify script runs
on a fixture repository and exits 0, that `plan` writes a plan
`plan-check.py` accepts and asks before publishing, and that `review`
writes its handoff file with the finding the fixture plants. The
scaffolded cases need `--scaffold` and Bash grants; see the comment at the
top of each `scaffold.sh`.

The `evals` workflow runs the suite weekly and on demand when the
repository has an `ANTHROPIC_API_KEY` secret, and uploads
`evals/results/` as an artifact. Without the secret it skips and says
so.

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

## Releases

Merging to `main` cuts a release when the commits since the last tag carry
a `feat` or `fix`; the README has the version rules. The release commit is
pushed with the workflow's `GITHUB_TOKEN`, which starts no other workflow,
so it gets no CI run of its own and does not redeploy this site. Run the
`docs` workflow by hand from the Actions tab after a release that touched
`docs/`. A personal access token in the release job would close that gap;
that is the owner's call.
