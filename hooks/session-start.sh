#!/usr/bin/env sh
# SessionStart hook: tell Claude which factory tools are present. It installs
# nothing and never fails a session start.
set -u

ROOT=${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}

have() { command -v "$1" >/dev/null 2>&1 && echo "$1" || echo "no $1"; }

config=absent
[ -f "$ROOT/factory.toml" ] && config=present
lawbook_cfg=absent
[ -f "$ROOT/lawbook.yaml" ] && lawbook_cfg=present

echo "factory: $(have poly-crap), $(have lawbook), $(have coderabbit), $(have gh), $(have glab), $(have acli), $(have jq); factory.toml $config, lawbook.yaml $lawbook_cfg. Run /factory:setup once per repo, /factory:verify before every commit."
exit 0
