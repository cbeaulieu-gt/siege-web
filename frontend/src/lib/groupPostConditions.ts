/**
 * Pure helper that groups an array of PostCondition objects by either
 * stronghold level or semantic type.
 *
 * No React, no localStorage — easy to test in isolation.
 */

import type { PostCondition } from "../api/types";
import {
  POST_CONDITION_TYPE_BY_ID,
  POST_CONDITION_TYPE_LABELS,
  POST_CONDITION_TYPE_ORDER,
  type PostConditionType,
} from "./postConditionTypes";

/** Grouping mode: group by stronghold level or by semantic type. */
export type GroupByMode = "level" | "type";

/** A single group as returned by groupPostConditions. */
export interface ConditionGroup {
  /** Display heading (e.g. "Stronghold Level 1", "Role", "Faction"). */
  heading: string;
  /** Set when mode="level"; the stronghold level number. */
  level?: number;
  /** Set when mode="type"; the PostConditionType key. */
  type?: PostConditionType;
  /** Conditions in this group, sorted alphabetically by description. */
  items: PostCondition[];
}

/**
 * Group conditions by stronghold level or semantic type.
 *
 * @param conditions - Array of PostCondition objects to group.
 * @param mode - "level" groups by stronghold_level 1/2/3 ascending;
 *               "type" groups in POST_CONDITION_TYPE_ORDER.
 * @returns Array of groups with headings; empty buckets are suppressed.
 */
export function groupPostConditions(
  conditions: PostCondition[],
  mode: GroupByMode
): ConditionGroup[] {
  if (conditions.length === 0) return [];

  if (mode === "level") {
    return groupByLevel(conditions);
  }
  return groupByType(conditions);
}

// ─── Level grouping ───────────────────────────────────────────────────────────

function groupByLevel(conditions: PostCondition[]): ConditionGroup[] {
  const buckets = new Map<number, PostCondition[]>();
  for (const c of conditions) {
    const existing = buckets.get(c.stronghold_level) ?? [];
    existing.push(c);
    buckets.set(c.stronghold_level, existing);
  }

  return [...buckets.entries()]
    .sort(([a], [b]) => a - b)
    .map(([level, items]) => ({
      heading: `Stronghold Level ${level}`,
      level,
      items: [...items].sort((a, b) =>
        a.description.localeCompare(b.description)
      ),
    }));
}

// ─── Type grouping ────────────────────────────────────────────────────────────

function groupByType(conditions: PostCondition[]): ConditionGroup[] {
  const buckets = new Map<PostConditionType, PostCondition[]>();

  for (const c of conditions) {
    // Defensive fallback: unknown ids land in "other"
    const type: PostConditionType =
      POST_CONDITION_TYPE_BY_ID[c.id] ?? "other";
    const existing = buckets.get(type) ?? [];
    existing.push(c);
    buckets.set(type, existing);
  }

  // Emit groups in canonical order; suppress empty buckets
  return POST_CONDITION_TYPE_ORDER.flatMap((type) => {
    const items = buckets.get(type);
    if (!items || items.length === 0) return [];
    return [
      {
        heading: POST_CONDITION_TYPE_LABELS[type],
        type,
        items: [...items].sort((a, b) =>
          a.description.localeCompare(b.description)
        ),
      },
    ];
  });
}
