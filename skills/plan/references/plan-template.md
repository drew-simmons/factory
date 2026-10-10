# plan.md template

Write `<spec_dir>/<slug>/plan.md` with these headings. Each slice is a
tracer bullet: one narrow path through every layer, demoable on its own,
sized for one fresh context window.

````markdown
# <Feature name> plan

Spec: ./spec.md
Base: origin/main
Tracker: local | github | gitlab | jira

## Slices

### 01 <imperative title>

- Requirements: R1, R2
- Blocked by: none
- Branch: <slug>/01-<task>
- Parent: origin/main
- Delivers: the end-to-end behavior this slice makes work, from the user's
  point of view.
- Acceptance:
  - [ ] <observable check>
  - [ ] <observable check>
- Tracker: <issue url or file path, filled in after publishing>

### 02 <imperative title>

- Requirements: R3
- Blocked by: 01
- Branch: <slug>/02-<task>
- Parent: <slug>/01-<task>
- Delivers: ...
- Acceptance:
  - [ ] ...
- Tracker: ...

## Waves

Slices in the same wave share no blockers and no write set, so they can run
in parallel worktrees. `Parent` for a slice in a later wave is the branch of
the slice it is blocked by; a slice with several blockers lists the last
one to merge as parent.

```json
{
  "waves": [
    { "id": 0, "slices": ["01"] },
    { "id": 1, "slices": ["02", "03"] }
  ]
}
```

## Notes

Prefactoring done first, expand-contract sequences for wide refactors,
validation commands, and anything an implementer needs that the spec does
not say.
````

Rules:

- Number slices from `01` in dependency order, blockers first.
- `Branch` is `<slug>/NN-<task>`. `Parent` is the branch the slice stacks on.
  The root slice's parent is `base`.
- Keep acceptance checks observable: a test name, a command and its output,
  a screen state.
- No file paths or code in slices; they go stale. A prototype snippet that
  encodes a decision is the one exception.
- `scripts/plan-check.py <plan.md>` reads exactly these headings and
  fields. It fails on a slice blocked by two independent chains, a `Parent`
  that is not `base` or another slice's `Branch`, a parent slice missing
  from `Blocked by`, a slice in no wave or two, and a wave that holds a
  slice with its blocker. `--stack` prints `NN branch parent` per slice.
