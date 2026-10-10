---
name: implement
description: Implement one planned slice with test-driven development, or walk the whole plan frontier with implementer agents in git worktrees. Use when the user runs /factory:implement, asks to implement a slice or ticket, build the next slice, or work the plan. Each slice ends with /factory:verify and is never committed red.
license: MIT
compatibility: Requires git and the repository's test runner. Parallel mode needs git worktree support.
metadata:
  upstream: "mattpocock-skills/tdd, mattpocock-skills/implement, cursor-plugins/pstack-principles"
allowed-tools: Bash(git:*) Bash(sh ${CLAUDE_SKILL_DIR}/scripts/release-worktree.sh *) Read Edit Write Glob Grep
---

# implement

Build one slice from `plan.md` as a tracer bullet: red test, green code,
verify, commit. In `--all` mode, do that for every slice on the frontier in
its own worktree.

## Load

- `${CLAUDE_PLUGIN_ROOT}/upstream/mattpocock-skills/skills/engineering/tdd/SKILL.md`:
  the red-green loop, seams, and anti-patterns. Read `tests.md` beside it before
  writing a test and `mocking.md` before adding a mock.
- `${CLAUDE_PLUGIN_ROOT}/upstream/mattpocock-skills/skills/engineering/implement/SKILL.md`
  and `implement-spec/SKILL.md`: single-ticket flow and the frontier
  orchestration with worktrees.
- `${CLAUDE_PLUGIN_ROOT}/upstream/cursor-plugins/pstack/skills/principle-prove-it-works/SKILL.md`:
  check the real artifact, not a proxy.

## Translate

- "Use /tdd" and "use /code-review" become the upstream files above and
  `/factory:review`. Refactoring stays out of the red-green loop; it belongs
  to `/factory:simplify`.
- Upstream's single integration branch becomes a stack: each slice commits
  on its own `Branch` from `plan.md`, created from its `Parent`.
- Upstream's `tdd` seam confirmation is satisfied by the seams in `spec.md`.
- Implementer subagents are the `factory:implementer` agent from this
  plugin, run through the Agent tool with `isolation: worktree`.

## Factory rules

- Shell discipline: one command per Bash call, with no `&&`, `;`, pipes,
  redirects, or `$(...)`. A tool grant matches the command word, so a
  compound command is denied whole, and one denied command is not a denied
  tool: retry with a single, simpler command. Read exit codes and output
  from the tool result. Create and edit files with the Write and Edit
  tools, never a shell heredoc.
- Read `factory.toml` for `base` and `[verify].max_iterations`.
- Typecheck and run the single test file often; run the full suite once
  before verify. Use the project's package manager (pnpm, uv, cargo, go).
- Never commit a red tree. Never weaken a test, skip a test, or add a
  suppression to get green; `/factory:verify` treats those as failures.
- Commit per slice with a conventional message that cites the slice id and
  requirement ids, for example `feat(auth): add session refresh (02, R3)`.
- Slice status (claimed, done) lives in the tracker item or issue file,
  never in `plan.md`.

## Steps

Single slice (`/factory:implement <NN>`):

1. Read `plan.md` and `spec.md`. Confirm every blocker of `<NN>` is done and
   the current branch is the slice's `Branch`. If the branch does not exist,
   create it from `Parent`: `git switch -c <branch> <parent>`.
2. Mark the slice claimed in its tracker item or issue file.
3. For each acceptance check: write one failing test at the agreed seam,
   confirm it fails for the right reason, write the smallest code that
   passes, run the file. One behavior per cycle.
4. Run the full suite once. Then run `/factory:verify --loop`, which arms
   the Stop hook before the first stage. If it exits 1, fix only what it
   names and rerun, up to `max_iterations`.
5. Commit the slice together with `<spec_dir>/<slug>/` (spec, plan, and
   any issue files), so the stack carries its own spec and `/factory:pr`
   never meets an untracked plan. Mark the slice done. Reply with the
   branch, the commit, the tests added, and the verify result.

Review fixes (`/factory:implement <NN> --from-review`):

1. Read `<spec_dir>/<slug>/review-NN.md`. Every unchecked `[P0]` to `[P2]`
   item is an acceptance check for this run; `[P3]` items stay as they are
   and are listed in the reply as deferred.
2. On the slice branch, run step 3 above for each item: a failing test at
   the seam where one exists, then the smallest fix. Tick the box.
3. Run the full suite, then `/factory:verify --loop` until 0. Commit the
   fixes with the review file as `fix(<scope>): address review (NN, R..)`.

All frontier slices (`/factory:implement --all`):

1. Compute the frontier from `plan.md`: slices whose blockers are all done.
2. For each frontier slice spawn one `factory:implementer` agent in a
   worktree with the slice id, spec path, plan path, branch, and parent.
   Never run two slices with overlapping write sets at once.
3. When an agent reports done, run
   `sh ${CLAUDE_SKILL_DIR}/scripts/release-worktree.sh <worktree> <NN>`: it
   copies the agent's `.verify/` evidence to `.verify/slices/NN/`, refuses a
   branch with no commit or a dirty tree, and removes the worktree so the branch
   can be checked out here. Then mark the slice done, recompute the frontier,
   and spawn the next wave. Nothing is pushed until `/factory:pr`.
4. Remove the untracked copy of `<spec_dir>/<slug>/` from this checkout
   when every slice commit carries it (`git clean -fd -- <spec_dir>/<slug>`),
   so the slice branches can be checked out. Reply with a table of slices,
   branches, and verify results from `.verify/slices/`, and point at
   `/factory:pr --stack`.

## Done when

The slice's acceptance checks each have a passing test, `/factory:verify`
exited 0, and the commit is on the slice branch.
