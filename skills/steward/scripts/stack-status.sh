#!/usr/bin/env sh
# stack-status: one row per slice of a plan, from the forge, plus the frontier.
#
#   sh stack-status.sh <plan.md>
#
# Columns: slice, branch, parent, pr, state, draft, mergeable, checks,
# review, parent_merged, url. Then two lines:
#   frontier: <NN>|none        the lowest slice whose PR is not merged
#   restack: <NN ...>|none     slices whose parent PR merged while their own
#                              PR still targets the parent branch
# Exit 0 with rows, 2 when gh or the plan is unusable. Needs gh and jq.
set -u

PLAN=${1:?usage: stack-status.sh <plan.md>}
HERE=$(cd "$(dirname "$0")" && pwd)
command -v gh >/dev/null 2>&1 || { echo "stack-status: gh is not installed" >&2; exit 2; }
command -v jq >/dev/null 2>&1 || { echo "stack-status: jq is not installed" >&2; exit 2; }
ROWS=$(python3 -I "$HERE/../../plan/scripts/plan-check.py" "$PLAN" --stack) || exit 2
BASE=$(sed -n 's/^Base: *//p' "$PLAN" | head -n 1)
BASE_SHORT=${BASE#origin/}
TMPDIR_STATUS=$(mktemp -d)
trap 'rm -rf "$TMPDIR_STATUS"' EXIT

pr_number() { gh pr list --head "$1" --state all --json number --jq '.[0].number // empty' 2>/dev/null; }
pr_view() {
  gh pr view "$1" --json state,isDraft,mergeable,reviewDecision,baseRefName,url,statusCheckRollup 2>/dev/null
}
checks_of() {
  printf '%s' "$1" | jq -r '
    (.statusCheckRollup // []) as $c
    | if ($c | length) == 0 then "none"
      elif any($c[]; (.conclusion // "") | IN("FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED")) then "red"
      elif any($c[]; (.status // "COMPLETED") != "COMPLETED") then "pending"
      else "green" end'
}

FRONTIER=none
RESTACK=
printf 'slice\tbranch\tparent\tpr\tstate\tdraft\tmergeable\tchecks\treview\tparent_merged\turl\n'
printf '%s\n' "$ROWS" | while IFS="$(printf '\t')" read -r id branch parent; do
  number=$(pr_number "$branch")
  if [ -z "$number" ]; then
    printf '%s\t%s\t%s\t-\tNONE\t-\t-\t-\t-\t%s\t-\n' "$id" "$branch" "$parent" "$( [ "$parent" = "$BASE" ] || [ "$parent" = "$BASE_SHORT" ] && echo base || echo '?')"
    continue
  fi
  view=$(pr_view "$number")
  state=$(printf '%s' "$view" | jq -r '.state')
  draft=$(printf '%s' "$view" | jq -r '.isDraft')
  mergeable=$(printf '%s' "$view" | jq -r '.mergeable')
  review=$(printf '%s' "$view" | jq -r '.reviewDecision // "none"')
  url=$(printf '%s' "$view" | jq -r '.url')
  target=$(printf '%s' "$view" | jq -r '.baseRefName')
  checks=$(checks_of "$view")
  if [ "$parent" = "$BASE" ] || [ "$parent" = "$BASE_SHORT" ]; then
    parent_merged=base
  else
    pn=$(pr_number "$parent")
    if [ -n "$pn" ] && [ "$(pr_view "$pn" | jq -r '.state')" = "MERGED" ]; then parent_merged=yes; else parent_merged=no; fi
  fi
  printf '%s\t%s\t%s\t#%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$id" "$branch" "$parent" "$number" "$state" "$draft" "$mergeable" "$checks" "$review" "$parent_merged" "$url"
  # The while loop runs in a subshell; hand the verdicts out through files.
  [ "$state" != "MERGED" ] && [ ! -f "$TMPDIR_STATUS/frontier" ] && printf '%s' "$id" >"$TMPDIR_STATUS/frontier"
  [ "$parent_merged" = yes ] && [ "$state" != "MERGED" ] && [ "$target" = "$parent" ] && printf '%s ' "$id" >>"$TMPDIR_STATUS/restack"
done
[ -f "$TMPDIR_STATUS/frontier" ] && FRONTIER=$(cat "$TMPDIR_STATUS/frontier")
[ -f "$TMPDIR_STATUS/restack" ] && RESTACK=$(sed "s/ *$//" "$TMPDIR_STATUS/restack")
printf 'frontier: %s\n' "$FRONTIER"
printf 'restack: %s\n' "${RESTACK:-none}"
