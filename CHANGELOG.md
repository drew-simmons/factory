# Changelog

## Unreleased

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
