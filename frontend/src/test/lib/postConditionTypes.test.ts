/**
 * Parity and correctness tests for the POST_CONDITION_TYPE_BY_ID map.
 *
 * These tests act as a guard: if a future seed addition goes unmapped,
 * the parity check will fail rather than silently falling through to "Other".
 *
 * Covered:
 * 1. Every id 1–36 has exactly one entry in the map.
 * 2. No id outside 1–36 exists in the map.
 * 3. No duplicate ids.
 * 4. Bucket counts match the canonical table from the issue spec.
 * 5. Spot-checks for non-obvious classifications.
 * 6. POST_CONDITION_TYPE_ORDER lists all 7 types exactly once in spec order.
 */

import { describe, it, expect } from "vitest";
import {
  POST_CONDITION_TYPE_BY_ID,
  POST_CONDITION_TYPE_ORDER,
  POST_CONDITION_TYPE_LABELS,
  type PostConditionType,
} from "../../lib/postConditionTypes";

describe("POST_CONDITION_TYPE_BY_ID — parity with seed", () => {
  const ids = Object.keys(POST_CONDITION_TYPE_BY_ID).map(Number);

  it("contains exactly 36 entries", () => {
    expect(ids).toHaveLength(36);
  });

  it("every id is in range 1–36", () => {
    for (const id of ids) {
      expect(id).toBeGreaterThanOrEqual(1);
      expect(id).toBeLessThanOrEqual(36);
    }
  });

  it("every id from 1 to 36 has an entry", () => {
    for (let id = 1; id <= 36; id++) {
      expect(POST_CONDITION_TYPE_BY_ID).toHaveProperty(String(id));
    }
  });

  it("no duplicate ids", () => {
    const unique = new Set(ids);
    expect(unique.size).toBe(ids.length);
  });
});

describe("POST_CONDITION_TYPE_BY_ID — bucket counts", () => {
  function count(type: PostConditionType): number {
    return Object.values(POST_CONDITION_TYPE_BY_ID).filter(
      (t) => t === type
    ).length;
  }

  it("Role bucket has 4 conditions", () => expect(count("role")).toBe(4));
  it("Affinity bucket has 4 conditions", () =>
    expect(count("affinity")).toBe(4));
  it("Faction bucket has 15 conditions", () =>
    expect(count("faction")).toBe(15));
  it("League bucket has 4 conditions", () => expect(count("league")).toBe(4));
  it("Rarity bucket has 3 conditions", () => expect(count("rarity")).toBe(3));
  it("Effect bucket has 5 conditions", () => expect(count("effect")).toBe(5));
  it("Other bucket has 1 condition", () => expect(count("other")).toBe(1));
});

describe("POST_CONDITION_TYPE_BY_ID — spot-checks", () => {
  it("id 1 maps to league (Telerian League)", () => {
    expect(POST_CONDITION_TYPE_BY_ID[1]).toBe("league");
  });

  it("id 19 maps to affinity (Void)", () => {
    expect(POST_CONDITION_TYPE_BY_ID[19]).toBe("affinity");
  });

  it("id 23 maps to faction (Demonspawn, Lv2)", () => {
    expect(POST_CONDITION_TYPE_BY_ID[23]).toBe("faction");
  });

  it("id 35 maps to effect (Sheep debuff immunity)", () => {
    expect(POST_CONDITION_TYPE_BY_ID[35]).toBe("effect");
  });

  it("id 36 maps to other (cannot be revived)", () => {
    expect(POST_CONDITION_TYPE_BY_ID[36]).toBe("other");
  });
});

describe("POST_CONDITION_TYPE_ORDER", () => {
  it("lists all 7 types exactly once", () => {
    expect(POST_CONDITION_TYPE_ORDER).toHaveLength(7);
    const unique = new Set(POST_CONDITION_TYPE_ORDER);
    expect(unique.size).toBe(7);
  });

  it("follows the spec order: role, affinity, faction, league, rarity, effect, other", () => {
    expect(POST_CONDITION_TYPE_ORDER).toEqual([
      "role",
      "affinity",
      "faction",
      "league",
      "rarity",
      "effect",
      "other",
    ]);
  });
});

describe("POST_CONDITION_TYPE_LABELS", () => {
  it("has a label for every type in POST_CONDITION_TYPE_ORDER", () => {
    for (const type of POST_CONDITION_TYPE_ORDER) {
      expect(POST_CONDITION_TYPE_LABELS).toHaveProperty(type);
      expect(typeof POST_CONDITION_TYPE_LABELS[type]).toBe("string");
    }
  });
});
