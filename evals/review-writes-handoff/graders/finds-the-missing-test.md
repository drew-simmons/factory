---
type: llm
---

PASS when the reply reports findings under Standards, Spec, and CodeRabbit
sections (CodeRabbit may say it was skipped), and the Spec section names
the missing regression test for the half-cent case as a finding with a P0
to P3 priority.

FAIL when the reply edits source files, commits, or reports no findings at
all.
