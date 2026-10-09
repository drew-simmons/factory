---
name: lawbook
description: Use lawbook, the CLI that checks a repository against the rules in its lawbook.yaml, and write or extend that file. Use this skill whenever the user mentions lawbook or lawbook.yaml, asks to add, write, tune, or test a code standard or rule, wants a check for something a linter cannot express (naming, error handling, comments, architecture, "every X must Y"), asks to fix or triage lawbook findings in CI, wants a pre-commit or CI step that enforces repository conventions, or asks to forbid or require a pattern, path, or file across the codebase, even if they never say the word "lawbook".
---

# Lawbook

Lawbook checks a directory against the rules in its `lawbook.yaml`: regular
expressions files must or must not match, paths that must or must not exist,
and standards written in prose that a model judges file by file. A failing
rule names the file and the reason, and the exit code says whether the check
passed. Rules are deterministic where a regex can express them and
model-judged only where judgment is needed.

Install with `npm install --global lawbook`, or run it with `npx lawbook`.
It needs Node.js 22.12 or newer.

## Which job is this?

- **Run or interpret a check** (the user wants to know whether the code
  passes, or has findings to fix): see [Running a check](#running-a-check).
- **Create or extend a config** (the user wants a rule, a standard, a
  `lawbook.yaml`): see [Writing a lawbook.yaml](#writing-a-lawbookyaml).
- **Tune a standard the model gets wrong**: see
  [Tuning a standard](#tuning-a-standard).
- **Adopt lawbook on a codebase with existing findings**: see
  [Adopting on an existing codebase](#adopting-on-an-existing-codebase).

The full key-by-key reference, output formats, and provider setup are in
`references/config.md`. Read it when a question goes beyond what is here,
for instance an unusual key, the JSON output shape, or a provider error.

## Running a check

```sh
lawbook check                 # every rule, from lawbook.yaml in the cwd
lawbook check path/to/repo    # another root; globs stay relative to it
lawbook check --no-llm        # deterministic rules only, no credentials needed
lawbook check --only no-console has-readme
lawbook check --changed       # staged, unstaged, and untracked files only
lawbook check --since origin/main
lawbook check --format json   # for parsing; also github, sarif, gitlab
```

Exit codes carry meaning, so read them before the output:

| Code | Meaning | What to do |
| ---- | ------- | ---------- |
| `0` | Every rule passed, was skipped, or had only `warn` findings. | Nothing. |
| `1` | A `level: error` rule has a finding. | Fix the file the finding names. |
| `2` | Lawbook could not run: bad config, invalid pattern, unknown `--only` id, no credentials, over the request budget. | Read the one-line `error:` on stderr and fix the cause, not the code. |

Text output prints one line per rule, `PASS`, `FAIL`, `WARN`, `ERROR`, or
`SKIP`, with findings indented under it:

```txt
FAIL no-console
  src/cli.ts:12: console.log("starting");
WARN spdx-header
  src/cli.ts: does not match /^// SPDX-License-Identifier: /
FAIL errors-are-actionable
  src/init.ts: "unexpected state" on line 41 says what broke but not what to do. (noul 0.12)

0 passed, 2 failed, 1 warned, 0 errored, 0 skipped
```

A `forbid` finding is `path:line: <the line>`, a `require` finding is
`path: does not match /pattern/`, `exists` and `absent` print `missing` or
`exists`, and a `standard` finding carries the model's reason and its
probability that the file meets the standard (`noul`, 0 to 1). `ERROR`
means the provider failed, not that the code is wrong.

### Fixing findings

Fix the code the finding names, then rerun just that rule with `--only <id>`
so the loop is fast and, for `standard` rules, cheap. Verdicts are cached
under `node_modules/.cache/lawbook`, so a rerun on unchanged files makes no
request.

A suppression comment is for a deliberate exception, not a shortcut past a
rule the team agreed on. It names the rule ids and works in any comment
syntax:

```ts
// lawbook-disable-next-line no-console
console.log("the one place we print");
debug(); // lawbook-disable-line no-debug, no-console
/* lawbook-disable-file errors-are-actionable */
```

`forbid` drops suppressed lines, `require` passes a file that disables it,
and `standard` never sends a file that disables it. `exists` and `absent`
look at paths, so comments cannot suppress them. When a whole directory
should be left out, prefer the rule's `exclude` globs.

### Standard rules need a model

`standard` rules call a provider: Amazon Bedrock by default (AWS credentials
from the environment, or `AWS_BEARER_TOKEN_BEDROCK`), or `claude-code` when
`llm.provider` says so, which runs the installed `claude` CLI, so the
subscription it is signed into pays; `claude auth status` says whether one
is. Before a run with `standard` rules, check which credentials the
environment has. With none, run `check --no-llm` so the deterministic rules
still run and say that the standards were skipped. Never put a key in
`lawbook.yaml`; the file carries only the provider name, model, and region.

Before the first run of a new or widened `standard` rule, count the cost:

```sh
lawbook check --dry-run      # lists the files per rule, then "N files, M model requests"
```

Every selected file of a `standard` rule is one request, so narrow `files`
or `exclude` until the count is reasonable, and cap the run with
`llm.maxRequests` or `--max-requests <n>`.

## Writing a lawbook.yaml

### Workflow

1. **Look at the repository first.** Note the languages and their
   extensions, where source, tests, fixtures, and generated code live, and
   whether it is a git work tree. The globs come from this, and so does the
   list of existing conventions worth encoding: a CONTRIBUTING.md, a style
   guide, a CLAUDE.md, lint rules that only cover part of a convention.
2. **Start the file.** `lawbook init` writes a commented starter when none
   exists (it refuses to overwrite). When a config exists, extend it; a
   duplicate `id` is an error. Keep the schema comment on line one so
   editors validate the file.
3. **Encode each convention as the most deterministic rule that fits.**
   A path check is `exists` or `absent`. A pattern a regex can express is
   `forbid` or `require`. Only a judgment call becomes a `standard`. A
   `forbid` rule gives the same answer every run and costs nothing; a
   `standard` rule costs a request per file and can flip on borderline
   files.
4. **Run it with no model first.** `lawbook check --no-llm` validates the
   config and runs the deterministic rules. Fix schema errors (unknown
   keys, an invalid regex) before anything else.
5. **Plan, then run the standards.** `lawbook check --dry-run` shows what
   each rule selects and the request count. When it looks right and
   credentials exist, run `lawbook check --only <new-id> --explain` to see
   the model's reasons for passing files too.
6. **Give new standards `level: warn`** until their wording settles, so CI
   stays green while the team reads the findings. Drop the `level` once
   the rule is trusted.
7. **Hand it to CI.** On a pull request, `lawbook check --since origin/main`
   judges only the files the branch changed. A pre-commit hook passes the
   staged files with `--files`. See `references/config.md` for the GitHub,
   GitLab, and pre-commit snippets.

### The shape of the file

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/drew-simmons/lawbook/main/lawbook.schema.json
version: 1
llm:
  provider: bedrock            # bedrock (default) | claude-code
  maxRequests: 200             # stop before the first request when a run would exceed this
rules:
  - id: no-console
    description: Production code logs through the logger
    files: ["src/**/*.ts"]
    exclude: ["src/**/*.test.ts"]
    forbid: 'console\.(log|debug)\('
    message: log through the logger in src/log.ts

  - id: spdx-header
    level: warn
    files: ["src/**/*.ts"]
    require: '^// SPDX-License-Identifier: '

  - id: has-readme
    exists: ["README.md", "docs/**/*.md"]

  - id: no-secrets-on-disk
    absent: ["**/*.pem", ".env"]

  - id: errors-are-actionable
    description: Users can act on every error
    files: ["src/**/*.ts"]
    exclude: ["src/**/*.test.ts"]
    threshold: 0.7
    standard: |
      Every error message shown to a user says what went wrong and what to
      do next. Internal assertions that users never see are exempt.
    fixtures:
      pass: ["fixtures/errors/good.ts"]
      fail: ["fixtures/errors/vague.ts"]
```

Rules run in order. Each has a unique `id`, an optional `description` and
`level` (`error` by default, or `warn`), and exactly one kind key. Unknown
keys anywhere are errors, so a typo cannot silently disable a rule.

| Kind | Needs `files` | Fails when |
| ---- | ------------- | ---------- |
| `forbid` | yes | Any line of a selected file matches. One finding per line. |
| `require` | yes | A selected file matches nowhere. One finding per file. |
| `exists` | no | None of its paths or globs matches anything. |
| `absent` | no | Any of its paths or globs matches. One finding per match. |
| `standard` | yes | The model's probability that a file meets the prose is below `threshold` (default `0.5`). |

### Globs and patterns

- `files` and `exclude` are globs relative to the checked directory. `*`
  stays inside a path segment, `**` crosses directories, `{a,b}` lists
  alternatives. Dotfiles are included, so `.github/**/*.yml` works.
- Inside a git work tree, files that `.gitignore` covers are left out of
  every rule, including `exists` and `absent`, so an ignored local `.env`
  does not count as present. `gitignore: false` turns that off.
- The top-level `ignore` defaults to `**/node_modules/**` and `**/.git/**`;
  setting it replaces the defaults, so repeat them.
- A rule whose globs select nothing passes. Binary files are skipped
  silently.
- `forbid` and `require` are JavaScript regular expressions with the `m`
  and `u` flags, so `^` and `$` match at line boundaries and the syntax
  must be valid in Unicode mode. Quote them with single quotes in YAML so
  backslashes survive. An invalid pattern exits `2`.
- `message` replaces the matched line or the pattern in a `forbid` or
  `require` finding. Use it to say what to do instead.

### Writing a standard

A standard is a prompt the model reads with one file at a time and no other
context, so write it so that one file can be judged on its own.

- **Say what the file must do**, not what reviewers dislike. "Every
  exported function has a doc comment that states what it returns" is
  checkable. "Code is well documented" is not.
- **Name the exemptions.** The model otherwise has to guess whether a test
  helper, an entry point, or a generated file counts. The clean-code
  example ends most standards with "Exempt: ...".
- **Say what an unaffected file means.** A standard about inheritance
  should state that a file with no inheritance meets it, else a passing
  file may be judged at `0.5` for lack of evidence.
- **Keep `files` narrow** and `exclude` tests, fixtures, and generated
  code unless the standard is about them.
- **Use `context`** to send a reference document, such as the style guide
  the standard leans on, with every request. The model is told to judge
  only the file, never the references.
- **Use `scope: set`** only for standards about consistency across files,
  such as "every model exports one class named after its file". The rule
  then makes one request for all selected files and gives one verdict
  with no file name.
- **Pick `threshold` by intent.** Raise it toward `0.8` for standards that
  must be met beyond doubt; lower it toward `0.3` to flag only clear
  violations. The default `0.5` passes a file the model cannot judge.

`examples/clean-code.lawbook.yaml` in the lawbook repository is a tested set
of sixteen rules distilled from ten software engineering books. Copy
standards from it or extend it rather than writing the same ones again:

```yaml
version: 1
extends: ["./clean-code.lawbook.yaml"]
rules: []
```

`extends` takes a path relative to the file or a package specifier resolved
from `node_modules`. Only `rules` are inherited; `ignore`, `gitignore`, and
`llm` come from the file lawbook reads.

## Tuning a standard

When a `standard` rule gives a verdict the user disagrees with, the fix is
almost always the wording, not the code or the model.

1. Run the one rule with reasons for every file:
   `lawbook check --only <id> --explain`. The reason shows what the model
   read into the standard, which is usually the exemption it needs spelled
   out.
2. Add `fixtures` to the rule: `pass`, files that must meet the standard,
   and `fail`, files that must not. Keep them out of `files` or `exclude`
   them so `check` does not judge them as code.
3. Run `lawbook test` (or `lawbook test --only <id>`). It judges each
   fixture alone and lists the ones on the wrong side of `threshold`, with
   the model's reason. Exit `1` means a fixture is misclassified.
4. Tighten the wording or move `threshold`, and run again. Verdicts are
   cached, so only changed fixtures and changed standards cost a request.

A file whose probability sits near `0.5` on every run is telling you the
standard is unclear, not that the model is.

## Adopting on an existing codebase

A new rule on an old codebase finds a lot. Record today's findings so only
new ones fail:

```sh
lawbook check --baseline lawbook-baseline.json --update-baseline
lawbook check --baseline lawbook-baseline.json      # from then on, and in CI
```

Commit the baseline. Run `--update-baseline` with the same `--config`,
`--only`, and `--no-llm` flags as the checks that read it, and without
`--files`, `--changed`, or `--since`, since it replaces the file with this
run's findings rather than merging. Entries are keyed without line numbers,
so edits elsewhere in a file do not resurface them, and each carries a
`count`, so a second `console.log` in a file that had one still fails.

## Things that go wrong

- **`error: no lawbook.yaml, lawbook.yml, lawbook.json found`**: run from
  the repository root, pass the root as the argument, or `--config <file>`.
- **A rule passes on a file that should fail**: check the globs with
  `--dry-run`; the file may be excluded, gitignored, binary, or over
  `llm.maxBytes` (listed as `skipped`).
- **`ERROR <id>` with a credential or region message**: the provider, not
  the code. Set the AWS credentials or `AWS_REGION`, run `claude auth login`
  for `claude-code`, or run `--no-llm`.
- **`over llm.maxRequests`**: narrow `files`, pass `--only`, or raise the
  cap deliberately.
- **`--dry-run prints text or json, not github`**: the annotation formats
  have nothing to annotate without a run.
- **`--files` or `--only` swallow the root**: both take lists, so put the
  root before them: `lawbook check . --files a.ts b.ts`.
