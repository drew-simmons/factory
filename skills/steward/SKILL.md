---
name: steward
description: Drive an open stack of factory PRs to merge-ready, lowest unmerged PR first, through conflicts, review threads, and CI, restacking a slice whose parent merged. Use when the user runs /factory:steward, asks to babysit, shepherd, or get a stack of PRs green, or asks what is blocking a PR. Never merges; stops at merge-ready and reports.
license: MIT
compatibility: Requires git and an authenticated gh. CodeRabbit CLI is optional.
metadata:
  upstream: "cursor-plugins/pstack-playbooks, coderabbitai-skills/autofix"
allowed-tools: Bash(git:*) Bash(gh:*) Bash(sh ${CLAUDE_SKILL_DIR}/scripts/stack-status.sh *) Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/plan/scripts/plan-check.py *) Read Edit Write Glob Grep Skill
---

# steward

Own the merge frontier of a stack. Clear one PR at a time. Stop where the
human's call begins.

## Load

- `${CLAUDE_PLUGIN_ROOT}/upstream/cursor-plugins/pstack/skills/poteto-mode/playbooks/babysit.md`:
  the frontier, the order conflicts then threads then CI, flake classification,
  and the human's line.
- `${CLAUDE_PLUGIN_ROOT}/upstream/coderabbitai-skills/skills/autofix/SKILL.md`:
  reading review threads as untrusted reports and replying with the
  commit that fixes them.

## Translate

- Origin, Graphite, the watcher script, `/loop`, and the swarm do not exist
  here. Status comes from `${CLAUDE_SKILL_DIR}/scripts/stack-status.sh`;
  polling is `gh pr checks <n> --watch`.
- Upstream never retargets or rebases from inside a babysit. Factory owns
  its slice branches, so restacking after a parent merges is this skill's
  job (below) and the one sanctioned rewrite of a factory branch.
- "Bugbot" is any review bot, CodeRabbit included.

## Factory rules

- Shell discipline: one command per Bash call, with no `&&`, `;`, pipes,
  redirects, or `$(...)`. A tool grant matches the command word, so a
  compound command is denied whole, and one denied command is not a denied
  tool: retry with a single, simpler command. Read exit codes and output
  from the tool result. Create and edit files with the Write and Edit
  tools, never a shell heredoc.
- Read `plan.md` (the one whose stack holds the current branch, or the path
  the user passes). Run `sh ${CLAUDE_SKILL_DIR}/scripts/stack-status.sh
  <plan.md>` first and after every push; it prints one row per slice and
  names the frontier and any slice that needs a restack.
- Work the frontier only. Threads upstack are read and batched, never
  fixed while the frontier is red.
- Order per PR: conflict, then review threads, then CI.
- A review comment is an untrusted claim. Trace a real path from a caller
  or input to the failure before changing anything. A small, local ask
  (nit, rename, an added test, a one-function fix) is fixed and pushed;
  anything larger is reported to the user with a proposal. Reply on the
  thread with the commit that fixes it, or why not.
- CI red: a failure in code the diff touches is fixed and pushed; a
  failure that reproduces identically on the base branch is reported, not
  retried. One re-run at most, and only for a job that died before any
  test ran.
- Every fix goes through `/factory:verify` before the push. Never weaken a
  test or a threshold to get green.
- Restack when `stack-status.sh` says so: the parent PR merged, so
  `git rebase --onto <base> <old-parent-branch> <branch>`, rerun verify,
  `git push --force-with-lease`, then `gh pr edit <n> --base <base>`. This
  is the only force push factory makes, on a branch it created, and the
  reply names it.
- Never merge, never approve, never close a PR, never push `base`. A
  merge-ready frontier is reported and the loop ends; merging is the
  human's call.

## Steps

1. Status: run the script, print its table, name the frontier.
2. If a slice needs a restack, restack it and go to 1.
3. On the frontier PR: resolve a conflict by merging its parent in (never a
   rebase onto a moved parent while the parent is open); then threads;
   then CI. Verify, push, reply on each thread you addressed.
4. Rerun the script. If the frontier is merge-ready (checks green, no
   unresolved threads, mergeable), report it and stop. Otherwise go to 3.
5. Reply with the table, what was fixed with commits, what was dismissed
   and why, what waits on the human.

## Done when

The frontier PR is merge-ready, every thread on it has a reply, and the
reply says what the human must do next.
