/**
 * Tests for the groupPostConditions helper.
 *
 * Covered:
 * 1. mode="level" — groups sorted by stronghold_level ascending; items alphabetical by description.
 * 2. mode="type"  — groups in POST_CONDITION_TYPE_ORDER; items alphabetical by description.
 * 3. Empty buckets are suppressed (heading not emitted).
 * 4. Conditions whose id is not in the map fall through to "other" (defensive).
 */

import { describe, it, expect } from "vitest";
import { groupPostConditions } from "../../lib/groupPostConditions";
import type { PostCondition } from "../../api/types";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function makeCond(
  id: number,
  description: string,
  stronghold_level: number
): PostCondition {
  return { id, description, stronghold_level };
}

// Canonical subset for level tests: a few conditions across all three levels.
// id 5 = role (L1), id 9 = faction (L1), id 19 = affinity (L2), id 29 = rarity (L3)
const MIXED: PostCondition[] = [
  makeCond(9, "Only Banner Lord Champions can be used.", 1),
  makeCond(5, "Only HP Champions can be used.", 1),
  makeCond(19, "Only Void Champions can be used.", 2),
  makeCond(29, "Only Legendary Champions can be used.", 3),
];

// ─── mode="level" ─────────────────────────────────────────────────────────────

describe("groupPostConditions — mode=level", () => {
  it("returns groups sorted by stronghold_level ascending", () => {
    const groups = groupPostConditions(MIXED, "level");
    const levels = groups.map((g) => g.level);
    expect(levels).toEqual([1, 2, 3]);
  });

  it("heading is 'Stronghold Level N'", () => {
    const groups = groupPostConditions(MIXED, "level");
    expect(groups[0].heading).toBe("Stronghold Level 1");
    expect(groups[1].heading).toBe("Stronghold Level 2");
    expect(groups[2].heading).toBe("Stronghold Level 3");
  });

  it("items within a group are sorted alphabetically by description", () => {
    const groups = groupPostConditions(MIXED, "level");
    const l1 = groups.find((g) => g.level === 1)!;
    const descriptions = l1.items.map((c) => c.description);
    expect(descriptions).toEqual([...descriptions].sort());
  });

  it("does not include a group with no items", () => {
    // Only L1 conditions
    const l1Only = MIXED.filter((c) => c.stronghold_level === 1);
    const groups = groupPostConditions(l1Only, "level");
    expect(groups.every((g) => (g.level ?? 0) === 1)).toBe(true);
    expect(groups).toHaveLength(1);
  });
});

// ─── mode="type" ──────────────────────────────────────────────────────────────

describe("groupPostConditions — mode=type", () => {
  it("returns groups in POST_CONDITION_TYPE_ORDER", () => {
    const groups = groupPostConditions(MIXED, "type");
    // MIXED has: role (id 5), faction (id 9), affinity (id 19), rarity (id 29)
    const types = groups.map((g) => g.type);
    // Expected order from spec: role, affinity, faction, league, rarity, effect, other
    // Present: role, affinity, faction, rarity — empty ones suppressed
    expect(types).toEqual(["role", "affinity", "faction", "rarity"]);
  });

  it("heading is the human-readable label (e.g. 'Role')", () => {
    const groups = groupPostConditions(MIXED, "type");
    const headings = groups.map((g) => g.heading);
    expect(headings).toContain("Role");
    expect(headings).toContain("Faction");
    expect(headings).toContain("Affinity");
    expect(headings).toContain("Rarity");
  });

  it("empty buckets are suppressed", () => {
    const groups = groupPostConditions(MIXED, "type");
    // MIXED has no league, effect, or other conditions
    const types = groups.map((g) => g.type);
    expect(types).not.toContain("league");
    expect(types).not.toContain("effect");
    expect(types).not.toContain("other");
  });

  it("items within a group are sorted alphabetically by description", () => {
    // Add multiple faction conditions to test within-group sort
    const factions: PostCondition[] = [
      makeCond(16, "Only Orc Champions can be used.", 1),
      makeCond(9, "Only Banner Lord Champions can be used.", 1),
      makeCond(14, "Only Lizardmen Champions can be used.", 1),
    ];
    const groups = groupPostConditions(factions, "type");
    const factionGroup = groups.find((g) => g.type === "faction")!;
    const descriptions = factionGroup.items.map((c) => c.description);
    expect(descriptions).toEqual([...descriptions].sort());
  });

  it("condition with unknown id falls through to 'other'", () => {
    // Use an id not in the map (e.g. 99)
    const unknown = [makeCond(99, "Unknown condition", 1)];
    const groups = groupPostConditions(unknown, "type");
    const types = groups.map((g) => g.type);
    expect(types).toContain("other");
  });
});

// ─── Edge cases ───────────────────────────────────────────────────────────────

describe("groupPostConditions — edge cases", () => {
  it("returns empty array for empty input", () => {
    expect(groupPostConditions([], "level")).toEqual([]);
    expect(groupPostConditions([], "type")).toEqual([]);
  });
});
