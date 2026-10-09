# Publishing slices to a tracker

Publish in dependency order, blockers first, so each slice can cite real
identifiers. Write the body to a temporary file and pass it with a file
flag; never interpolate markdown into a shell string. After publishing,
fill the `Tracker:` line of each slice in `plan.md`.

Slice body, every tracker:

```markdown
## What to build

<Delivers text from plan.md>

## Acceptance criteria

- [ ] ...

## Blocked by

- <identifier> or "None (can start immediately)"

## Stack

Branch `<branch>` on `<parent>`. Spec: <spec path or url>.
```

## local

One file per slice at `<spec_dir>/<slug>/issues/NN-<task>.md`:

```markdown
# NN: <title>

**Blocked by:** NN, NN or None (can start immediately)
**Status:** ready
**Branch:** <branch> on <parent>

## What to build
...
## Acceptance criteria
- [ ] ...
```

Status moves `ready` to `claimed` to `done`. Record claims and results by
editing the file. A slice is unblocked when every file it lists is `done`.

## github

Read
`${CLAUDE_PLUGIN_ROOT}/upstream/mattpocock-skills/skills/engineering/setup-matt-pocock-skills/issue-tracker-github.md`
for the full command set. Minimum:

```bash
gh issue create --title "<Feature>: tracking" --body-file /tmp/tracking.md --label factory
gh issue create --title "NN <title>" --body-file /tmp/NN.md --label factory
gh api repos/<owner>/<repo>/issues/<n> --jq .id
gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>
```

Use native issue dependencies when the API accepts them; otherwise keep the
`Blocked by` line in the body. Add each slice to a task list in the tracking
issue body.

## gitlab

Follow the `glab` skill when it is available; it documents flags that fail
silently. Minimum:

```bash
glab issue create --title "<Feature>: tracking" --description "$(cat /tmp/tracking.md)" --label factory --yes
glab issue create --title "NN <title>" --description "$(cat /tmp/NN.md)" --label factory --yes
glab api --method POST "projects/:id/issues/<child-iid>/links" -f target_issue_iid=<blocker-iid> -f link_type=is_blocked_by
```

## jira

Requires `acli` (Atlassian CLI) and `acli jira auth status` authenticated.
`jira_site`, `jira_project`, and `jira_type` come from `factory.toml`.

```bash
acli jira workitem create --project <KEY> --type Epic --summary "<Feature>" --description-file /tmp/tracking.md --json
acli jira workitem create --project <KEY> --type <jira_type> --summary "NN <title>" --description-file /tmp/NN.md --parent <EPIC-KEY> --json
acli jira workitem link type
acli jira workitem link create --help
```

Create the parent first, then each slice with `--parent`. Link blockers with
`acli jira workitem link create` using the `Blocks` type when the instance
has it; check `--help` for the exact flags before the first call. Keep the
`Blocked by` line in the body as well.
