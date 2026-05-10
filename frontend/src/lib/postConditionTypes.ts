/**
 * Post condition type taxonomy.
 *
 * The 36 canonical conditions are seeded in backend/app/db/seeds.py with stable,
 * explicit IDs. This static id→type map is intentionally hardcoded: the data is
 * finite, deterministic, and rarely changes. A future seed addition that has no
 * map entry will surface as a test failure in postConditionTypes.test.ts rather
 * than a silent fallback to "other".
 *
 * Follow-up: migrate this map to a backend `condition_type` column so the source
 * of truth lives next to the data (tracked as a separate issue after this MVP).
 */

export type PostConditionType =
  | "role"
  | "affinity"
  | "faction"
  | "league"
  | "rarity"
  | "effect"
  | "other";

/** Human-readable label for each PostConditionType. */
export const POST_CONDITION_TYPE_LABELS: Record<PostConditionType, string> = {
  role: "Role",
  affinity: "Affinity",
  faction: "Faction",
  league: "League",
  rarity: "Rarity",
  effect: "Effect",
  other: "Other",
};

/** Display order — matches the Acceptance Criteria heading order. */
export const POST_CONDITION_TYPE_ORDER: PostConditionType[] = [
  "role",
  "affinity",
  "faction",
  "league",
  "rarity",
  "effect",
  "other",
];

/**
 * id → type, derived from backend/app/db/seeds.py canonical 36.
 *
 * Layout by seed order:
 *   League (4):       ids 1–4
 *   Role (4):         ids 5–8
 *   Faction L1 (8):   ids 9–16
 *   Effect L1 (2):    ids 17–18
 *   Affinity (4):     ids 19–22
 *   Faction L2 (4):   ids 23–26
 *   Effect L2 (2):    ids 27–28
 *   Rarity (3):       ids 29–31
 *   Faction L3 (3):   ids 32–34
 *   Effect L3 (1):    id 35
 *   Other (1):        id 36
 */
export const POST_CONDITION_TYPE_BY_ID: Record<number, PostConditionType> = {
  // League (4)
  1: "league",
  2: "league",
  3: "league",
  4: "league",
  // Role (4)
  5: "role",
  6: "role",
  7: "role",
  8: "role",
  // Faction L1 (8)
  9: "faction",
  10: "faction",
  11: "faction",
  12: "faction",
  13: "faction",
  14: "faction",
  15: "faction",
  16: "faction",
  // Effect L1 (2)
  17: "effect",
  18: "effect",
  // Affinity (4)
  19: "affinity",
  20: "affinity",
  21: "affinity",
  22: "affinity",
  // Faction L2 (4)
  23: "faction",
  24: "faction",
  25: "faction",
  26: "faction",
  // Effect L2 (2)
  27: "effect",
  28: "effect",
  // Rarity (3)
  29: "rarity",
  30: "rarity",
  31: "rarity",
  // Faction L3 (3)
  32: "faction",
  33: "faction",
  34: "faction",
  // Effect L3 (1)
  35: "effect",
  // Other (1)
  36: "other",
};
