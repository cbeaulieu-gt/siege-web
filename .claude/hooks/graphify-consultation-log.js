#!/usr/bin/env node
/**
 * PostToolUse hook — logs every invocation of the `graphify` skill to
 * `docs/graphify-bookkeeping/consultations.jsonl`.
 *
 * Purpose: bookkeeping for the graphify integration experiment (issue #440).
 * We want a deterministic count of how often the graph is actually consulted
 * during normal sessions, separate from whether Claude *thinks* it consulted
 * it. The hook is the source of truth.
 *
 * Schema (one JSON object per line):
 *   {
 *     "timestamp":  "ISO-8601 UTC",
 *     "session_id": "<harness session id>",
 *     "cwd":        "<repo root or wherever Claude was running>",
 *     "args":       "<the Skill tool's args string, often the user's query>"
 *   }
 *
 * The hook NEVER blocks tool execution. All failures are swallowed silently —
 * a broken log file is strictly better than a broken session.
 */

const fs = require("fs");
const path = require("path");

let raw = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => {
  raw += chunk;
});
process.stdin.on("end", () => {
  try {
    const payload = JSON.parse(raw);

    // Only act on Skill tool calls.
    if (payload.tool_name !== "Skill") return;

    // Skill name may be present at tool_input.skill (Claude Code's native shape).
    const skillName = payload.tool_input?.skill ?? payload.tool_input?.name ?? null;
    if (skillName !== "graphify") return;

    const entry = {
      timestamp: new Date().toISOString(),
      session_id: payload.session_id || null,
      cwd: payload.cwd || null,
      args: (payload.tool_input && payload.tool_input.args) || null,
    };

    // Derive log location from the hook's own filesystem position rather than
    // payload.cwd — this is robust to worktree cwd mis-reports and isn't
    // affected by hypothetical poisoned payloads. The hook script always lives
    // at <repo>/.claude/hooks/graphify-consultation-log.js, so <repo> is two
    // levels up. Addresses PR #441 review feedback.
    const repoRoot = path.resolve(__dirname, "..", "..");
    const outDir = path.join(repoRoot, "docs", "graphify-bookkeeping");
    const outFile = path.join(outDir, "consultations.jsonl");
    fs.mkdirSync(outDir, { recursive: true });
    fs.appendFileSync(outFile, JSON.stringify(entry) + "\n");
  } catch {
    // Hook is observation-only. Silent on any failure.
  }
});
