# Graphify Dry-Run for siege-web

A scoped evaluation plan for [`safishamsi/graphify`](https://github.com/safishamsi/graphify) — a tool that builds a queryable knowledge graph (code + docs + PDFs + images) from a project folder and exposes it to AI coding assistants.

**Goal of this dry-run:** produce graphify's artifacts inside `siege-web/graphify-out/` so I can judge whether the graph genuinely illuminates this codebase, **without** modifying my global `~/.claude/CLAUDE.md`, this repo's `.claude/settings.json`, or installing any harness hooks. Everything below is reversible by deleting one folder.

---

## Why this approach

Graphify's full install does two things:

1. **Global**: drops a skill at `~/.claude/skills/graphify/SKILL.md` and **appends a `# graphify` block to `~/.claude/CLAUDE.md`** (string-match guarded — not a fenced/marker block, so manual cleanup is needed if I back it out).
2. **Per-project**: appends a `## graphify` section to this repo's `CLAUDE.md` and registers a `PreToolUse` hook in `.claude/settings.json` that nudges the assistant to consult `GRAPH_REPORT.md` whenever a `Bash` command contains `grep`/`rg`/`find`/etc.

Both are reasonable but non-trivial mutations to harness configuration I tune carefully. The dry-run skips both, runs only the CLI, and lets me decide whether the artifact is worth the integration cost **after** seeing it.

---

## Step 1 — Install the CLI globally

```powershell
uv tool install graphifyy
```

> The PyPI package is `graphifyy` (double-y). The CLI command is `graphify`.

Verify it's on PATH:

```powershell
graphify --version
```

If "not recognized," open a new PowerShell window — `uv tool` updates PATH but the current session won't see it.

---

## Step 2 — Optional: gate the first build with `.graphifyignore`

Cheap insurance. Each non-code file (markdown, PDF, image) becomes an LLM API call during the first build. A `.graphifyignore` (same syntax as `.gitignore`, including `!` negation) keeps vendored deps and build output out of scope.

From the siege-web root:

```powershell
@'
node_modules/
dist/
build/
.next/
.venv/
coverage/
*.generated.*
*.min.js
'@ | Set-Content -Encoding UTF8 .graphifyignore
```

Adjust to siege-web's actual layout. If unsure what to ignore, skip this step — the build will still work, just bigger.

---

## Step 3 — Build the graph (the only step with $ cost)

From the siege-web root:

```powershell
graphify .
```

What happens under the hood:

| Content type | Mechanism | Cost |
| --- | --- | --- |
| Code (29 languages, AST via tree-sitter) | Local | Free |
| Docs, markdown, PDFs, images, videos | LLM API call per file | $$ |

Watch terminal output. If it's processing far more files than expected, `Ctrl+C` and tighten `.graphifyignore` before re-running.

Check the cost summary when it finishes:

```powershell
Get-Content .\graphify-out\cost.json
```

---

## Step 4 — Inspect the three artifacts

```powershell
# The headline summary the assistant would read on every query
code .\graphify-out\GRAPH_REPORT.md

# The interactive graph (click nodes, filter, search)
Start-Process .\graphify-out\graph.html

# The raw graph data (used by the query commands below)
Get-Content .\graphify-out\graph.json | Select-Object -First 50
```

**The honest evaluation lives in `GRAPH_REPORT.md`, not `graph.html`.** The viz is dopamine — colorful and clickable on any codebase. The report's "god nodes," "surprising connections," and "suggested questions" sections are what tell me whether the LLM extraction actually *understood* siege-web. If those sections name files/concepts I'd nominate myself, it worked. If they're generic ("`index.ts` is highly connected") or wrong, it didn't.

---

## Step 5 — Try query commands without any hook wiring

These work directly off `graphify-out/graph.json` — no skill registration, no settings.json mutation:

```powershell
graphify query "how does authentication flow through the app?"
graphify query "what connects the database layer to the API routes?"
graphify path "<some-component-name>" "<some-service-name>"
graphify explain "<a-concept-i-want-mapped>"
```

**Acid test:** ask 3–5 questions I already know the answer to. If it answers them correctly, the tool can help with the ones I don't.

---

## Step 6 — Decide

| Outcome | Next move |
| --- | --- |
| Graph is genuinely illuminating | Run `graphify claude install` (accept the CLAUDE.md / `.claude/settings.json` mutations) |
| Useful but not always-on | Keep the CLI, rebuild manually when useful, query from terminal — no install |
| Generic or wrong | Delete and move on |

---

## Abort / full cleanup

Nothing outside `siege-web/graphify-out/` was touched. To roll back completely:

```powershell
Remove-Item -Recurse -Force .\graphify-out
Remove-Item .\.graphifyignore       # if added and unwanted
Remove-Item .\GRAPHIFY_DRY_RUN.md   # this file
uv tool uninstall graphifyy          # remove the CLI itself
```

After this, the repo is byte-identical to before the dry-run, and `~/.claude/CLAUDE.md` was never modified.

---

## Windows-specific gotchas to watch for

- **`/graphify .` will fail in PowerShell.** PowerShell treats `/` as a path separator. Use `graphify .` (no leading slash). The slash form only works inside an AI coding assistant's chat prompt.
- **The PreToolUse hook graphify installs uses `python3`.** Windows installers typically register `python.exe`, not `python3.exe`. If I do eventually run `graphify claude install`, the hook's `python3 -c "..."` may silently no-op (it's wrapped in `2>/dev/null || true`) — meaning the nudge never fires and I won't know.
- **The hook also relies on Bash `case` syntax.** Claude Code on Windows routes hook commands through Git Bash, so this works — but it's an implicit dependency on Git Bash being present.
- **Hook matcher is substring-based on `*grep*`.** That catches `pg_dump | grep`, `kubectl get pods | grep`, anything-grep. False-positive nudges are low cost but worth knowing.

---

## Reference

- Repo: https://github.com/safishamsi/graphify
- PyPI: https://pypi.org/project/graphifyy/
- Repo signals at evaluation time (2026-05-13): 47k stars, 5k forks, MIT, ~5 weeks old. Star count is anomalously high for age — treat it as marketing signal, not quality signal. Evaluate the artifact, not the badges.
