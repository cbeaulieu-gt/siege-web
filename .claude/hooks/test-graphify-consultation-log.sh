#!/usr/bin/env bash
# Smoke tests for graphify-consultation-log.js
# Run from repo root: bash .claude/hooks/test-graphify-consultation-log.sh
set -euo pipefail

HOOK=".claude/hooks/graphify-consultation-log.js"
JSONL="docs/graphify-bookkeeping/consultations.jsonl"

# Ensure output directory and file exist so we can manipulate them cleanly.
mkdir -p "docs/graphify-bookkeeping"
touch "$JSONL"

# Back up any existing content so real telemetry is not polluted.
BACKUP=$(mktemp)
cp "$JSONL" "$BACKUP"

# Restore on exit regardless of pass/fail.
restore() {
  cp "$BACKUP" "$JSONL"
  rm -f "$BACKUP"
}
trap restore EXIT

# Helper: count lines in the log file.
line_count() {
  wc -l < "$JSONL"
}

PASS=0
FAIL=0

fail() {
  echo "FAIL: $1"
  FAIL=$((FAIL + 1))
}

# ── Case 1: non-Skill payload ──────────────────────────────────────────────
BEFORE=$(line_count)
printf '{"tool_name":"Bash","tool_input":{"command":"echo hi"},"session_id":"test-1"}' \
  | node "$HOOK"
AFTER=$(line_count)
if [ "$AFTER" -eq "$BEFORE" ]; then
  echo "PASS: case 1 — non-Skill payload does not append"
  PASS=$((PASS + 1))
else
  fail "case 1 — non-Skill payload appended $((AFTER - BEFORE)) line(s); expected 0"
fi

# ── Case 2: Skill payload but skill != graphify ────────────────────────────
BEFORE=$(line_count)
printf '{"tool_name":"Skill","tool_input":{"skill":"commit-commands:commit"},"session_id":"test-2"}' \
  | node "$HOOK"
AFTER=$(line_count)
if [ "$AFTER" -eq "$BEFORE" ]; then
  echo "PASS: case 2 — non-graphify Skill does not append"
  PASS=$((PASS + 1))
else
  fail "case 2 — non-graphify Skill appended $((AFTER - BEFORE)) line(s); expected 0"
fi

# ── Case 3: valid graphify Skill payload ───────────────────────────────────
BEFORE=$(line_count)
printf '{"tool_name":"Skill","tool_input":{"skill":"graphify","args":"what connects A to B?"},"session_id":"test-3"}' \
  | node "$HOOK"
AFTER=$(line_count)
DELTA=$((AFTER - BEFORE))
if [ "$DELTA" -ne 1 ]; then
  fail "case 3 — expected exactly 1 new line, got $DELTA"
else
  # Verify the appended JSON contains the expected session_id.
  if tail -1 "$JSONL" | grep -qF '"session_id":"test-3"'; then
    echo "PASS: case 3 — graphify Skill appended 1 line with correct session_id"
    PASS=$((PASS + 1))
  else
    fail "case 3 — line was appended but session_id not found in: $(tail -1 "$JSONL")"
  fi
fi

# ── Summary ────────────────────────────────────────────────────────────────
if [ "$FAIL" -eq 0 ]; then
  echo "All 3 hook smoke tests passed."
  exit 0
else
  echo "$FAIL of $((PASS + FAIL)) tests FAILED."
  exit 1
fi
