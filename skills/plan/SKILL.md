---
name: plan
description: Break an agreed spec.md into vertical slices with blocking edges, stacked branch names, and parallel waves, written to plan.md and published to the configured tracker. Use when the user runs /factory:plan, asks to plan a spec, create tickets or issues from a spec, or split work into slices for worktrees and stacked PRs. Publishing to a remote tracker happens only after the user approves the breakdown.
license: MIT
compatibility: Requires git. Publishing needs gh, glab, or acli depending on factory.toml.
metadata:
  upstream: "mattpocock-skills/to-tickets, addyosmani-agent-skills/planning, cursor-plugins/pstack-playbooks"
allowed-tools: Bash(git:*) Bash(gh:*) Bash(glab:*) Bash(acli:*) Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/plan-check.py *) Read Write Glob Grep
---

# plan

Turn `spec.md` into slices an implementer can take one at a time, in
parallel worktrees, each landing as one PR in a stack.

## Load

- `${CLAUDE_PLUGIN_ROOT}/upstream/mattpocock-skills/skills/engineering/to-tickets/SKILL.md`:
  tracer-bullet slices, blocking edges, expand-contract for wide refactors, the
  frontier, and the quiz-the-user step.
- `${CLAUDE_PLUGIN_ROOT}/upstream/addyosmani-agent-skills/skills/planning-and-task-breakdown/SKILL.md`:
  dependency graph and acceptance criteria per task. Skim; do not write its
  `tasks/plan.md` or `tasks/todo.md`.
- `${CLAUDE_PLUGIN_ROOT}/upstream/cursor-plugins/pstack/skills/poteto-mode/playbooks/multi-phase-plan.md`:
  one PR per section with its own evidence. Take the idea, not the swarm-lane
  template.
- `${CLAUDE_SKILL_DIR}/references/plan-template.md` and
  `${CLAUDE_SKILL_DIR}/references/trackers.md`.

## Translate

- Upstream's `.scratch/<feature>/issues/` becomes `<spec_dir>/<slug>/issues/`.
- "Run /setup-matt-pocock-skills" becomes "run /factory:setup".
- Cursor `Task` and `poteto-agent` become the Agent tool with the Explore
  type. `AskQuestion` becomes AskUserQuestion.
- The `ready-for-agent` label becomes the `factory` label, or none for local.

## Factory rules

- Read `factory.toml` for `spec_dir`, `base`, and `[tracker]`. Without a
  tracker kind, default to `local` and say so.
- Refuse to plan from a spec whose `Status` is not `agreed`; point at
  `/factory:spec`.
- Every slice names its `Branch` and `Parent`. The stack is a base-branch
  chain: the root slice's parent is `base`, each later slice's parent is
  the branch of the slice it is blocked by.
- Slices in one wave must have disjoint write sets. When two slices touch
  the same files, put them in different waves and make one block the other.
- Every blocker of a slice must be an ancestor of its `Parent`. A slice
  that needs two independent chains cannot be stacked on both; serialize
  the chains (make the head of one block the root of the other) rather
  than let an implementer copy commits across branches.
  `${CLAUDE_SKILL_DIR}/scripts/plan-check.py <plan.md>` checks these
  rules and the waves; it must exit 0 before the breakdown is shown.
- After publishing, slice status lives in the tracker (or the issue
  files), not in `plan.md`. `plan.md` is not edited to track progress, so
  the copy in every slice commit stays identical.

## Steps

1. Read `spec.md` and the code around the seams it names. Look for
   prefactoring that makes the slices smaller; schedule it as slice `01`.
2. Draft the slices with ids, requirement ids, blockers, branch, parent,
   delivers, and acceptance checks. Then compute waves. Write the draft
   to `plan.md` and run `python3 ${CLAUDE_SKILL_DIR}/scripts/plan-check.py
   <plan.md>`; fix every finding it names until it exits 0.
3. Present the breakdown as a numbered list and ask the three upstream
   questions: granularity, blocking edges, merge or split. Iterate until
   the user approves. Do not publish before approval.
4. Update `plan.md` with what the user changed and rerun `plan-check.py`.
5. Publish per `tracker.kind` using `references/trackers.md`. For `local`,
   write one issue file per slice. For remote trackers, create the tracking
   item first, then each slice, blockers before dependents, and fill the
   `Tracker:` lines in `plan.md`.
6. Reply with the plan path, the wave table, and the first frontier: the
   slices with no blockers, ready for `/factory:implement`. Do not commit;
   the first slice commits `<spec_dir>/<slug>/` with its code.

## Done when

`plan.md` exists with every slice traced to requirement ids, a valid
`waves` block, a `Tracker:` line per slice, and `plan-check.py` exits 0.
