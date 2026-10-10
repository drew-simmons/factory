#!/usr/bin/env sh
# Seeds a python repo with an agreed spec and a local tracker, so /factory:plan
# has everything it needs and nothing to publish to a forge. Run the case with:
#   claude plugin eval . --case plan-check-passes --scaffold \
#     --allow-tools Write "Bash(git *)" "Bash(python3 *)"
set -eu
git init -q -b main
git config commit.gpgsign false
git config user.name eval
git config user.email eval@example.com
mkdir -p src tests docs/specs/json-status
cat >pyproject.toml <<'PY'
[project]
name = "status"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[dependency-groups]
dev = ["pytest>=8", "pytest-cov>=5"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
PY
cat >src/status.py <<'PY'
def report(version: str, uptime: int) -> dict:
    return {"version": version, "uptime": uptime}


def render(data: dict) -> str:
    return "\n".join(f"{k}: {v}" for k, v in data.items())
PY
cat >tests/test_status.py <<'PY'
from status import render, report


def test_render():
    assert render(report("1.0", 3)) == "version: 1.0\nuptime: 3"
PY
printf "[factory]\nbase = 'main'\n\n[tracker]\nkind = 'local'\n" >factory.toml
printf '.venv/\n.verify/\n.factory/\n' >.gitignore
cat >docs/specs/json-status/spec.md <<'MD'
# JSON status output

Status: agreed
Base: main

## Problem

Scripts cannot parse the status report because it is plain text only.

## Solution

A `--json` flag prints the same report as one JSON object on one line.
Text stays the default.

## Requirements

- R1. WHEN `status --json` runs THEN the system SHALL print the report as one JSON object on one line.
- R2. WHEN `status` runs without the flag THEN the output SHALL be unchanged.
- R3. IF an unknown flag is given THEN the system SHALL exit 2 with usage.

## Testing decisions

- Seams: the `render` function for the JSON shape; the CLI entry point for the flag and exit codes.

## Implementation decisions

A `render_json` beside `render`; argument parsing in a new `cli` module.

## Out of scope

Pretty-printed JSON.

## Assumptions

- `json.dumps` with default separators is acceptable.

## Open questions

None.
MD
git add -A
git commit -q -m base
