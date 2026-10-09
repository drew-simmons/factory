# Changelog

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
