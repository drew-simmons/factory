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
# Reads the hook payload on stdin. Exits 0 (let the turn end) when no loop is
# armed, when the loop belongs to another session, when this turn is already a
# continuation forced by this hook, when nothing changed against the base, or
# when verify passes. Otherwise bumps the iteration and prints a block decision
# whose reason is verify's own summary. At max_iterations it disarms and lets
# the turn end with a note, so a stuck loop cannot run forever.
#
# Adapted from drew-simmons/verify-loop and the ralph-loop plugin.
set -u

INPUT=$(cat)
json() { printf '%s' "$INPUT" | jq -r "$1" 2>/dev/null; }

if [ "$(json '.stop_hook_active // false')" = "true" ]; then
  exit 0
fi

ROOT=${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}
cd "$ROOT" 2>/dev/null || exit 0
STATE=.factory/loop.local.md
[ -f "$STATE" ] || exit 0

FRONT=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$STATE")
field() { printf '%s\n' "$FRONT" | sed -n "s/^$1: *//p" | head -n 1; }
STATE_SESSION=$(field session_id)
HOOK_SESSION=$(json '.session_id // ""')
if [ -n "$STATE_SESSION" ] && [ "$STATE_SESSION" != "$HOOK_SESSION" ]; then
  exit 0
fi
ITERATION=$(field iteration)
MAX=$(field max_iterations)
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
  jq -n --rawfile log .verify/stop.tail --arg n "$NEXT" --arg max "$MAX" \
    '{decision: "block", reason: ("verify found problems in the current change (loop " + $n + " of " + $max + "). Fix only what is named, then run /factory:verify until it exits 0. Do not weaken tests or thresholds.\n\n" + $log)}'
else
  jq -n --rawfile log .verify/stop.tail --arg n "$NEXT" --arg max "$MAX" \
    '{decision: "block", reason: ("verify could not run (exit 2, loop " + $n + " of " + $max + "). Fix the setup it names, not the code, then run /factory:verify.\n\n" + $log)}'
fi
exit 0
