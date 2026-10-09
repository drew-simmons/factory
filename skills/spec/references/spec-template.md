# spec.md template

Write `<spec_dir>/<slug>/spec.md` with these headings in this order. Keep
every requirement id stable once written; later plans and reviews cite them.

```markdown
# <Feature name>

Status: draft | agreed
Base: origin/main

## Problem

The problem from the user's point of view. Two to five sentences.

## Solution

What changes for the user once this ships. No implementation detail.

## Requirements

Numbered, testable, one behavior each. Use the project's own vocabulary.

- R1. WHEN <trigger> THEN the system SHALL <observable behavior>.
- R2. IF <state> THEN the system SHALL <observable behavior>.

## Testing decisions

- Seams: the public boundaries tests run against, highest seam first.
  Existing seams before new ones. Name prior art tests in this repo.
- What a good test is here: behavior through the seam, no internals.

## Implementation decisions

Modules touched, interfaces changed, schema or API contracts, and any
architectural choice already made. No file paths, no code, except a snippet
from a prototype that encodes a decision better than prose.

## Out of scope

What this spec deliberately does not cover.

## Assumptions

Decisions the agent made without asking, each one sentence, so the user can
overturn any of them in one pass.

## Open questions

Decisions only the user can make. Number them. Give a recommended answer
for each. Empty when the spec is agreed.
```
