/**
 * Post priority constants shared across PostsTab, PostSuggestionsModal,
 * and any other surface that renders a Post's `priority` field.
 *
 * Priority is stored as a raw int on the Post model (not an enum) and
 * mapped to a display label / badge color here.
 */

export const PRIORITY_LABELS: Record<number, string> = {
  0: "Unset",
  1: "Low",
  2: "Medium",
  3: "High",
};

export const PRIORITY_BADGE_COLORS: Record<number, string> = {
  0: "bg-slate-100 text-slate-400",
  1: "bg-slate-100 text-slate-600",
  2: "bg-amber-100 text-amber-700",
  3: "bg-red-100 text-red-700",
};

export function priorityLabel(priority: number): string {
  return PRIORITY_LABELS[priority] ?? String(priority);
}

export function priorityBadgeColor(priority: number): string {
  return PRIORITY_BADGE_COLORS[priority] ?? "bg-slate-100 text-slate-600";
}
