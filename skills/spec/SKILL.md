---
name: spec
description: Align the user and the agent on one spec.md before any code. Use when the user runs /factory:spec, asks to write a spec, turn a conversation or issue into a spec, or agree on requirements and test seams for a feature or bugfix. Writes <spec_dir>/<slug>/spec.md and does not publish to a tracker.
license: MIT
compatibility: Requires git and read access to the repository.
metadata:
  upstream: "mattpocock-skills/to-spec, mattpocock-skills/grilling"
allowed-tools: Bash(git:*) Read Write Glob Grep
---

# spec

Turn the conversation, an issue, or a request into one `spec.md` that a
planner can slice and an implementer can test against.

## Load

- `${CLAUDE_PLUGIN_ROOT}/upstream/mattpocock-skills/skills/engineering/to-spec/SKILL.md`:
  the synthesis-first process and the section intent.
- `${CLAUDE_PLUGIN_ROOT}/upstream/mattpocock-skills/skills/productivity/grilling/SKILL.md`:
  design-tree rounds with a recommended answer per question.
- `${CLAUDE_SKILL_DIR}/references/spec-template.md`: the exact headings.

## Translate

- Upstream publishes the spec to the issue tracker with a triage label.
  Factory writes a local file only; `/factory:plan` publishes slices later.
- Upstream's "run /setup-matt-pocock-skills" becomes "run /factory:setup".
- Upstream's long numbered user stories become numbered requirements with
  stable ids (`R1`, `R2`) in the EARS form shown in the template.
- Facts come from Explore subagents (the Agent tool); decisions come from
  the user. Never ask the user for something the repo can answer.

## Factory rules

- Shell discipline: one command per Bash call, with no `&&`, `;`, pipes,
  redirects, or `$(...)`. A tool grant matches the command word, so a
  compound command is denied whole, and one denied command is not a denied
  tool: retry with a single, simpler command. Read exit codes and output
  from the tool result. Create and edit files with the Write and Edit
  tools, never a shell heredoc.
- Read `factory.toml` for `spec_dir` (default `docs/specs`) and `base`.
  If `.kiro/specs/` exists and the user did not set `spec_dir`, use it.
- Pick a short kebab-case slug. Reuse an existing spec directory when the
  request continues earlier work.
- Write prose in plain words, sentence-case headings, no em dashes.

## Steps

1. Gather evidence: the conversation, any linked issue (`gh issue view`,
   `glab issue view`, `acli jira workitem view`), nearby code, tests,
   glossary, and ADRs. Spawn Explore agents for anything that takes more
   than a few reads.
2. Draft the seams: the highest public boundaries tests will run against.
   Prefer existing seams; the ideal number is one.
3. Run at most one grilling round for decisions the repo cannot settle.
   Number each question, give a recommended answer, and wait. Skip the
   round when nothing is open.
4. Write `spec.md` from the template. Put every decision the agent made
   without asking under Assumptions. Set `Status: draft`.
5. Reply with the path, the seams, and the open questions list, so the user
   can answer everything in one message. When the user answers, update the
   file, clear the questions, and set `Status: agreed`.

## Done when

`spec.md` has numbered requirements, named seams, no open questions, and
`Status: agreed`. Do not start planning or coding from a draft spec.
