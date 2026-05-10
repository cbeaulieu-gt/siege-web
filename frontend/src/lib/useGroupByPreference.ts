/**
 * Hook: persists the "Group by" toggle choice in localStorage.
 *
 * Usage:
 *   const [mode, setMode] = useGroupByPreference("siege-web:postConditions:groupBy");
 */

import { useState } from "react";
import type { GroupByMode } from "./groupPostConditions";

const VALID_MODES = new Set<GroupByMode>(["level", "type"]);

/**
 * Read + write a GroupByMode from localStorage.
 *
 * @param storageKey - localStorage key to use. Use the canonical key
 *   `"siege-web:postConditions:groupBy"` everywhere so the preference
 *   follows the user across all three surfaces.
 * @returns `[mode, setMode]` — current mode and a setter that also writes
 *   the new value to localStorage.
 */
export function useGroupByPreference(
  storageKey: string
): [GroupByMode, (next: GroupByMode) => void] {
  const [mode, setModeState] = useState<GroupByMode>(() => {
    try {
      const stored = localStorage.getItem(storageKey);
      if (stored && VALID_MODES.has(stored as GroupByMode)) {
        return stored as GroupByMode;
      }
    } catch {
      // localStorage may be unavailable in sandboxed contexts
    }
    return "level";
  });

  function setMode(next: GroupByMode) {
    setModeState(next);
    try {
      localStorage.setItem(storageKey, next);
    } catch {
      // silently ignore write failures
    }
  }

  return [mode, setMode];
}
