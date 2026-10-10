# Changelog

## Unreleased

## 0.7.0 (2026-10-10)

- `verify` stage 7 passes `--changed-lines` when the installed lawbook has
  it (0.4 and later), so a standard finding on a line the change did not
  touch no longer fails the run or sends the implementer after it; the
  summary counts the findings dropped as outside the change.

## 0.6.0 (2026-10-10)

- Every skill and both agents carry a shell discipline rule: one command
  per Bash call, no chains, pipes, redirects, or substitution, files
  through Write and Edit; a denied command is retried, not treated as a
  denied tool. `implement --all` names `run_in_background: false` and the
  loop resumes from disk when an agent is orphaned anyway; the plan skill
  names the behavioural dependency `plan-check` cannot see; `run.md` fields
  take the template's values literally.
- Simulations run without GitHub with `SIM_FORGE=0` (local bare origin,
  local tracker, forge checks skipped), resume a run or an `implement
  --all` that ended its turn mid-slice, and tolerate a slice the
  implementer kept red. Report for the four 2026-10-10 batches.

## 0.5.0 (2026-10-10)

- `/factory:run <size>` drives every stage a small, medium, or large change
  needs, stops only at the human gates, and resumes from
  `<spec_dir>/<slug>/run.md` in a later session.
- `/factory:steward` replaces `pr --babysit`: it works the lowest unmerged
  PR of a stack through conflicts, review threads, and CI, restacks a
  slice whose parent merged, and never merges. `stack-status.sh` reads
  the stack from the forge and names the frontier.
- Evals: the verify case grants the tools it needs and checks the exit
  code; new cases for `plan` (plan-check accepts the result, no publish
  before approval) and `review` (the handoff file with the planted
  finding); an `evals` workflow runs the suite weekly when an
  `ANTHROPIC_API_KEY` secret exists.
- `plan-check.py` in the plan skill reads `plan.md` and fails on a slice
  blocked by two independent chains, a Parent that is not the base or a
  slice branch, a parent slice missing from `Blocked by`, or waves that
  disagree with the blockers. The plan skill runs it before presenting the
  breakdown; verify runs it as stage 0b when a plan changed. `--stack`
  lists the slices for the skills that walk the stack.
- `/factory:review` writes `<spec_dir>/<slug>/review-NN.md` with one
  checkbox per finding, and `/factory:implement <NN> --from-review` fixes
  the unchecked P0 to P2 items and commits with the file.
- `release-worktree.sh` in the implement skill copies an implementer
  agent's verify evidence to `.verify/slices/NN/` before removing its
  worktree; `/factory:simplify` commits its own change; `/factory:pr
  --stack` opens one PR per slice branch, bottom up, with a stack table.
- Simulations: a timeout per session, an isolated Claude config directory,
  three free checks per stage (no error, no denial, finished on its own),
  issue and PR baselines, one throwaway repository per run, review checks
  on the handoff file, a non-zero exit on any failed check, and
  `report.sh` to print a run's tables as markdown. The verify tests cover
  the node stack, a missing coverage file, and the lawbook stage.
- The Stop hook gates every stop until `max_iterations`, not one forced
  continuation; it blocks without `jq`; it reads the repository from the
  payload cwd and also runs on SubagentStop, so implementer agents in
  worktrees are gated on their worktree.
- `verify.sh` exits 2 on a base ref or slice Parent that does not resolve,
  on a stage command that is not installed, and on a `factory.toml` it
  cannot read, instead of falling back to `main` or reporting a failed
  gate. The green stamp covers the settings that decide the verdict. The
  root is the work tree around the current directory.
- poly-crap gates the changed functions only and receives
  `[verify].exclude`; after a test change the full scan is advisory. The
  floor compares CRAP thresholds numerically, catches an error-level
  lawbook rule demoted or deleted, and counts test definitions removed
  inside a kept file.
- CI pins tool versions, runs shellcheck and the verify script on this
  repository, validates both manifests, and reads the CRAP threshold from
  `factory.toml`. The upstream sync PR updates only entries that are
  behind and lists new tags for a hand update. Tests cover both hooks and
  keep the docs in step with the setup reference.

## 0.4.0 (2026-10-09)

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
