#!/usr/bin/env sh
# scaffold.sh <target-dir> <owner/repo>
#
# Copies the status fixture to <target-dir>, installs its pinned dev
# dependencies, commits it as main with a fixed date so the base commit is
# the same on every run, creates the throwaway GitHub repository when it does
# not exist, and pushes main.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
TARGET=$1
REPO=$2

rm -rf "$TARGET"
mkdir -p "$TARGET"
cp -R "$HERE/." "$TARGET/"
rm -rf "$TARGET/scaffold.sh" "$TARGET/node_modules" "$TARGET/coverage" "$TARGET/.verify"

cd "$TARGET"
git init -q -b main
git config commit.gpgsign false
git config user.name "factory sim"
git config user.email "factory-sim@example.com"
git add -A
GIT_AUTHOR_DATE=2026-10-01T00:00:00Z GIT_COMMITTER_DATE=2026-10-01T00:00:00Z \
  git commit -q -m "chore: seed the status fixture"

if gh repo view "$REPO" --json name >/dev/null 2>&1; then
  git remote add origin "https://github.com/$REPO.git"
else
  gh repo create "$REPO" --private --source . --remote origin \
    --description "Throwaway fixture for factory end-to-end simulations"
fi
git push -q -u origin main
git fetch -q origin
pnpm install --frozen-lockfile --silent
echo "scaffold: $TARGET on $REPO at $(git rev-parse --short HEAD)"
