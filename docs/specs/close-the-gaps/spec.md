# Close the four gaps

Status: agreed
Base: origin/main

## Problem

The plugin promises that a human agrees a spec and a plan, walks away, and
comes back to a verified stack of PRs. An analysis of v0.4.0 found four gaps
between that promise and the code. The loop is not chained, so a human still
sequences the stages and carries review findings back by hand. The gate
script has correctness holes that let a red change end a turn or measure
the wrong diff. The plugin itself is thinly tested, so those holes were not
caught. And the docs, config, and manifests have drifted apart.

## Solution

The gate is honest and tested, the deterministic parts of the loop are
scripts with tests instead of prose, one skill sequences the stages and
resumes from disk, and the stack is stewarded after the PRs open. The user
sees the same four gates as before: spec answers, plan approval, starting
the PRs, and merging.

## Requirements

- R1. WHEN a verify loop is armed and the tree is red THEN the Stop hook
  SHALL block the turn on every stop until `max_iterations`, with or
  without `jq`, on the repository named by the payload's working directory.
- R2. WHEN the base ref, a slice's Parent, a stage command, or
  `factory.toml` cannot be resolved or read THEN `verify.sh` SHALL exit 2
  and name the missing thing, never fall back to `main` or report a failed
  gate.
- R3. WHEN a change raises the CRAP threshold, demotes or deletes an
  error-level lawbook rule, or removes test definitions THEN the floor
  SHALL fail; WHEN it lowers the threshold THEN the floor SHALL pass.
- R4. WHEN tests changed THEN poly-crap SHALL gate only the functions the
  change touched and list the rest as advisory.
- R5. WHEN CI runs THEN it SHALL run shellcheck, the verify script on this
  repository, and both manifest validations with pinned tool versions.
- R6. WHEN a plan has a slice blocked by two independent chains, a slice in
  no wave or two, or a Parent that is not a slice branch THEN `plan-check`
  SHALL exit 1 and name the slice, and the plan skill SHALL not present
  the breakdown until it exits 0.
- R7. WHEN `/factory:review` finishes THEN it SHALL write
  `<spec_dir>/<slug>/review-NN.md` with checkbox findings per axis, and
  `/factory:implement NN --from-review` SHALL fix the unchecked P0 to P2
  items and tick them.
- R8. WHEN an implementer agent reports done THEN the parent SHALL release
  its worktree with `release-worktree.sh`, which copies the verify evidence
  out first; WHEN simplify leaves a green non-empty diff THEN it SHALL
  commit it.
- R9. WHEN `/factory:pr --stack` runs THEN it SHALL open or update one PR
  per existing slice branch, bottom up, each against its Parent.
- R10. WHEN a simulation stage errors, is denied a tool, or runs out of
  budget THEN the run SHALL record a failed check and exit non-zero.
- R11. WHEN `/factory:run <size>` is invoked THEN it SHALL drive the stages
  for that size, stop only at the human gates, and resume from
  `<spec_dir>/<slug>/run.md` in a later session.
- R12. WHEN `/factory:steward` runs on a stack THEN it SHALL work the lowest
  unmerged PR through conflicts, review threads, and CI, restack a slice
  whose parent merged, and never merge.
- R13. WHEN the evals workflow runs with an API key THEN it SHALL run every
  eval case and upload the results.

## Testing decisions

- Seams: the shell scripts and Python scripts by their exit code and
  output, run on temporary git repositories (prior art:
  `tests/test_verify_sh.py`); the Stop hook through its stdin payload with
  a stub verify; `plan-check` and `stack-status` through canned inputs.
- Skill prose is tested by evals and simulations, which spend model budget
  and run outside CI.

## Implementation decisions

Three slices, one per tier, stacked. Rules that failed in simulation move
from prose into scripts the skills call. Each setting keeps one source of
truth. Skills stay under 150 lines and cite their upstream method files.

## Out of scope

Changing the vendored upstream files. A merge step. A personal access token
for the release job.

## Assumptions

- lawbook rule levels are `error` and `warn`; a demotion is `error` to
  `warn`.
- A force push with lease on a slice branch that factory created is the one
  sanctioned rewrite, used only to restack after a parent merges.
- Simulations and evals are run by the owner after merge, not in this
  change.

## Open questions

None.
