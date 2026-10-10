#!/usr/bin/env sh
# Stop hook: while a factory loop is armed, a red change cannot end the turn.
#
# The loop is armed when .factory/loop.local.md exists in the project with
# this session's id. /factory:verify --loop and /factory:implement write it:
#
#   ---
#   session_id: <id>
#   iteration: 0
#   max_iterations: 5
#   ---
#
# Reads the hook payload on stdin. The repository is the payload's cwd (a
# worktree agent's stop carries its worktree), else the work tree around the
# current directory, else CLAUDE_PROJECT_DIR. Exits 0 (let the turn end) when
# no loop is armed, when the loop belongs to another session, when nothing
# changed against the base, or when verify passes. Otherwise bumps the
# iteration and prints a block decision whose reason is verify's own summary.
# The bound is max_iterations within one loop, not one forced continuation:
# a stop that this hook itself caused is gated again. At max_iterations it
# disarms and lets the turn end with a note, so a stuck loop cannot run
# forever. Without jq the decision is still a block, with a fixed reason.
#
# Adapted from drew-simmons/verify-loop and the ralph-loop plugin.
set -u

INPUT=$(cat)
if command -v jq >/dev/null 2>&1; then HAVE_JQ=1; else HAVE_JQ=0; fi
# field <jq filter> <key>: a string field of the payload, by jq or by sed.
field() {
  if [ "$HAVE_JQ" = 1 ]; then
    printf '%s' "$INPUT" | jq -r "$1" 2>/dev/null
  else
    printf '%s' "$INPUT" | sed -n "s/.*\"$2\" *: *\"\([^\"]*\)\".*/\1/p" | head -n 1
  fi
}

CWD=$(field '.cwd // ""' cwd)
if [ -n "$CWD" ] && [ -d "$CWD" ]; then cd "$CWD" || exit 0; fi
ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || ROOT=${CLAUDE_PROJECT_DIR:-}
[ -n "$ROOT" ] || exit 0
cd "$ROOT" 2>/dev/null || exit 0
STATE=.factory/loop.local.md
[ -f "$STATE" ] || exit 0

FRONT=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$STATE")
state_field() { printf '%s\n' "$FRONT" | sed -n "s/^$1: *//p" | head -n 1; }
STATE_SESSION=$(state_field session_id)
HOOK_SESSION=$(field '.session_id // ""' session_id)
if [ -n "$STATE_SESSION" ] && [ "$STATE_SESSION" != "$HOOK_SESSION" ]; then
  exit 0
fi
ITERATION=$(state_field iteration)
MAX=$(state_field max_iterations)
case $ITERATION in ''|*[!0-9]*) ITERATION=0 ;; esac
case $MAX in ''|*[!0-9]*) MAX=5 ;; esac

if [ "$ITERATION" -ge "$MAX" ]; then
  rm -f "$STATE"
  echo "factory: verify loop reached $MAX iterations; disarmed. The change is still red." >&2
  exit 0
fi

SCRIPT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}/skills/verify/scripts/verify.sh"
mkdir -p .verify
sh "$SCRIPT" >.verify/stop.log 2>&1
rc=$?
if [ "$rc" -eq 0 ]; then
  rm -f "$STATE"
  exit 0
fi

NEXT=$((ITERATION + 1))
TMP="$STATE.tmp.$$"
sed "s/^iteration: .*/iteration: $NEXT/" "$STATE" >"$TMP"
mv "$TMP" "$STATE"
tail -n 40 .verify/stop.log >.verify/stop.tail

if [ "$rc" -eq 1 ]; then
  HEAD_LINE="verify found problems in the current change (loop $NEXT of $MAX). Fix only what is named, then run /factory:verify until it exits 0. Do not weaken tests or thresholds."
else
  HEAD_LINE="verify could not run (exit $rc, loop $NEXT of $MAX). Fix the setup it names, not the code, then run /factory:verify."
fi
if [ "$HAVE_JQ" = 1 ]; then
  jq -n --rawfile log .verify/stop.tail --arg head "$HEAD_LINE" \
    '{decision: "block", reason: ($head + "\n\n" + $log)}'
else
  printf '{"decision":"block","reason":"%s The findings are in .verify/stop.tail."}\n' "$HEAD_LINE"
fi
exit 0
