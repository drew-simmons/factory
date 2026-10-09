---
name: setup
description: Configure a repository for the factory skills by writing factory.toml (spec directory, base branch, issue tracker, verify commands). Only run when the user explicitly invokes /factory:setup or asks to set up factory in this repo. Detects the stack and remote host first and asks only what it cannot detect.
license: MIT
compatibility: Requires git. Uses gh, glab, or acli when the tracker needs one.
metadata:
  upstream: "mattpocock-skills/setup"
allowed-tools: Bash(git:*) Bash(gh auth status) Bash(glab auth status) Bash(acli:*) Read Write
---

# setup

Write `factory.toml` once per repository so the other factory skills do not
ask the same questions on every run.

## Load

- `${CLAUDE_SKILL_DIR}/references/factory-toml.md`: the schema, stack
  defaults, and tracker kinds.
- `${CLAUDE_PLUGIN_ROOT}/upstream/mattpocock-skills/skills/engineering/setup-matt-pocock-skills/SKILL.md`:
  the explore-then-confirm pattern. Read its `issue-tracker-*.md` siblings only
  when the chosen tracker needs them.

## Translate

- Upstream writes `docs/agents/*.md` and a CLAUDE.md block. Factory writes
  `factory.toml` only. Do not create `docs/agents/` or edit CLAUDE.md.
- Upstream's triage labels and domain docs sections do not apply. Skip them.
- "Local markdown under `.scratch/`" becomes `<spec_dir>/<slug>/issues/`.

## Steps

1. Confirm the user invoked this skill. If the model reached it on its own,
   stop and ask before writing anything.
2. Detect, never ask, for anything in this list:
   - stack marker files (`pnpm-lock.yaml`, `package.json`, `pyproject.toml`,
     `uv.lock`, `Cargo.toml`, `go.mod`);
   - remote host from `git remote -v` (github.com, gitlab.com, self-hosted);
   - default branch from `git symbolic-ref refs/remotes/origin/HEAD`;
   - `lawbook.yaml`, an existing coverage file, `tsconfig.json`;
   - an existing `factory.toml` (update it in place; keep user edits).
3. Report the detected values in a few lines. Then ask, one question at a
   time, only for what detection left open:
   - tracker kind when the remote is ambiguous or the user may prefer local
     files or Jira;
   - Jira site, project key, and work item type when kind is `jira`;
   - a test command when no stack marker matched.
   Recommend an answer with every question.
4. Check the tracker tool is usable: `gh auth status`, `glab auth status`, or
   `acli jira auth status`. Report a failure; do not run a login.
5. Show the draft `factory.toml`. Write it after the user accepts. Omit keys
   that equal the defaults so the file stays short.
6. Add `.verify/`, `.factory/`, and `.claude/worktrees/` (where implementer
   agents work) to `.gitignore` if they are not already ignored.
7. Commit `factory.toml` and `.gitignore` when either changed, as
   `chore: configure factory`, and nothing else. Setup is the one skill
   that commits configuration; later skills refuse an uncommitted tree.

## Done when

`factory.toml` exists, every key in it was either detected or chosen by the
user, its changes are committed, and the reply lists the verify commands
the stack default will run.
