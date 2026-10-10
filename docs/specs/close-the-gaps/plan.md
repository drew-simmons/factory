# Close the four gaps plan

Spec: ./spec.md
Base: origin/main
Tracker: local

## Slices

### 01 Make the gate honest and the plugin tested

- Requirements: R1, R2, R3, R4, R5
- Blocked by: none
- Branch: close-the-gaps/01-gate
- Parent: origin/main
- Delivers: a Stop hook that cannot be ended by trying twice, a verify
  script whose exit codes mean what the docs say, a floor that catches the
  moves that lower the bar, and a CI that would catch a regression in any
  of them.
- Acceptance:
  - [ ] `uv run pytest` passes with new tests for the hook and every new
        verify exit path, each written red first.
  - [ ] `sh skills/verify/scripts/verify.sh` exits 0 on this repository.
  - [ ] shellcheck, ruff, rumdl, lawbook, and the plugin validator are
        clean.
- Tracker: ./issues/01-gate.md

### 02 Close the loop

- Requirements: R6, R7, R8, R9, R10
- Blocked by: 01
- Branch: close-the-gaps/02-loop
- Parent: close-the-gaps/01-gate
- Delivers: a plan that is checked before it is presented, review findings
  that reach implement through a file, worktrees that are released by a
  script, a simplify that commits, one PR invocation for a stack, and a
  simulation harness that fails loudly.
- Acceptance:
  - [ ] `plan-check.py` rejects the diamond from the 2026-10-09 report and
        accepts this plan.
  - [ ] `release-worktree.sh` is tested on a real worktree.
  - [ ] every simulation run script passes shellcheck and exits non-zero
        on a failed check.
- Tracker: ./issues/02-loop.md

### 03 Orchestrate and steward

- Requirements: R11, R12, R13
- Blocked by: 02
- Branch: close-the-gaps/03-orchestrate
- Parent: close-the-gaps/02-loop
- Delivers: `/factory:run` to sequence a size's stages and resume from
  disk, `/factory:steward` to drive a stack to merge-ready, and an evals
  workflow that runs when a key is present.
- Acceptance:
  - [ ] `stack-status.sh` is tested against a stub `gh`.
  - [ ] both new skills pass the plugin validator and the lawbook rules.
  - [ ] the evals workflow skips cleanly without a key.
- Tracker: ./issues/03-orchestrate.md

## Waves

Slices in the same wave share no blockers and no write set, so they can run
in parallel worktrees. `Parent` for a slice in a later wave is the branch of
the slice it is blocked by.

```json
{
  "waves": [
    { "id": 0, "slices": ["01"] },
    { "id": 1, "slices": ["02"] },
    { "id": 2, "slices": ["03"] }
  ]
}
```

## Notes

The slices are serial on purpose: each tier's tests are what the next tier
is verified with. Validation per slice is the command list in the spec's
testing decisions.
