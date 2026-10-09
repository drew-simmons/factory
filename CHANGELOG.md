# Changelog

## Unreleased

- `simulations/`: three end-to-end runs (small bug, medium feature as a
  stack, large feature with parallel waves) that drive every skill through
  headless sessions against fixtures whose `lawbook.yaml` extends the
  clean-code example, with a report per batch.
- `verify.sh` finds standard rules through `extends`, reads the model
  request cap from `[verify].max_requests`, keeps the stack globs literal
  at the repository root, writes the Stop hook state file itself with
  `--loop`, fails on a `fail`-level model-judged standard (warn-level
  findings stay advisory), and measures a planned slice against its
  `Parent` from `plan.md` instead of the whole stack.
- The slice commit carries `<spec_dir>/<slug>/`; the tracker notes create
  the `factory` label before the first issue.

## 0.3.0 (2026-10-09)

- Docs site built with Blume under `docs/`, deployed to GitHub Pages,
  with a guide on when to reach for factory that sizes a change as
  small, medium, or large, and one page per skill.

## 0.2.0 (2026-10-09)

- `explain-diff` skill: a rich, interactive HTML explanation of a change,
  diff, branch, or PR, with background, intuition, code walkthrough, and a
  five-question quiz.
- Tagged releases: after each merge to `main` that carries a `feat` or `fix`
  commit, CI bumps the version in the plugin manifests, `pyproject.toml`, and
  `uv.lock`, tags `vX.Y.Z`, and publishes a GitHub release with the changelog
  section as the notes (`scripts/release.py`).

## 0.1.0 (2026-10-08)

First release.

- Eight skills: `setup`, `spec`, `plan`, `implement`, `simplify`, `verify`,
  `pr`, `review`, each a portable SKILL.md wrapper over vendored upstream
  method files.
- Two agents: `implementer` (one slice per worktree) and `reviewer`
  (read-only, one axis per run).
- `verify.sh` with stack detection for node, python, rust, and go, a floor
  stage that rejects a lowered bar, and poly-crap and lawbook gates.
- Opt-in Stop hook that keeps a red change from ending the turn while a
  loop is armed.
- `scripts/sync-upstream.py` with a content-hashed manifest, `check`,
  `diff`, `update`, `verify`, and `notices` commands, and a weekly workflow
  that opens a PR when upstream moves.
