# run.md template

Write `<spec_dir>/<slug>/run.md` with these fields. It is the only state
the run skill keeps; a fresh session reads it and continues.

```markdown
# Run: <slug>

Size: small | medium | large
Stage: spec | plan | implement | simplify | review | fix | pr | review-pr | verify | done
Slice: NN            # the slice the per-slice stages are on (large only)
Waiting on: none | spec answers | plan approval | pr

## Log

- 2026-10-10 12:01 spec: drafted docs/specs/<slug>/spec.md, 3 open questions
- 2026-10-10 12:40 spec: agreed
- 2026-10-10 12:41 plan: 3 slices, 2 waves, plan-check exit 0; waiting on approval
- 2026-10-10 13:02 plan: published, 4 issues
- 2026-10-10 13:03 implement --all: 01 02 green in wave 0, 03 green in wave 1
- 2026-10-10 13:40 simplify 01: committed 9d2c1f0
- 2026-10-10 13:45 review 01: 1 P2, 2 P3 in review-01.md
- 2026-10-10 13:52 fix 01: P2 fixed, 7a1e22b; verify exit 0
- 2026-10-10 14:30 pr --stack: #12 #13 #14
- 2026-10-10 14:35 done
```

Rules:

- One line per stage per slice, with the evidence that proves it: a path, a
  count, a commit, an exit code, a URL.
- `Waiting on` is `none` except while a human gate is open.
- `Stage` moves forward only. A failed stage keeps its value and gets a log
  line saying what failed; the next `/factory:run` retries it.
- The file is committed with the first slice like the rest of the spec
  directory, and amended on later slice branches as the run advances.
