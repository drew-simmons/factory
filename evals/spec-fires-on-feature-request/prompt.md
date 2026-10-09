---
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill, AskUserQuestion]
tags: [trigger]
---

Before we write any code, let's agree on a spec for this: users of our CLI
want a `--json` flag on the `status` command so scripts can parse the output.
Write up the spec so we can review it together.
