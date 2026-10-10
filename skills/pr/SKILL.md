---
name: pr
description: Open a pull request or merge request for the current slice branch, targeting its parent branch in the stack, with a body built from the verify evidence. Only run when the user explicitly invokes /factory:pr or asks to open a PR; never open one on your own initiative. Refuses on a red tree, never opens drafts, never merges.
license: MIT
compatibility: Requires git and an authenticated gh (GitHub) or glab (GitLab).
metadata:
  upstream: "cursor-plugins/pstack-playbooks, mattpocock-skills/pr"
allowed-tools: Bash(git:*) Bash(gh:*) Bash(glab:*) Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/plan/scripts/plan-check.py *) Read Write
---

# pr

Publish one green slice as one PR in a base-branch stack and hand it to the
reviewer, human or bot.

## Load

- `${CLAUDE_PLUGIN_ROOT}/upstream/cursor-plugins/pstack/skills/poteto-mode/playbooks/opening-a-pr.md`:
  commits, titles, descriptions, stacks, readiness.
- `${CLAUDE_PLUGIN_ROOT}/upstream/mattpocock-skills/skills/engineering/pr/SKILL.md`:
  the evidence and merge-danger sections and the summary visuals.
- `${CLAUDE_SKILL_DIR}/references/pr-body.md`: the merged body template.

## Translate

- Origin, Graphite, `origin pr`, the built-in PR tool, swarm, arena,
  interrogate, and `/no-comments` do not exist here. Use `gh` or `glab`
  only, and `/factory:simplify` in place of `/deslop`.
- `/technical-writing` and `/unslop` become the writing rules in this
  skill: plain words, short sentences, no em dashes.
- Babysitting the stack after the PRs are open is `/factory:steward`.

## Factory rules

- Shell discipline: one command per Bash call, with no `&&`, `;`, pipes,
  redirects, or `$(...)`. A tool grant matches the command word, so a
  compound command is denied whole, and one denied command is not a denied
  tool: retry with a single, simpler command. Read exit codes and output
  from the tool result. Create and edit files with the Write and Edit
  tools, never a shell heredoc.
- Confirm the user invoked this skill. If the model reached it on its own,
  stop and ask.
- Read `factory.toml` for `base`. Read `plan.md` for the slice's `Branch`,
  `Parent`, and tracker item.
- Refuse when the tree is red: `.verify/green` must exist and match the
  current change (rerun `/factory:verify` to be sure). Refuse when there
  are uncommitted changes; do not commit them.
- Target the parent branch: `gh pr create --base <parent>` or
  `glab mr create --target-branch <parent>`. The root slice targets `base`.
- Never `--draft`. Never merge. Never force-push. Never push `base`.
- Reuse an open PR for the same head branch; update its body instead of
  opening a second one.
- `--stack`: run steps 1 to 6 once per slice, bottom up, for every row of
  `python3 ${CLAUDE_PLUGIN_ROOT}/skills/plan/scripts/plan-check.py <plan.md>
  --stack` whose branch exists (`git switch <branch>` first). Each body
  carries a `## Stack` table, `NN | branch | parent | PR`, with the URLs
  known so far; after the last PR, update the earlier bodies so every
  table is complete. Stop at the first slice that refuses (red or dirty)
  and report which PRs were opened.

## Steps

1. Resolve the forge from `git remote -v` and check `gh auth status` or
   `glab auth status`. Stop on failure; do not run a login.
2. Rebase the slice branch onto the tip of its parent when the parent moved,
   then rerun `/factory:verify`.
3. Push: `git push -u origin <branch>`.
4. Write the body from `references/pr-body.md` to a temporary file. Take
   the Verification numbers from `.verify/summary.txt`. Mention the tracker
   item so the forge links it.
5. Create or update the PR with `--body-file`. Read it back with
   `gh pr view` or `glab mr view` and confirm base, head, title, and that
   it is not a draft.
6. If the repository has a CodeRabbit config (`.coderabbit.yaml`) or a
   GitHub app review will run, stop here and post the URL. Otherwise say no
   bot review is configured and suggest `/factory:review`.
7. Point at `/factory:steward` for driving the stack to merge-ready.

## Done when

The PR URL is posted, it targets the right parent, it is not a draft, and
the body carries real verify evidence. With `--stack`, one PR per existing
slice branch, each with the same stack table.
