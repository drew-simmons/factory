---
title: explain-diff
description: A rich, interactive HTML explanation of a change, diff, branch, or PR. Outside the loop.
---

## What it does

`/factory:explain-diff` writes an interactive HTML page that explains a
code change. It fires when the user asks for a rich explanation of a
change, diff, branch, or PR. It sits outside the factory loop: it reads
the change and the surrounding code, and writes nothing but the
explanation.

## Sections

- **Background.** The existing system relevant to the change, with a deep
  background for beginners that a familiar reader can skip, then a
  narrower background directly relevant to the change.
- **Intuition.** The core idea of the change with concrete examples and
  toy data, figures, and diagrams. The essence, not the full details.
- **Code walkthrough.** The change itself, in reading order.
- **Quiz.** Five questions to check understanding.

## Writes

`.temp/<date>-explanation-<slug>.html`.

## Upstream

This skill is wholly owned and loads no vendored files. It is the one
skill exempt from the lawbook rule that every skill must cite an upstream
method.
