#!/usr/bin/env sh
# report.sh <run>: print the stage and check tables of a finished run as
# markdown, ready to paste into simulations/reports/<date>.md. The human adds
# the narrative; the numbers are never retyped.
set -u
SIM=$(cd "$(dirname "$0")" && pwd)
RUN=${1:?usage: report.sh <run>}
RESULTS=$SIM/results/$RUN
[ -f "$RESULTS/stages.tsv" ] || { echo "report.sh: no $RESULTS/stages.tsv" >&2; exit 2; }

printf '### %s\n\n' "$RUN"
awk -F'\t' '
  { sessions++; if ($5 != "-") cost += $5; if ($6 != "-") secs += $6 }
  END { printf "%d sessions, $%.2f, %d min.\n\n", sessions, cost, secs / 60 }
' "$RESULTS/stages.tsv"

printf '| Stage | Exit | Error | Turns | USD | Seconds | Denials | Subtype |\n|---|---|---|---|---|---|---|---|\n'
awk -F'\t' '{ printf "| %s | %s | %s | %s | %s | %s | %s | %s |\n", $1, $2, $3, $4, $5, $6, $7, $8 }' "$RESULTS/stages.tsv"

pass=$(grep -c '^pass' "$RESULTS/checks.tsv")
fail=$(grep -c '^FAIL' "$RESULTS/checks.tsv")
printf '\n%s checks passed, %s failed.\n\n' "$pass" "$fail"
if [ "$fail" -gt 0 ]; then
  printf '| Stage | Failed check |\n|---|---|\n'
  awk -F'\t' '$1 == "FAIL" { printf "| %s | %s |\n", $2, $3 }' "$RESULTS/checks.tsv"
  printf '\n'
fi
