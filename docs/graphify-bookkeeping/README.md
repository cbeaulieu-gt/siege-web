# graphify bookkeeping

Telemetry for the graphify knowledge-graph integration (issue [#440](https://github.com/glitchwerks/rsl-siege-manager/issues/440)).

The graph itself lives in `graphify-out/` (gitignored). This directory tracks **how the graph is used** so we can answer two questions after a few weeks:

1. **Is the graph actually being consulted?** Or has Claude been told it exists but not reached for it?
2. **When it is consulted, is the information correct?** Where does it mislead, and what category of failure dominates (stale, missing edge, wrong direction, fabricated)?

If both look good, the integration earns its keep and we can consider promoting to MCP, building an architecture-only second graph, or shipping the pattern to other repos. If either looks bad, we yank it.

## Files

| File | Source | Schema | Append method |
|---|---|---|---|
| `consultations.jsonl` | `PostToolUse` hook at `.claude/hooks/graphify-consultation-log.js` | `{timestamp, session_id, cwd, args}` | Automatic on every `Skill(graphify, ...)` call |
| `misfires.jsonl` | Manual — Claude appends per CLAUDE.md instructions when user signals "wrong" | `{timestamp, query, graph_claim, correction, source_file_corrected?, category}` | `Edit`/`Write` tool, no user prompt — extract from context |

Both files are JSONL — one JSON object per line, no enclosing array, no trailing comma.

## Schemas

### `consultations.jsonl`

```json
{
  "timestamp":  "2026-05-17T10:23:14.512Z",
  "session_id": "01HXYZ...",
  "cwd":        "I:\\games\\raid\\siege-web",
  "args":       "query \"How does day-role-sync flow?\""
}
```

- `timestamp` — ISO-8601 UTC, set by the hook at append time.
- `session_id` — Claude Code harness session id. Lets us group multiple consultations within one conversation.
- `cwd` — to distinguish runs from the main checkout vs worktrees.
- `args` — the raw `Skill` tool args string. Often the user's query verbatim, including the `/graphify` subcommand (`query`, `--update`, `path`, etc.).

The hook never blocks tool execution. If it errors, no entry is written — the tool call proceeds normally. Treat missing entries as "we got nothing" rather than "the tool didn't run."

### `misfires.jsonl`

```json
{
  "timestamp":           "2026-05-17T10:25:48.000Z",
  "query":               "How does day-role-sync flow?",
  "graph_claim":         "schedule_role_sync() is called from update_siege_member only",
  "correction":          "apply_attack_day also calls schedule_role_sync; the graph missed the fan-out edge",
  "source_file_corrected": "backend/app/api/siege_members.py:L142-L168",
  "category":            "missing_edge"
}
```

Categories (pick one):

| Category | Meaning |
|---|---|
| `stale` | Graph reflects an older commit; the code/doc has changed since the last `--update`. Fix: run `/graphify --update`. |
| `missing_edge` | The relationship genuinely exists in the code but the extractor didn't find it. Fix: file an upstream graphify issue or add a manual seed. |
| `wrong_direction` | An edge exists but `source` and `target` are reversed (commonly `calls` edges where AST detection inferred the wrong direction). Fix: same as `missing_edge`. |
| `fabricated` | The graph reported a relationship that does not exist. Fix: tighten the semantic-extraction prompt; also worth checking whether `INFERRED` confidence was low. |
| `other` | Use sparingly; prefer one of the four above. |

## Analyzing

```bash
# How many consultations this week?
.venv/Scripts/python.exe -c "
import json, pathlib, datetime as dt
cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)
entries = [json.loads(l) for l in pathlib.Path('docs/graphify-bookkeeping/consultations.jsonl').read_text().splitlines() if l.strip()]
recent = [e for e in entries if dt.datetime.fromisoformat(e['timestamp'].replace('Z','+00:00')) >= cutoff]
print(f'Consultations (last 7d): {len(recent)}')
"

# Misfire rate
.venv/Scripts/python.exe -c "
import json, pathlib
c = sum(1 for l in pathlib.Path('docs/graphify-bookkeeping/consultations.jsonl').read_text().splitlines() if l.strip())
m = sum(1 for l in pathlib.Path('docs/graphify-bookkeeping/misfires.jsonl').read_text().splitlines() if l.strip())
print(f'Misfires / Consultations: {m}/{c} = {(m/c*100) if c else 0:.1f}%')
"

# Misfire category breakdown
.venv/Scripts/python.exe -c "
import json, pathlib, collections
entries = [json.loads(l) for l in pathlib.Path('docs/graphify-bookkeeping/misfires.jsonl').read_text().splitlines() if l.strip()]
print(collections.Counter(e.get('category', 'other') for e in entries))
"
```

## When to review

Weekly during the experiment. Look for:

- **Zero consultations** → CLAUDE.md hint isn't triggering. Either the trigger list is too narrow, the model isn't recognizing the shapes, or no genuine cross-cutting questions came up. Tighten triggers or expand scope.
- **High consultations, zero misfires** → graph is useful and accurate. Consider promoting to MCP for lower per-call overhead.
- **High consultations, high misfire rate** → graph is shaped right but extraction is wrong. Check the category breakdown — `stale` means freshness is the issue (`--update` discipline); `missing_edge`/`wrong_direction`/`fabricated` mean the extraction itself needs tuning (better prompts, different chunking, exclude tests).
- **Low consultations, high misfire rate** → graph is bad enough that Claude is correctly avoiding it. Yank the integration.

## Out of scope (for now)

- Auto-rotation / size-capping of the JSONL files. They're text, append-only, cheap. Revisit only if they cross ~10 MB.
- Cross-session aggregation (multiple machines / clones). Each clone keeps its own logs.
- Privacy scrubbing. `args` may include user-typed queries — these are the user's own queries about their own code, no PII expected. If that changes, add scrubbing here.
