#!/usr/bin/env sh
# Run one end-to-end simulation of the factory loop.
#
#   sh simulations/run.sh small-bug
#   sh simulations/run.sh medium-feature
#   sh simulations/run.sh large-feature
#
# Each run scaffolds a fixture repository under simulations/results/<run>/repo,
# pushes it to a throwaway private GitHub repository, then drives the factory
# skills through headless claude sessions and records what they produced.
# SIM_REPO overrides the GitHub repository, SIM_BUDGET the dollar cap per
# session, SIM_MODEL the model. gh needs a token: GH_TOKEN when set, else the
# pass entry named by SIM_GH_PASS_ENTRY (default Personal/GITHUB_TOKEN).
set -u

SIM=$(cd "$(dirname "$0")" && pwd)
FACTORY=$(cd "$SIM/.." && pwd)
RUN=${1:?usage: run.sh <small-bug|medium-feature|large-feature>}
[ -f "$SIM/runs/$RUN.sh" ] || { echo "run.sh: no run named $RUN" >&2; exit 2; }
for tool in claude gh jq uuidgen poly-crap lawbook; do
  command -v "$tool" >/dev/null 2>&1 || { echo "run.sh: $tool is not installed" >&2; exit 2; }
done
if [ -z "${GH_TOKEN:-}" ]; then
  command -v pass >/dev/null 2>&1 || { echo "run.sh: set GH_TOKEN (pass is not installed)" >&2; exit 2; }
  GH_TOKEN=$(pass show "${SIM_GH_PASS_ENTRY:-Personal/GITHUB_TOKEN}") || { echo "run.sh: no GitHub token" >&2; exit 2; }
  export GH_TOKEN
fi
# A plugin root under a .claude/ directory (where the desktop app keeps its
# worktrees) makes Claude Code treat reads of the vendored upstream files as
# sensitive and deny them in headless mode, so the sessions load the plugin
# through a symlink that keeps .claude/ out of the path.
case $FACTORY in
  */.claude/*)
    WORK_ROOT=${SIM_WORK_ROOT:-${TMPDIR:-/tmp}/factory-sim}
    mkdir -p "$WORK_ROOT"
    ln -sfn "$FACTORY" "$WORK_ROOT/factory-plugin"
    FACTORY=$WORK_ROOT/factory-plugin ;;
esac
export SIM FACTORY RUN
exec sh "$SIM/runs/$RUN.sh"
