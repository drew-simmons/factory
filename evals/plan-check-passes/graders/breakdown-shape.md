---
type: llm
---

PASS when the reply presents a numbered breakdown of slices where every
slice names a branch and a parent, the slices trace to requirement ids such
as R1, and the reply asks the user about granularity, blocking edges, and
merge or split before publishing.

FAIL when the reply publishes to a tracker or creates issue files before the
user approves, writes implementation code, or presents slices without
branch, parent, or requirement ids.
