---
name: run
description: Drive the whole factory loop for one change at a chosen size (small, medium, large), stopping only at the human gates, and resume from disk in a later session. Only run when the user explicitly invokes /factory:run; it reaches /factory:pr, which the user must start. Writes <spec_dir>/<slug>/run.md and calls the other factory skills in order.
license: MIT
compatibility: Requires git and everything the skills it calls require. Large runs need git worktree support.
metadata:
  upstream: "mattpocock-skills/implement-spec, cursor-plugins/pstack-playbooks"
allowed-tools: Bash(git:*) Read Write Glob Skill
---

# run

Sequence the stages a change of a given size needs, keep the position on
disk, and hand control back only where a human decides. Every stage is an
existing factory skill called through the Skill tool; this skill adds no
method of its own.

## Load

- `${CLAUDE_PLUGIN_ROOT}/upstream/mattpocock-skills/skills/engineering/implement-spec/SKILL.md`:
  the frontier and the sparse, pointer-based handoff between stages.
- `${CLAUDE_PLUGIN_ROOT}/upstream/cursor-plugins/pstack/skills/poteto-mode/playbooks/multi-phase-plan.md`:
  one PR per unit with its own evidence; the plan as a checklist the operator
  audits from evidence. Take the idea, not the swarm lanes.
- `${CLAUDE_SKILL_DIR}/references/run-template.md`: the state file.
- `${CLAUDE_PLUGIN_ROOT}/docs/content/when-to-use.md`: the three sizes.

## Translate

- Upstream's integration branch and merger subagent become the stack
  `/factory:implement --all` builds and `/factory:pr --stack` publishes.
- Upstream's "fix all review issues in one implementer" becomes
  `/factory:implement <NN> --from-review` per slice.
- The operator's "explicit go" is each human gate below.

## Factory rules

- Shell discipline: one command per Bash call, with no `&&`, `;`, pipes,
  redirects, or `$(...)`. A tool grant matches the command word, so a
  compound command is denied whole, and one denied command is not a denied
  tool: retry with a single, simpler command. Read exit codes and output
  from the tool result. Create and edit files with the Write and Edit
  tools, never a shell heredoc.
- Confirm the user invoked this skill. If the model reached it on its own,
  stop and ask.
- `/factory:run <size> <request or spec path>` starts a run;
  `/factory:run` with no arguments resumes the run whose `run.md` has
  `Stage` other than `done`. Refuse to start a second run while one is
  open; name it.
- Write `run.md` before and after every stage, with a log line. Nothing
  about the position lives in the conversation.
- At a human gate, write `Waiting on`, ask with AskUserQuestion, and end
  the turn. The answer is applied by the stage that asked (spec, plan),
  not by this skill.
- Never skip a stage of the size, never call a stage out of order, never
  merge. A stage is finished when its skill has returned; never end the
  turn while an implementer agent is still running.

## Stages per size

| Size | Stages, in order | Human gates |
|---|---|---|
| small | verify | none; the change is already on a branch |
| medium | spec, plan, implement 01, simplify, review, implement 01 --from-review, pr, review | spec answers; plan approval; start the PR |
| large | spec, plan, implement --all, then per slice bottom up: simplify, review, implement NN --from-review; then pr --stack, review per PR | spec answers; plan approval; start the PRs |

`review` after `pr` reports only; its findings wait for the human, who can
answer with `/factory:implement NN --from-review` or `/factory:steward`.

## Steps

1. Starting: read `factory.toml` for `spec_dir`. Pick the slug the spec
   skill will use (or take it from the spec path). Write `run.md` with
   `Size`, `Stage: spec` (or `verify` for small), `Waiting on: none`.
2. Resuming: read `run.md`. If `Waiting on` is not `none`, confirm the
   gate is satisfied (`Status: agreed` in `spec.md`; the user's approval
   message for the plan; the user's go for the PR). If it is not, ask again
   and end the turn.
3. Run the current stage through the Skill tool with the arguments the
   table implies. Read its result from disk, never from memory: `spec.md`
   status, `plan.md` and `plan-check --stack`, `.verify/green`, the
   `review-NN.md` boxes, the PR URLs.
4. Append one log line, set `Stage` to the next stage (or `done`), and
   write `run.md`. Go to step 2.
5. On `done`, reply with the spec path, the slices and their PRs, the
   review findings left unchecked, and `.verify/slices/` evidence paths.

## Done when

`run.md` says `Stage: done`, every stage of the size has a log line with
evidence, and every PR of the stack is open against its parent.
