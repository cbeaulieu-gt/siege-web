---
name: commit
description: Commits to the current Git repository
---

- Commit your current changes.
- Do not use composite commands, which always force a permission request from the user.
- Given you're already in the Git repository folder - do not explicitly `cd` first - as it's redundant, and can also cause a composite command. 
- After a successful commit, ask me with the AskUserQuestion tool if I'd like you to push. Never push without asking.