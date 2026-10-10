# Simulations

End-to-end runs of the factory loop, driven the way a user would drive it:
one headless `claude -p` session per skill, loading this checkout as the
plugin, against a small fixture repository pushed to a throwaway private
GitHub repository. The fixtures' `lawbook.yaml` extends lawbook's
`clean-code.lawbook.yaml` example, once by relative path and once by npm
package specifier, and `factory.toml` turns on the model-judged lawbook
stage.

| Run | Fixture | Shape | Proves |
|---|---|---|---|
| `small-bug` | `ledger` (python, uv, pytest-cov) | one-function rounding bug, one slice | setup, spec, plan, implement, simplify, pr, review, plus verify.sh probes: stamp, floor, poly-crap |
| `medium-feature` | `status` (typescript, pnpm, vitest, tsc) | a `--json` flag, two stacked slices | the node stack path, a PR whose base is the previous slice |
| `large-feature` | `ledger` | monthly statement, four slices in three waves | `implement --all` with implementer agents in worktrees, one PR per slice on its parent |

## Running one

```sh
sh simulations/run.sh small-bug
```

Needs `claude`, `gh`, `jq`, `uuidgen`, `poly-crap`, `lawbook`, `uv`, `pnpm`,
and `timeout`. `gh` needs a token: `GH_TOKEN` when set, otherwise the `pass`
entry `Personal/GITHUB_TOKEN` (override with `SIM_GH_PASS_ENTRY`). `SIM_REPO`
picks the GitHub repository (each run has its own throwaway by default),
`SIM_BUDGET` the dollar cap per session (default 10), `SIM_MODEL` the model,
`SIM_STAGE_TIMEOUT` the seconds a session may take (default 1800),
`SIM_WORK_ROOT` where the fixture checkouts go.

The sessions run with a Claude config directory that holds only the
credentials, so the user's global `CLAUDE.md` and settings cannot steer a
run. `SIM_ISOLATE=0` turns that off.

A run takes between fifteen minutes and an hour and spends real model
budget. It is not part of CI or `pytest`. It exits 1 when any check failed.

## What a run writes

Everything lands under `simulations/results/<run>/`, which git ignores:

- the fixture checkout itself is at `$SIM_WORK_ROOT/<run>/repo` (default
  `$TMPDIR/factory-sim`), outside this repository: a checkout under this
  worktree's `.claude/` path makes Claude Code treat every write as a
  sensitive config edit and deny it.
- `<stage>.json`, `<stage>.result.md`, `<stage>.stderr`,
  `<stage>.denials.jsonl`: the session envelope, its final reply, and every
  tool call the permission rules denied.
- `<stage>.verify/` and `<stage>.factory/`: `.verify/` and `.factory/` as
  the stage left them.
- `stages.tsv`: exit code, error flag, turns, cost, seconds, and denials per
  stage. `checks.tsv`: one pass or FAIL line per assertion.

Checks assert on files and on the forge (`gh issue list`, `gh pr view`),
never on the model's prose, so a run cannot pass by describing work it did
not do. Every stage also gets three checks for free: the session ended
without error, no tool call was denied, and it finished on its own rather
than on the budget or turn cap.

```sh
sh simulations/report.sh small-bug
```

prints the stage and check tables of a finished run as markdown for the
report.

## How the sessions are driven

`lib.sh` starts every session with `--permission-mode acceptEdits` and
`--permission-prompts none`, so edits are accepted and any tool a skill did
not declare is denied and logged. Stages that need a user reply, the spec's
grilling round and the plan's approval, get a scripted second turn through
`--resume`.

## Reports

Each batch of runs gets a report in `reports/` with the tables from
`report.sh`, the findings, and what was filed or fixed as a result. The
fixture repositories on GitHub (`factory-sim-<run>`) stay until deleted by
hand:

```sh
gh repo delete drew-simmons/factory-sim-small-bug --yes
```
