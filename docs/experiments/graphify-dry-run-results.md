# Graphify Dry-Run — Results & Decision

**Date:** 2026-05-15
**Tool:** [`safishamsi/graphify`](https://github.com/safishamsi/graphify) (PyPI `graphifyy`)
**Tracking issue:** #397
**Runbook:** [`graphify-dry-run.md`](./graphify-dry-run.md)
**Decision:** Do not adopt.

---

## TL;DR

The dry-run was executed twice against rsl-siege-manager at commit `6085fd66` — once excluding tests, once including them. Evaluated against the acid-test criteria from #397 (god nodes, surprising connections, and suggested questions should reflect things the user would nominate themselves), the tool failed on all three headline outputs. The without-tests run surfaces utilities and React page components alongside legitimate domain models; the with-tests run is dominated by test fixtures. Neither output justifies integrating a `PreToolUse` hook.

---

## What was run

Two runs at commit `6085fd66`:

| Run | Scope | Nodes | Edges | Communities | Extraction quality |
|-----|-------|-------|-------|-------------|-------------------|
| A (codebase only) | `.graphifyignore` excluded `backend/tests/`, `frontend/src/**/__tests__/` | 833 | 1758 | 52 | 85% EXTRACTED / 15% INFERRED (avg confidence 0.59) |
| B (codebase + tests) | No exclusions beyond vendored deps | 1886 | 3876 | 141 | 90% EXTRACTED / 10% INFERRED (avg confidence 0.62) |

Run cost: $0 token cost in both cases. graphify uses tree-sitter for code extraction; LLM API calls fire only for non-code files. After `.graphifyignore`, there were effectively none.

---

## Evaluation against the acid test

Issue #397 set this bar:

> "whether GRAPH_REPORT.md's named extractions (god nodes, surprising connections, suggested questions) reflect things the user would nominate themselves — generic graph-theory output ('`index.ts` is highly connected') means it didn't work."

Each finding below quotes the report directly. The raw artifacts are not committed (see "Artifact handling"), but the quotes are verifiable by re-running the dry-run against the same commit.

### Finding 1 — Test fixtures dominate "core abstractions" with tests included

Run B's god-node list, verbatim (`graphify-out-with-tests/GRAPH_REPORT.md`, lines 141–150):

```
1. `_make_siege()` - 124 edges
2. `_make_member()` - 92 edges
3. `_make_position()` - 85 edges
4. `SiegeMember` - 78 edges
5. `_make_building()` - 64 edges
6. `_make_group()` - 60 edges
7. `BoardPage()` - 55 edges
8. `makeSiegeMember()` - 55 edges
9. `PostsPage()` - 37 edges
10. `_session_with_siege_and_configs()` - 35 edges
```

Six of the top ten — positions 1, 2, 3, 5, 6, and 8 — are test factory functions (`_make_siege`, `_make_member`, `_make_position`, `_make_building`, `_make_group`, `makeSiegeMember`). Position 10 is a test session fixture. These are the highest-connectivity nodes in the graph, and they are infrastructure for verifying the codebase, not the codebase itself.

This is the cleanest failure signal in the dataset. The god-node list is explicitly labeled "your core abstractions." No developer would nominate `_make_siege()` as a core abstraction of a siege-assignment web app. The metric — degree centrality — is measuring test coverage, not architecture. The inversion is structural: the better your test coverage, the more your test factories saturate every part of the codebase, and the higher their degree count climbs. Codebases that most need architectural insight (low coverage, high complexity) will produce the cleanest god-node lists. Codebases that least need it (high coverage, known domain) will look like run B.

### Finding 2 — Codebase-only god nodes are surface-level

Run A's god-node list, verbatim (`graphify-out/GRAPH_REPORT.md`, lines 55–64):

```
1. `SiegeMember` - 55 edges
2. `BoardPage()` - 53 edges
3. `Post Suggestions Modal Handoff` - 40 edges
4. `postsTab` - 29 edges
5. `cn()` - 29 edges
6. `PostsPage()` - 28 edges
7. `BuildingType` - 27 edges
8. `MembersPage()` - 27 edges
9. `MemberRole` - 25 edges
10. `Self-Host on Azure Wiki Page` - 23 edges
```

`SiegeMember`, `BuildingType`, and `MemberRole` at positions 1, 7, and 9 are legitimate domain models a developer would identify as important. That is three of ten.

The remaining seven are less useful. `BoardPage()`, `PostsPage()`, and `MembersPage()` at positions 2, 6, and 8 are React top-level page components — they import many things because they are entry points, not because they encode domain logic. `cn()` at position 5 is a one-line Tailwind class-merging utility (`src/lib/utils.ts`). It scores 29 edges because every component that merges conditional classes imports it. This is the canonical generic-graph-theory false positive the runbook warned about: `cn()` is "highly connected" in the same way `/dev/null` would be if files wrote to it — the connection count reflects a structural pattern, not semantic importance. `Post Suggestions Modal Handoff` at position 3 is a planning document node extracted from `docs/design-refs/`, not a code entity at all. `Self-Host on Azure Wiki Page` at position 10 is a wiki article.

The acid test asks whether these are things the user would nominate. They are not.

### Finding 3 — Surprising connections cross language boundaries spuriously

Both runs surface INFERRED edges between Python backend types and TypeScript frontend types, presented under the heading "Surprising Connections (you probably didn't know these)." From run A (`graphify-out/GRAPH_REPORT.md`, lines 73–74):

```
- `AuthError` --uses--> `Member`  [INFERRED]
  backend/app/api/auth.py → frontend/src/api/types.ts
```

And from run B (`graphify-out-with-tests/GRAPH_REPORT.md`, lines 158–159):

```
- `TestStartupValidation` --uses--> `MemberRole`  [INFERRED]
  backend/tests/test_auth.py → frontend/src/api/types.ts
```

A Python class does not "use" a TypeScript type at runtime. These are name-based similarity matches — `AuthError` and `Member` share a namespace with identically-named constructs in the frontend — presented as semantic relationships. The confidence is low (avg INFERRED confidence 0.59 in run A, 0.62 in run B), but the framing ("you probably didn't know these") presents them as insights worth investigating. They are not.

The one genuinely plausible INFERRED connection in run A is:

```
- `PostPriorityResponse` --uses--> `PostPriorityConfig`  [INFERRED]
  backend/app/api/post_priority_config.py → frontend/src/api/posts.ts
```

The backend schema and the frontend type do mirror each other by contract. But that relationship is a deliberate design decision well-known to anyone who wrote it — not a discovery.

### Finding 4 — Community cohesion is universally weak

The majority of rsl-siege-manager's 52 communities (run A) score between 0.05 and 0.17 on cohesion. Run A community distribution:

- Communities 0, 2, 3, 6: cohesion 0.05–0.06 (the four largest communities, 36–112 nodes each)
- Most remaining communities: cohesion 0.08–0.17
- Cohesion above 0.25: six communities, all small (3–10 nodes)

The report itself flags cohesion 0.05 as "weakly interconnected" in the Suggested Questions section: "Should `Community 0` be split into smaller, more focused modules? — Cohesion score 0.05 - nodes in this community are weakly interconnected." Community 0 has 112 nodes.

rsl-siege-manager has a clean three-service architecture (backend / frontend / bot) that any developer can describe in a sentence. The graph algorithm is not finding that structure — it is producing communities with no legible semantic identity and flagging most of them as internally incoherent.

### Finding 5 — Noise inflated into knowledge gaps

Run A reports 259 isolated nodes; run B reports 752. The leading examples in both are identical (`graphify-out/GRAPH_REPORT.md`, line 213; `graphify-out-with-tests/GRAPH_REPORT.md`, line 447):

```
`initial schema  Revision ID: 0001 Revises: Create Date: 2026-03-16`,
`add autofill and attack day preview columns to siege  Revision ID: 0002 Revises:`,
`make siege date nullable  Revision ID: 0003 Revises: 0002 Create Date: 2026-03-1`,
`Add post_priority_config table`, ...
```

These are Alembic migration revision docstrings parsed as standalone graph nodes. A migration docstring like `"make siege date nullable"` is a change-tracking annotation, not an architectural entity. There are 17 Alembic migration files in this repo. The isolated-node count growing from 259 to 752 when tests are added is almost entirely test docstrings and test function descriptions parsed the same way.

The report labels these as "possible documentation gaps or missing edges" — a framing that implies they are meaningful silences the developer should investigate. They are not gaps; they are noise.

### Finding 6 — Suggested questions are self-referential

The Suggested Questions section in both runs consists primarily of two kinds of questions:

1. **Betweenness centrality prompts:** "Why does `_make_siege()` connect Community 12 to Community 0, Community 1, Community 3...?" These ask the developer to explain why a test fixture has high betweenness. The answer is obvious: it creates the primary domain object; every test uses it.

2. **Inferred-edge audits:** "Are the 17 inferred relationships involving `SiegeMember` (e.g. with `Base` and `TestSeedDemoMembers`) actually correct?" This is the tool asking the developer to validate the tool's own low-confidence connections. It is not the tool answering questions about the codebase; it is the tool outsourcing its uncertainty.

Run A's most interesting question — "What is the exact relationship between `bootstrap-images.ps1` and `scripts/bootstrap-images.ps1`?" — is itself tagged AMBIGUOUS. The answer is: they are the same script referenced by two slightly different paths in different contexts. This is a file-naming question, not an architectural one.

---

## What graphify is good at

The throughput is fine: 833 nodes in a few minutes, $0 LLM cost on a code-heavy repo. The tree-sitter extraction is genuinely fast and does pick up real entities — `SiegeMember`, `BuildingType`, and `MemberRole` in the god-node list are correct. The `graph.html` interactive visualization is well-built and easy to navigate. The EXTRACTED cross-service connections are occasionally real: `PostPriorityResponse --uses--> PostPriorityConfig` between `backend/app/api/post_priority_config.py` and `frontend/src/api/posts.ts` reflects an actual contract.

The problem is not the underlying graph build. The problem is what the report does with it.

---

## Why this is a rejection, not a tuning problem

The headline outputs — god nodes, surprising connections, suggested questions — are what would justify wiring a `PreToolUse` hook that nudges the assistant to consult `GRAPH_REPORT.md` on every `grep`/`rg`/`find` invocation. If those outputs are mostly test fixtures (run B), surface-level import counts (run A), low-confidence cross-language inferences, and self-referential audit requests, then the hook would be steering the assistant's attention toward noise on every search. Tightening `.graphifyignore` further would fix run B's test-fixture problem, but it would not fix the architecture-of-the-metric problem visible in run A: degree centrality will always surface utilities and entry points over domain logic, regardless of what the ignore file excludes. The tool is measuring the right thing (connectivity) for the wrong purpose (identifying abstractions worth knowing about).

---

## Cost incurred vs cost avoided

**Cost incurred:**

- ~10 minutes of CLI time across two runs.
- $0 LLM cost (tree-sitter handled all code; no non-code files survived the ignore filter in any meaningful quantity).

**Cost avoided by not adopting:**

The two harness mutations from `graphify claude install` documented in #397:

1. **Global CLAUDE.md append** — a `# graphify` block appended to `~/.claude/CLAUDE.md` without a parseable fence marker, requiring manual cleanup on backout.
2. **Per-project `PreToolUse` hook** — fires on `Bash` commands containing `grep`/`rg`/`find` substrings. As noted in the runbook's Windows-specific gotchas section: the hook matcher is substring-based (`*grep*`), creating false-positive nudges on `pg_dump | grep`, `kubectl get pods | grep`, and similar. The hook also uses `python3` (not `python.exe`) which may silently no-op on Windows.

---

## Artifact handling

The raw outputs (`graphify-out/`, `graphify-out-with-tests/`) — `graph.html`, `graph.json`, `GRAPH_REPORT.md`, `cache/`, `manifest.json` — total approximately 12 MB and are not committed. They remain locally in the worktree until cleanup. This doc is the durable evidence; specific quotes above are the verifiable findings. Anyone who wants to reproduce can follow [`graphify-dry-run.md`](./graphify-dry-run.md) against the same commit (`6085fd66`).

---

## Follow-up

- Close issue #397 with this doc linked as the decision artifact.
- After #398 merges, run the local `clean-gone` skill (hyphen) to remove the worktree and branch. Do not use `commit-commands:clean_gone` (underscore) — it is broken in this environment due to issue `anthropics/claude-code#52226`.
- `.graphifyignore` in the worktree was auto-generated by the runner script; it does not need to land in `main`.

---

🤖 _Generated by Claude Code on behalf of @cbeaulieu-gt_
