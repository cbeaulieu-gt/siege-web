/**
 * GroupByToggle — "Group by: Level / Type" segmented control.
 *
 * Uses the same inline-button + cn() pattern as the sub-tabs in
 * PostPrioritiesPage rather than introducing a new shadcn primitive.
 */

import { cn } from "../lib/utils";
import type { GroupByMode } from "../lib/groupPostConditions";

interface Props {
  value: GroupByMode;
  onChange: (next: GroupByMode) => void;
  /** Extra class names for the container. */
  className?: string;
}

/**
 * A compact segmented control labelled "Group by: Level / Type".
 *
 * @example
 * <GroupByToggle value={mode} onChange={setMode} />
 */
export function GroupByToggle({ value, onChange, className }: Props) {
  return (
    <div
      className={cn("flex items-center gap-1.5", className)}
      role="group"
      aria-label="Group by"
    >
      <span className="text-xs font-medium text-slate-500">Group by:</span>
      <div className="flex gap-0.5 rounded-md border border-slate-200 bg-slate-100 p-0.5">
        <button
          type="button"
          aria-pressed={value === "level"}
          onClick={() => onChange("level")}
          className={cn(
            "rounded px-2.5 py-1 text-xs font-medium transition-colors",
            value === "level"
              ? "bg-white text-slate-900 shadow-sm"
              : "text-slate-600 hover:text-slate-900"
          )}
        >
          Level
        </button>
        <button
          type="button"
          aria-pressed={value === "type"}
          onClick={() => onChange("type")}
          className={cn(
            "rounded px-2.5 py-1 text-xs font-medium transition-colors",
            value === "type"
              ? "bg-white text-slate-900 shadow-sm"
              : "text-slate-600 hover:text-slate-900"
          )}
        >
          Type
        </button>
      </div>
    </div>
  );
}
