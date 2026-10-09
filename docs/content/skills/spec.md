---
title: spec
description: Align the user and the agent on one spec.md before any code.
---

## What it does

`/factory:spec` turns the conversation, an issue, or a request into one
`spec.md` that a planner can slice and an implementer can test against.
It fires when the user runs the skill, asks to write a spec, asks to turn
a conversation or issue into a spec, or asks to agree on requirements and
test seams for a feature or bugfix.

It writes a local file only. Nothing goes to a tracker; `/factory:plan`
publishes slices later.

## Reads

- `factory.toml` for `spec_dir` (default `docs/specs`) and `base`. If
  `.kiro/specs/` exists and `spec_dir` was not set, it uses that.
- The conversation, any linked issue (`gh issue view`,
  `glab issue view`, `acli jira workitem view`), nearby code, tests,
  glossary, and ADRs. Explore subagents gather anything that takes more
  than a few reads.

## Writes

`<spec_dir>/<slug>/spec.md` with these headings in this order: Problem,
Solution, Requirements, Testing decisions, Implementation decisions, Out
of scope, Assumptions, Open questions. Requirements are numbered with
stable ids in EARS form:

```text
- R1. WHEN <trigger> THEN the system SHALL <observable behavior>.
- R2. IF <state> THEN the system SHALL <observable behavior>.
```

The slug is short kebab-case. An existing spec directory is reused when
the request continues earlier work.

## Rules

- Facts come from the repository; decisions come from the user. Never
  ask the user for something the repo can answer.
- Seams are the highest public boundaries tests will run against.
  Existing seams before new ones; the ideal number is one.
- At most one grilling round, for decisions the repo cannot settle. Each
  question is numbered and carries a recommended answer. The round is
  skipped when nothing is open.
- Every decision the agent made without asking goes under Assumptions so
  the user can overturn any of them in one pass.
- Plain words, sentence-case headings, no em dashes.

## Done when

`spec.md` has numbered requirements, named seams, no open questions, and
`Status: agreed`. Planning and coding never start from a draft.

## Upstream

Wraps `mattpocock-skills/to-spec` for the synthesis-first process and
`mattpocock-skills/grilling` for design-tree rounds with a recommended
answer per question. Upstream publishes the spec to the tracker with a
triage label; factory keeps it local. Upstream's long numbered user
stories become requirements with stable ids.
