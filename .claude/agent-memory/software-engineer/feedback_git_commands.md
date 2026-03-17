---
name: Git command style — no cd
description: Never use cd before git commands; use git -C <path> instead
type: feedback
---

Never use `cd` before git commands. Use `git -C <path>` to specify the working directory.

**Why:** cd with git causes security errors in this environment.

**How to apply:** Any time a git command needs a specific working directory, use `git -C I:/games/raid/siege-web <command>` (or the relevant path) rather than `cd I:/games/raid/siege-web && git <command>`.
