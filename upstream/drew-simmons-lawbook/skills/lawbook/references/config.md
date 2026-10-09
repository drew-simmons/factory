# lawbook reference

The complete `lawbook.yaml` format, every command and flag, the output
formats, and provider setup. `SKILL.md` covers the workflow; come here for
a key, a flag, or a shape. The published docs at
<https://drew-simmons.github.io/lawbook/> say the same in more words, and
`lawbook schema` prints the JSON Schema the installed version validates
with.

## Contents

1. [Config file](#config-file)
2. [Rules](#rules)
3. [The llm section and providers](#the-llm-section-and-providers)
4. [Commands and flags](#commands-and-flags)
5. [Output formats](#output-formats)
6. [Baseline file](#baseline-file)
7. [CI and hook snippets](#ci-and-hook-snippets)
8. [Exit codes](#exit-codes)

## Config file

`lawbook check` reads the first of `lawbook.yaml`, `lawbook.yml`, or
`lawbook.json` in the checked directory, unless `--config` names a file.
JSON is valid YAML, so both share one schema. Unknown keys anywhere are
errors.

| Key | Required | Meaning |
| --- | --- | --- |
| `version` | yes | Always `1`. |
| `extends` | no | A config file or a list of them whose rules run before this file's own. An entry starting with `.` or an absolute path is relative to this file; anything else is a package specifier resolved from `node_modules` the way `require` would, so `@acme/lawbook-rules` or `@acme/lawbook-rules/strict.yaml` works once installed. Rules are collected depth-first. Only `rules` are inherited; `ignore`, `gitignore`, and `llm` come from the file lawbook reads, so a config that extends another and sets only `llm` (with `rules: []`) runs the same rules through a different judge. Globs in inherited rules are relative to the checked directory. A duplicate id across files, a cycle, or an unresolvable entry exits `2`. |
| `ignore` | no | Globs no rule looks at. Defaults to `["**/node_modules/**", "**/.git/**"]`; setting it replaces the defaults. |
| `gitignore` | no | Whether files `.gitignore` covers are left out when the root is inside a git work tree. Defaults to `true`. One `git ls-files` call lists the tracked files plus untracked files git does not ignore, and every rule selects from that listing. |
| `llm` | no | The model that judges `standard` rules. See below. |
| `rules` | yes | The rules, run in order. |

Editor support comes from the first line:

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/drew-simmons/lawbook/main/lawbook.schema.json
```

## Rules

Every rule:

| Key | Required | Meaning |
| --- | --- | --- |
| `id` | yes | Unique across the config and everything it extends. Names the rule in output, in `--only`, and in suppression comments. |
| `description` | no | A note for readers. JSON output carries it; SARIF uses it as the rule's short description. |
| `level` | no | `error` (default) fails the run on findings. `warn` prints them as `WARN` and leaves the exit code alone. An `ERROR` status (provider failure) is never a pass whatever the level. |

`forbid`, `require`, and `standard` rules also take:

| Key | Required | Meaning |
| --- | --- | --- |
| `files` | yes | Globs, relative to the checked directory, that select the files the rule reads. At least one. |
| `exclude` | no | Globs the rule leaves out, on top of the top-level `ignore`. |

`forbid` and `require` also take `message`, text that replaces the matched
line or the pattern in each finding.

### forbid

```yaml
- id: no-console
  files: ["src/**/*.ts"]
  exclude: ["src/**/*.test.ts"]
  forbid: 'console\.(log|debug)\('
  message: log through the logger in src/log.ts
```

Fails on every line of a selected file that matches. Finding:
`path:line: <the line>` or `path:line: <message>`.

### require

```yaml
- id: spdx-header
  files: ["src/**/*.ts"]
  require: '^// SPDX-License-Identifier: '
```

Fails for every selected file the pattern matches nowhere. Finding:
`path: does not match /pattern/` or `path: <message>`.

Patterns are JavaScript regular expressions compiled with the `m` and `u`
flags: `^` and `$` match at line boundaries, and the pattern must be valid
Unicode-mode syntax (so a stray `\-` or an unescaped `{` is an error).
Quote them with single quotes in YAML. An invalid pattern exits `2`.

A `forbid` pattern is tested one line at a time, so `\n` and a lookaround
into another line never match. A `require` pattern is tested against the
whole file. A rule about two adjacent lines is a `require` with a negative
lookahead anchored to the start of the file by `(?<![\s\S])`:

```yaml
- id: exports-are-documented
  files: ["src/**/*.js"]
  require: '(?<![\s\S])(?![\s\S]*?(?<!\*/)\nexport (async )?function)'
  message: an exported function has no doc comment above it
```

### exists and absent

```yaml
- id: has-docs
  exists: ["README.md", "docs/**/*.md"]
- id: no-keys
  absent: ["**/*.pem", ".env"]
```

Each takes one path or glob, or a list. A plain path matches a file or a
directory with that name; a glob matches files only. `exists` passes when
anything matches and fails with `path: missing` per entry otherwise.
`absent` reports `path: exists` for every match. Both honor `ignore` and
`.gitignore` but not `--files`, `--changed`, or `--since`, since they are
about the tree, not the change set.

### standard

```yaml
- id: errors-are-actionable
  description: Users can act on every error
  files: ["src/**/*.ts"]
  exclude: ["src/**/*.test.ts"]
  threshold: 0.7
  scope: file
  standard: |
    Every error message shown to a user says what went wrong and what to
    do next. Internal assertions that users never see are exempt.
  context: ["docs/style.md"]
  fixtures:
    pass: ["fixtures/errors/good.ts"]
    fail: ["fixtures/errors/vague.ts", "fixtures/errors/silent.ts"]
  llm: { model: anthropic.claude-sonnet-5 }
```

| Key | Required | Meaning |
| --- | --- | --- |
| `standard` | yes | The standard in prose. |
| `threshold` | no | Probability, `0` to `1`, a file must reach to pass. Default `0.5`. |
| `scope` | no | `file` (default) judges each selected file in its own request. `set` sends every selected file in one request, each as a `File: <path>` block, and gets one verdict for the set; the finding names no file. A set over `llm.maxBytes` is an `ERROR` without a request. |
| `llm` | no | Per-rule overrides: `provider`, `model`, `region`. A rule that keeps the run's provider inherits its model and region. A rule that names the other provider starts from that provider's defaults. `concurrency`, `maxBytes`, and `cache` always come from the run's `llm`. |
| `context` | no | Files, relative to the checked directory, sent with every request as reference material and never judged. A missing or binary one exits `2` before any request. They sit in the cached prompt prefix and do not count against `maxBytes`. |
| `fixtures` | no | `pass`, files that must meet the standard, and `fail`, files that must not. `lawbook test` judges them. |

How a file is judged: one request carries a fixed system prompt, the
standard, any `context`, the file's path, and its full content. The model
answers `{ "noul": number, "reason": string }`, where `noul` is the
probability from `0` to `1` that the file meets the standard and `0.5`
means it cannot tell. Files the standard does not apply to are to be
treated as meeting it. Files are judged up to `llm.concurrency` at a time
with no knowledge of each other, and results print in path order.

Files over `llm.maxBytes` are listed as `path: skipped, N bytes over
llm.maxBytes M` and do not change the rule's status. A file with
`lawbook-disable-file <id>` is listed as `path: suppressed by
lawbook-disable-file` and never sent.

Verdicts are cached under `node_modules/.cache/lawbook/` in the checked
directory, keyed by model, system prompt, standard, context, path, and
content. A rerun on an unchanged tree makes no request. `--no-cache` skips
it for one run, `--cache-dir` moves it, and `llm.cache: false` turns it off.

## The llm section and providers

Defaults:

```yaml
llm:
  provider: bedrock
  model: anthropic.claude-haiku-4-5
  concurrency: 4
  maxBytes: 131072
  cache: true
```

| Key | Meaning |
| --- | --- |
| `provider` | `bedrock` (default) or `claude-code`, which runs the installed `claude` CLI. |
| `model` | The model id in the provider's own naming. Bedrock defaults to `anthropic.claude-haiku-4-5` and takes only undated `anthropic.<model>` ids; its Messages endpoint does not serve every model Bedrock lists (not Haiku 5.5 or Sonnet 5.5 as of October 2026), and a 404 names what to use. `claude-code` defaults to `claude-haiku-5-5` and also takes an alias such as `sonnet`. |
| `region` | Bedrock only. Else `AWS_REGION`, else `AWS_DEFAULT_REGION`. Under `claude-code` it is a config error. |
| `concurrency` | Files judged at once. Integer, at least `1`, default `4`. Lower it when rate-limited. |
| `maxBytes` | Largest file sent, in bytes. Default `131072`. |
| `cache` | Whether verdicts are cached on disk. Default `true`. |
| `maxRequests` | Most model requests one run may make. No default. The plan is counted before any client is built, and a run over the cap exits `2` with both numbers. `--max-requests` overrides it. |

Credentials never go in the file:

| Provider | Credentials |
| --- | --- |
| `bedrock` | The AWS chain: environment variables, a shared profile, SSO, or an instance role; else `AWS_BEARER_TOKEN_BEDROCK` as a bearer token. The region must offer the model. |
| `claude-code` | The login of the `claude` CLI on `PATH`: `claude auth login` once, then `claude auth status`. `ANTHROPIC_API_KEY` works too, billed as API usage. |

A problem building the client (missing region, missing key) exits `2`
before any rule runs. A provider error on a request is recorded against
that file, the rule stops sending new requests and reports the rest as
`not judged after an earlier error`, the rule's status is `ERROR`, every
other rule still runs, and the run exits `2` after printing the report.

## Commands and flags

`lawbook` with no command prints usage and exits `2`. `--help` and
`--version` exit `0`.

### lawbook init [root]

Writes a starter `lawbook.yaml` into `root` (default `.`) and prints its
path. Exits `2` when any config file already exists there or `root` does
not exist. The starter has two rules that pass in an empty directory and
commented examples of the rest.

### lawbook check [root]

| Flag | Meaning |
| --- | --- |
| `-c, --config <file>` | Read this config. Globs in it stay relative to `root`. |
| `--format <format>` | `text` (default), `json`, `github`, `sarif`, `gitlab`. |
| `--only <ids...>` | Run only these rules, in config order. An unknown id exits `2`. |
| `--no-llm` | Report `standard` rules as `SKIP` without building a provider client. |
| `--files <paths...>` | Check only these files. Paths are relative to the current directory or absolute. |
| `--changed` | Only files changed in the working tree against `HEAD`: staged, unstaged, untracked. |
| `--since <ref>` | Only files committed since the merge base with `ref` (`git diff <ref>...HEAD`). |
| `--baseline <file>` | Hide the findings this file records. Relative to the current directory. |
| `--update-baseline` | Write this run's findings to the `--baseline` file, then report with them hidden. |
| `--dry-run` | List the files each rule would check and the request count, exit `0`, read nothing, build no client. Text or JSON only. |
| `--explain` | Print the model's reason for passing files too. |
| `--max-requests <n>` | Exit `2` before any request when the plan exceeds `n`. Overrides `llm.maxRequests`. |
| `--no-cache` | Ask the model for every file and store nothing. |
| `--cache-dir <dir>` | Where verdicts are cached. Relative to the current directory. |

`--files`, `--changed`, and `--since` union into one candidate set; a
`files` rule selects only candidates its globs match, so a lockfile or an
image no rule covers is simply not checked. `--changed` and `--since` need
`root` inside a repository and a ref git can resolve, else exit `2`. Both
`--files` and `--only` take lists, so put `root` before them.

Dry-run output:

```txt
PLAN no-console (forbid, 2 files)
  src/cli.ts
  src/init.ts
PLAN has-readme (exists, 1 file)
  README.md
PLAN errors-are-actionable (standard, 2 files)
  src/cli.ts
  src/init.ts

3 files, 2 model requests
```

A `scope: set` rule counts one request. `--format json` gives
`{ "rules": [{ "id", "kind", "level", "files", "requests" }], "requests" }`.

### lawbook test [root]

Judges each `standard` rule's `fixtures`, one file per request, with the
rule's `context` and `llm`, through the same cache as `check`. Rules without
fixtures are left out.

| Flag | Meaning |
| --- | --- |
| `-c, --config <file>` | As for `check`. |
| `--format <format>` | `text` (default) or `json`. |
| `--only <ids...>` | Test only these rules. |
| `--no-cache`, `--cache-dir <dir>` | As for `check`. |

```txt
FAIL errors-are-actionable
  fixtures/errors/vague.ts: expected fail, judged pass (noul 0.72): The messages name the failing step.

4 fixtures, 1 misclassified
```

JSON: `{ "rules": [{ "id", "cases": [{ "path", "expected", "actual",
"decision", "reason" }] }], "summary": { "cases", "misclassified" } }` with
every fixture. Exit `1` when any fixture is misclassified, `2` when a
fixture is missing or binary or the provider fails.

### lawbook schema

Prints the JSON Schema for `lawbook.yaml` from the installed version.

## Output formats

### text

One line per rule, findings indented, then a summary that always lists all
five counts: `N passed, N failed, N warned, N errored, N skipped`. When a
`standard` rule ran, one more line reports cost:
`3 requests (1 cached), 4210 input tokens, 180 output tokens`. Findings a
baseline hides are counted as `  N findings in baseline` under the rule.

### json

```json
{
  "results": [
    {
      "id": "errors-are-actionable",
      "kind": "standard",
      "level": "error",
      "status": "fail",
      "findings": [
        {
          "path": "src/cli.ts",
          "message": "\"unexpected state\" on line 41 says what broke but not what to do.",
          "decision": { "type": "noul", "noul": 0.12 }
        }
      ],
      "decisions": {
        "src/cli.ts": { "type": "noul", "noul": 0.12 },
        "src/init.ts": { "type": "noul", "noul": 0.97 }
      },
      "usage": { "inputTokens": 310, "outputTokens": 48, "cacheReadInputTokens": 1200, "cacheCreationInputTokens": 400, "requests": 2, "cached": 0 }
    }
  ],
  "summary": { "passed": 0, "failed": 1, "warned": 0, "errored": 0, "skipped": 0, "usage": { "...": "same shape" } }
}
```

`status` is `pass`, `fail`, `warn`, `error`, or `skip`. `forbid` findings
carry a 1-based `line`. A judged `standard` rule adds `decisions` by path
(or one `decision` for `scope: set`), `reasons` by path under `--explain`,
`skipped` as `[{ "path", "message" }]`, and `baselined` when a baseline hid
findings.

### github

One workflow command per finding, so a GitHub Actions job annotates the pull
request inline, then the summary as a notice. `warn` findings annotate as
warnings, everything else as errors.

```txt
::error file=src/cli.ts,line=12,title=no-console::console.log("starting");
::notice title=lawbook::0 passed, 1 failed, 0 warned, 0 errored, 0 skipped
```

### sarif

SARIF 2.1.0 with one run: one rule per lawbook rule (its `description` as
the short description), one result per finding, paths relative to a `ROOT`
base. Findings without a path (a multi-pattern `exists`, a `scope: set`
finding) have no `locations`.

### gitlab

A GitLab code quality report: a JSON array with one issue per finding.
`severity` is `major` under a failing rule, `minor` under `warn`, `critical`
for a provider error. The `fingerprint` hashes rule, path, and message but
not the line. Findings without a path are located at the config file, line 1.

## Baseline file

```json
{
  "version": 1,
  "findings": [
    { "rule": "no-console", "path": "src/old.ts", "message": "console.log(\"x\");", "count": 1 },
    { "rule": "errors-are-actionable", "path": "src/cli.ts", "count": 1 }
  ]
}
```

| Kind | Key |
| --- | --- |
| `forbid` | rule, path, message (the matched line, or the rule's `message`, in which case one entry counts all of a file's matches) |
| `require`, `exists`, `absent` | rule and path |
| `standard` | rule and path; a `scope: set` finding is keyed by the rule alone. Provider errors are never baselined. |

A run hides `count` identical findings and shows the rest. Entries are
sorted, so regenerating gives a readable diff. `--update-baseline` replaces
the file; it does not merge. A missing or invalid baseline exits `2`, as
does `--update-baseline` without `--baseline`.

## CI and hook snippets

GitHub Actions, pull requests only:

```yaml
- uses: actions/checkout@v5
  with:
    fetch-depth: 0
- run: npx lawbook check --since origin/${{ github.base_ref }} --format github
  env:
    AWS_REGION: us-west-2
    AWS_BEARER_TOKEN_BEDROCK: ${{ secrets.AWS_BEARER_TOKEN_BEDROCK }}
```

`github.base_ref` is set on `pull_request` events only. Drop the `env` and
add `--no-llm` when the job has no provider credentials.

GitHub code scanning:

```yaml
- run: npx lawbook check --format sarif > lawbook.sarif
  continue-on-error: true
- uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: lawbook.sarif
```

GitLab:

```yaml
lawbook:
  script: npx lawbook check --format gitlab > gl-code-quality-report.json
  artifacts:
    when: always
    reports:
      codequality: gl-code-quality-report.json
```

pre-commit or prek, using the hooks the lawbook repository defines
(`lawbook` skips `standard` rules, `lawbook-llm` runs them):

```yaml
repos:
  - repo: https://github.com/drew-simmons/lawbook
    rev: v0.1.0
    hooks:
      - id: lawbook
```

Or with `lawbook` installed globally:

```yaml
- repo: local
  hooks:
    - id: lawbook
      name: lawbook
      entry: lawbook check . --no-llm --files
      language: system
```

Persist `node_modules/.cache/lawbook` between CI jobs with a cache action
so unchanged files cost no request.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Every rule passed, was skipped, or had only `warn` or baselined findings. For `test`, every fixture landed on its side. |
| `1` | A `level: error` rule has a finding the baseline does not hide, or a fixture is misclassified. Findings print on stdout; stderr is empty. |
| `2` | Lawbook could not do what was asked: bad usage, a missing or invalid config, an invalid pattern, an unknown `--only` id, a bad baseline, `--changed` or `--since` outside git, a run over `llm.maxRequests`, or a provider that could not be reached or gave no verdict. Config and usage errors print one `error:` line on stderr and no report; a provider error during a rule still prints the report with the rule as `ERROR`. |
