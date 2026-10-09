# PR body

Title: Conventional Commits, `type(scope): subject`, imperative, under 70
characters, no trailing period.

Body, each section under a `##` heading, in this order. Drop a section with
nothing to say. Short sentences, few identifiers, under 40 lines.

```markdown
## Why

The problem and the approach in one to three sentences.

## What changed

- One to three bullets. Name a symbol or path only when it carries the change.

## Scope

Slice NN of <feature> (spec: <path or url>). What this PR leaves out.

## Evidence

- Before: <failing test, output, or screenshot>
- After: <passing test, output, or screenshot>

## Blast radius

One or two sentences on who or what this touches and why that is safe or
risky. Door: one-way or two-way.

## Verification

- `sh verify.sh` exit 0 at <short sha>: <n> changed functions under
  threshold, lawbook <n> passed.
- <other real run path and its outcome>

## Stack

Base: `<parent-branch>`. Parent PR: <url or none>. Next: <slice id or none>.
```

Attach screenshots or a short video when they prove a claim. Do not paste
full SHAs, transcripts, or file-by-file lists.
