#!/usr/bin/env sh
# Seeds a python repo with a spec, a one-slice plan, and a slice branch whose
# commit misses one requirement, so /factory:review has a real finding to
# write. Run the case with:
#   claude plugin eval . --case review-writes-handoff --scaffold \
#     --allow-tools Write "Bash(git *)" "Bash(python3 *)"
set -eu
git init -q -b main
git config commit.gpgsign false
git config user.name eval
git config user.email eval@example.com
mkdir -p src tests docs/specs/half-up
cat >pyproject.toml <<'PY'
[project]
name = "money"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[dependency-groups]
dev = ["pytest>=8", "pytest-cov>=5"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
PY
cat >src/money.py <<'PY'
from decimal import ROUND_HALF_EVEN, Decimal


def round_cents(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
PY
cat >tests/test_money.py <<'PY'
from decimal import Decimal

from money import round_cents


def test_round_cents():
    assert round_cents(Decimal("1.234")) == Decimal("1.23")
PY
printf "[factory]\nbase = 'main'\n\n[tracker]\nkind = 'local'\n" >factory.toml
printf '.venv/\n.verify/\n.factory/\n' >.gitignore
cat >docs/specs/half-up/spec.md <<'MD'
# Half-up rounding

Status: agreed
Base: main

## Problem

`round_cents(Decimal("0.125"))` returns 0.12; finance expects 0.13.

## Solution

Every printed amount rounds half up.

## Requirements

- R1. WHEN an amount ends in a half cent THEN `round_cents` SHALL round away from zero.
- R2. WHEN the rounding changes THEN a regression test SHALL cover the half-cent case.

## Testing decisions

- Seams: `round_cents`.

## Implementation decisions

Use `ROUND_HALF_UP`.

## Out of scope

Negative amounts.

## Assumptions

None.

## Open questions

None.
MD
cat >docs/specs/half-up/plan.md <<'MD'
# Half-up rounding plan

Spec: ./spec.md
Base: main
Tracker: local

## Slices

### 01 Round half up

- Requirements: R1, R2
- Blocked by: none
- Branch: half-up/01-round
- Parent: main
- Delivers: half cents round away from zero, with a regression test.
- Acceptance:
  - [ ] test_round_half_cent passes
- Tracker: ./issues/01-round.md

## Waves

```json
{"waves": [{"id": 0, "slices": ["01"]}]}
```
MD
git add -A
git commit -q -m base
git switch -q -c half-up/01-round
sed -i.bak 's/ROUND_HALF_EVEN/ROUND_HALF_UP/g' src/money.py
rm -f src/money.py.bak
git add -A
git commit -q -m "fix(money): round half up (01, R1)"
