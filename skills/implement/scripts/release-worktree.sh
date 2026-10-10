#!/usr/bin/env sh
# release-worktree: take an implementer agent's worktree down without losing
# its evidence or its branch.
#
#   sh release-worktree.sh <worktree-path> <slice-id>
#
# Copies <worktree>/.verify/summary.txt, stop.log, and the loop state file
# into .verify/slices/<slice-id>/ of the main checkout, confirms the slice
# branch has a commit past its parent, then removes the worktree and prunes.
# Exit 0 released, 1 the branch has nothing committed (the worktree is kept
# so the work is not lost), 2 bad arguments or not a worktree.
#
# The branch stays; only the checkout goes, so `git switch <branch>` works in
# the main checkout again. Run from anywhere inside the main checkout.
set -u

WORKTREE=${1:?usage: release-worktree.sh <worktree-path> <slice-id>}
SLICE=${2:?usage: release-worktree.sh <worktree-path> <slice-id>}
ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "release-worktree: not inside a git repository" >&2; exit 2; }
cd "$ROOT" || exit 2
[ -d "$WORKTREE" ] || { echo "release-worktree: $WORKTREE is not a directory" >&2; exit 2; }
WORKTREE=$(cd "$WORKTREE" && pwd -P)
git worktree list --porcelain | grep -Fqx "worktree $WORKTREE" \
  || { echo "release-worktree: $WORKTREE is not a worktree of $ROOT" >&2; exit 2; }

BRANCH=$(git -C "$WORKTREE" branch --show-current)
[ -n "$BRANCH" ] || { echo "release-worktree: $WORKTREE has no branch checked out" >&2; exit 2; }

EVIDENCE=.verify/slices/$SLICE
mkdir -p "$EVIDENCE"
for f in summary.txt stop.log stop.tail green; do
  [ -f "$WORKTREE/.verify/$f" ] && cp "$WORKTREE/.verify/$f" "$EVIDENCE/$f"
done
[ -f "$WORKTREE/.factory/loop.local.md" ] && cp "$WORKTREE/.factory/loop.local.md" "$EVIDENCE/loop.local.md"

# A branch with no commit that some other branch does not already have has
# nothing to release yet.
OTHERS=$(git for-each-ref --format='%(refname)' refs/heads refs/remotes | grep -Fvx "refs/heads/$BRANCH")
# shellcheck disable=SC2086
OWN=$(git rev-list --count "$BRANCH" --not $OTHERS 2>/dev/null || echo 0)
if [ "${OWN:-0}" -eq 0 ]; then
  echo "release-worktree: $BRANCH has no commit of its own; the worktree at $WORKTREE is kept" >&2
  exit 1
fi
if [ -n "$(git -C "$WORKTREE" status --porcelain)" ]; then
  echo "release-worktree: $WORKTREE has uncommitted changes; the worktree is kept" >&2
  exit 1
fi

git worktree remove --force "$WORKTREE" || exit 2
git worktree prune
echo "release-worktree: released $WORKTREE; $BRANCH stays, evidence in $EVIDENCE"
exit 0
