import { useState, useEffect, useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  RefreshCw,
  ArrowRight,
  Plus,
  Check,
  Lock,
  Ban,
  Info,
} from "lucide-react";
import { previewPostSuggestions, applyPostSuggestions } from "../api/sieges";
import type {
  PostSuggestionEntry,
  PostSuggestionPreviewResult,
  PostSuggestionStaleEntry,
} from "../api/types";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog";
import { Button } from "./ui/button";
import { cn } from "../lib/utils";

// ─── Types ────────────────────────────────────────────────────────────────────

type OutcomeFilter = "all" | "new" | "replace" | "same" | "skipped";

type Classification = "new" | "replace" | "same" | "skipped";

interface Props {
  open: boolean;
  onClose: () => void;
  siegeId: number;
}

// ─── Priority metadata (mapped to our scale: 0=Unset, 1=Low, 2=Med, 3=High) ──

const PRIORITY_META: Record<
  number,
  { label: string; pill: string }
> = {
  3: {
    label: "High",
    pill: "bg-rose-50 text-rose-700 ring-rose-200",
  },
  2: {
    label: "Med",
    pill: "bg-amber-50 text-amber-700 ring-amber-200",
  },
  1: {
    label: "Low",
    pill: "bg-slate-50 text-slate-600 ring-slate-200",
  },
  0: {
    label: "Unset",
    pill: "bg-slate-50 text-slate-500 ring-slate-200",
  },
};

function getPriorityMeta(priority: number) {
  return PRIORITY_META[priority] ?? PRIORITY_META[0];
}

// ─── Skip reason labels (adapted from design to our labels) ───────────────────

const SKIP_REASON_LABEL: Record<
  NonNullable<PostSuggestionEntry["skip_reason"]>,
  string
> = {
  no_match: "No member matches any of the post conditions",
  reserve: "Position is set to reserve",
  disabled: "Position is disabled",
};

// ─── Stale reason labels ──────────────────────────────────────────────────────

const STALE_REASON_LABEL: Record<PostSuggestionStaleEntry["reason"], string> =
  {
    position_missing: "position was removed",
    position_disabled: "position was disabled",
    position_reserve: "position was set to reserve",
    member_inactive: "member became inactive",
    member_changed: "another planner assigned a different member",
  };

// ─── Outcome tile configuration ───────────────────────────────────────────────

interface TileConfig {
  key: OutcomeFilter;
  label: string;
  hint: string;
  bar: string;
  text: string;
  soft: string;
  ring: string;
  showSelected: boolean;
}

const TILE_CONFIG: TileConfig[] = [
  {
    key: "all",
    label: "All posts",
    hint: "Everything reviewed",
    bar: "bg-slate-900",
    text: "text-slate-900",
    soft: "bg-white",
    ring: "ring-slate-900",
    showSelected: false,
  },
  {
    key: "new",
    label: "New assignments",
    hint: "Empty positions",
    bar: "bg-violet-500",
    text: "text-violet-700",
    soft: "bg-violet-50",
    ring: "ring-violet-500",
    showSelected: true,
  },
  {
    key: "replace",
    label: "Replacements",
    hint: "Member would change",
    bar: "bg-amber-500",
    text: "text-amber-700",
    soft: "bg-amber-50",
    ring: "ring-amber-500",
    showSelected: true,
  },
  {
    key: "same",
    label: "Already optimal",
    hint: "Suggestion = current",
    bar: "bg-slate-300",
    text: "text-slate-600",
    soft: "bg-white",
    ring: "ring-slate-400",
    showSelected: false,
  },
  {
    key: "skipped",
    label: "Skipped",
    hint: "Cannot fill",
    bar: "bg-rose-400",
    text: "text-rose-700",
    soft: "bg-rose-50",
    ring: "ring-rose-500",
    showSelected: false,
  },
];

// ─── Classify helper ──────────────────────────────────────────────────────────

function classify(entry: PostSuggestionEntry): Classification {
  if (entry.skip_reason) return "skipped";
  if (entry.matches_current) return "same";
  if (entry.current_member_id == null) return "new";
  return "replace";
}

// ─── Sub-components ───────────────────────────────────────────────────────────

/** A colored pill chip used in the member change cell. */
function Pill({
  tone,
  className,
  children,
}: {
  tone: "slate" | "violet" | "amber";
  className?: string;
  children: React.ReactNode;
}) {
  const toneClass = {
    slate: "bg-slate-100 text-slate-700 ring-slate-200",
    violet: "bg-violet-100 text-violet-800 ring-violet-200",
    amber: "bg-amber-100 text-amber-800 ring-amber-200",
  }[tone];
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-1.5 py-0.5 text-[11px] font-medium ring-1 ring-inset",
        toneClass,
        className
      )}
    >
      {children}
    </span>
  );
}

/** The "Member change" cell content — new / replace / same / skipped. */
function ChangeCell({ entry }: { entry: PostSuggestionEntry }) {
  const cls = classify(entry);

  if (cls === "skipped") {
    return (
      <span className="text-sm italic text-slate-400">No suggestion</span>
    );
  }

  if (cls === "same") {
    return (
      <div className="flex min-w-0 items-center gap-2">
        <Pill tone="slate" className="max-w-[140px] truncate">
          {entry.current_member_name}
        </Pill>
        <span className="shrink-0 text-xs italic text-slate-400">
          stays put
        </span>
      </div>
    );
  }

  const before =
    entry.current_member_name ? (
      <Pill
        tone="slate"
        className="max-w-[140px] truncate opacity-70 line-through"
      >
        {entry.current_member_name}
      </Pill>
    ) : (
      <span className="inline-flex shrink-0 items-center gap-1 rounded border border-dashed border-slate-300 bg-white px-1.5 py-0.5 text-[11px] text-slate-400">
        <Plus className="h-2.5 w-2.5" />
        empty
      </span>
    );

  const afterTone = cls === "new" ? "violet" : "amber";

  return (
    <div className="flex min-w-0 items-center gap-2">
      {before}
      <ArrowRight className="h-3.5 w-3.5 shrink-0 text-slate-400" />
      <Pill tone={afterTone} className="max-w-[160px] truncate">
        {entry.suggested_member_name}
      </Pill>
    </div>
  );
}

/** Skip reason icon for the conditions cell. */
function SkipIcon({ reason }: { reason: string | null }) {
  if (reason === "reserve")
    return <Lock className="h-3 w-3" aria-hidden="true" />;
  if (reason === "disabled")
    return <Ban className="h-3 w-3" aria-hidden="true" />;
  return <Info className="h-3 w-3" aria-hidden="true" />;
}

/** The "Matched condition" cell content. */
function ConditionCell({
  entry,
  skipped,
}: {
  entry: PostSuggestionEntry;
  skipped: boolean;
}) {
  if (skipped) {
    const label =
      SKIP_REASON_LABEL[
        entry.skip_reason as NonNullable<PostSuggestionEntry["skip_reason"]>
      ] ?? entry.skip_reason;
    return (
      <span className="inline-flex items-center gap-1 text-xs text-rose-600">
        <SkipIcon reason={entry.skip_reason} />
        {label}
      </span>
    );
  }

  if (!entry.suggested_condition_description) return null;

  return (
    <span className="inline-flex max-w-full items-center gap-1 rounded-md bg-emerald-50 px-1.5 py-0.5 text-[11px] font-medium text-emerald-800 ring-1 ring-inset ring-emerald-200">
      <Check className="h-2.5 w-2.5 shrink-0" aria-hidden="true" />
      <span className="truncate">{entry.suggested_condition_description}</span>
    </span>
  );
}

/** A single filter tile button. */
function SummaryTile({
  config,
  count,
  selectedCount,
  active,
  onClick,
}: {
  config: TileConfig;
  count: number;
  selectedCount?: number;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "group relative flex flex-col gap-0.5 overflow-hidden rounded-lg border px-3 py-2.5 text-left transition-all",
        config.soft,
        active
          ? cn(
              "border-transparent shadow-sm ring-2 ring-offset-1",
              config.ring
            )
          : "border-slate-200 hover:border-slate-300 hover:shadow-sm"
      )}
    >
      <span
        className={cn(
          "absolute inset-y-0 left-0 w-1 rounded-l-lg",
          config.bar,
          !active && "opacity-80"
        )}
      />
      <span className="ml-1.5 text-[11px] font-medium uppercase tracking-wide text-slate-500">
        {config.label}
      </span>
      <div className="ml-1.5 flex items-baseline gap-1.5">
        <span className={cn("text-2xl font-semibold tabular-nums", config.text)}>
          {count}
        </span>
        {config.showSelected && selectedCount != null && count > 0 && (
          <span className="text-xs tabular-nums text-slate-500">
            · {selectedCount} selected
          </span>
        )}
      </div>
      <span className="ml-1.5 text-[11px] text-slate-400">{config.hint}</span>
    </button>
  );
}

/** Loading sub-state: spinner + label. */
function StateLoading() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 px-6">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-violet-500" />
      <p className="text-sm text-slate-500">Generating suggestions…</p>
    </div>
  );
}

/** Empty sub-state: 0 posts on this siege. */
function StateEmpty({ onClose }: { onClose: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-16 px-8 text-center">
      <div className="rounded-full bg-slate-100 p-3 text-slate-400">
        <Info className="h-6 w-6" aria-hidden="true" />
      </div>
      <p className="text-sm font-medium text-slate-700">
        No posts on this siege
      </p>
      <p className="max-w-xs text-xs text-slate-500">
        Add post buildings in siege settings before generating suggestions.
      </p>
      <Button
        size="sm"
        className="mt-1"
        onClick={onClose}
      >
        Open settings
      </Button>
    </div>
  );
}

/** Stale-conflict sub-state (after 409). */
function StateStaleConflict({
  staleEntries,
  preview,
  checked,
  onClose,
  onRegenerate,
  onApplyRemaining,
  applyPending,
}: {
  staleEntries: PostSuggestionStaleEntry[];
  preview: PostSuggestionPreviewResult;
  checked: Record<number, boolean>;
  onClose: () => void;
  onRegenerate: () => void;
  onApplyRemaining: (ids: number[]) => void;
  applyPending: boolean;
}) {
  // Position IDs that are stale
  const staleSet = new Set(staleEntries.map((e) => e.position_id));

  // Remaining = actionable positions that are still selected and not stale.
  const remainingIds = preview.assignments
    .filter(
      (e) =>
        e.suggested_member_id !== null &&
        !e.matches_current &&
        checked[e.position_id] &&
        !staleSet.has(e.position_id)
    )
    .map((e) => e.position_id);

  return (
    <div className="flex flex-col">
      {/* Amber conflict banner */}
      <div className="space-y-3 border-b border-amber-100 bg-amber-50 px-6 py-4">
        <p className="text-sm font-medium text-amber-900">
          {staleEntries.length} of your selected changes can no longer be
          applied.
        </p>
        <ul className="space-y-1 text-sm text-amber-800">
          {staleEntries.map((se) => {
            const entry = preview.assignments.find(
              (a) => a.position_id === se.position_id
            );
            const label = entry
              ? `Post #${entry.building_number}`
              : `Position ${se.position_id}`;
            return (
              <li key={se.position_id} className="flex items-baseline gap-2">
                <span className="font-mono text-xs text-amber-700">{label}</span>
                <span className="text-xs">
                  — {STALE_REASON_LABEL[se.reason]}
                </span>
              </li>
            );
          })}
        </ul>
      </div>

      {/* Explanation + actions */}
      <div className="px-6 py-4 text-sm text-slate-600">
        <p>
          You can apply the remaining{" "}
          <span className="font-semibold text-slate-900">
            {remainingIds.length}
          </span>{" "}
          changes, or regenerate the preview to incorporate the latest board
          state.
        </p>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-end gap-2 border-t border-slate-100 bg-slate-50 px-6 py-3">
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
        <Button
          variant="outline"
          onClick={onRegenerate}
          disabled={applyPending}
        >
          <RefreshCw className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
          Regenerate
        </Button>
        <Button
          onClick={() => onApplyRemaining(remainingIds)}
          disabled={remainingIds.length === 0 || applyPending}
        >
          Apply remaining {remainingIds.length}
        </Button>
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function PostSuggestionsModal({
  open,
  onClose,
  siegeId,
}: Props) {
  const queryClient = useQueryClient();

  const [preview, setPreview] = useState<PostSuggestionPreviewResult | null>(
    null
  );
  /** Keyed by position_id; true = include in apply payload. */
  const [checked, setChecked] = useState<Record<number, boolean>>({});
  const [staleEntries, setStaleEntries] = useState<
    PostSuggestionStaleEntry[] | null
  >(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [filter, setFilter] = useState<OutcomeFilter>("all");

  const previewMutation = useMutation({
    mutationFn: () => previewPostSuggestions(siegeId),
    onSuccess: (data) => {
      setPreview(data);
      setStaleEntries(null);
      setErrorMessage(null);
      setFilter("all");
      // Pre-check every actionable row (suggested & not matching current)
      const initial: Record<number, boolean> = {};
      for (const entry of data.assignments) {
        initial[entry.position_id] =
          entry.suggested_member_id !== null && !entry.matches_current;
      }
      setChecked(initial);
    },
    onError: () => {
      setErrorMessage("Failed to generate suggestions. Please try again.");
    },
  });

  const applyMutation = useMutation({
    mutationFn: (positionIds: number[]) =>
      applyPostSuggestions(siegeId, positionIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["board", siegeId] });
      queryClient.invalidateQueries({ queryKey: ["posts", siegeId] });
      handleClose();
    },
    onError: (err: unknown) => {
      const axiosErr = err as {
        response?: {
          status?: number;
          data?: { detail?: { stale_entries?: PostSuggestionStaleEntry[] } };
        };
      };
      if (
        axiosErr.response?.status === 409 &&
        axiosErr.response.data?.detail?.stale_entries
      ) {
        setStaleEntries(axiosErr.response.data.detail.stale_entries);
        setErrorMessage(null);
      } else {
        setErrorMessage("Failed to apply suggestions. Please try again.");
      }
    },
  });

  function handleClose() {
    setPreview(null);
    setChecked({});
    setStaleEntries(null);
    setErrorMessage(null);
    setFilter("all");
    onClose();
  }

  // Auto-fire preview when the dialog opens.
  useEffect(() => {
    if (open && !preview && !previewMutation.isPending) {
      previewMutation.mutate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function handleOpen(isOpen: boolean) {
    if (!isOpen) {
      handleClose();
    }
  }

  function toggleCheck(positionId: number) {
    setChecked((prev) => ({ ...prev, [positionId]: !prev[positionId] }));
  }

  function handleApply(positionIds?: number[]) {
    if (!preview) return;
    const ids =
      positionIds ??
      preview.assignments
        .filter(
          (e) =>
            e.suggested_member_id !== null &&
            !e.matches_current &&
            checked[e.position_id]
        )
        .map((e) => e.position_id);
    applyMutation.mutate(ids);
  }

  // ── Derived values ──────────────────────────────────────────────────────────

  const buckets = useMemo(
    () =>
      preview
        ? {
            new: preview.assignments.filter((e) => classify(e) === "new"),
            replace: preview.assignments.filter(
              (e) => classify(e) === "replace"
            ),
            same: preview.assignments.filter((e) => classify(e) === "same"),
            skipped: preview.assignments.filter(
              (e) => classify(e) === "skipped"
            ),
          }
        : { new: [], replace: [], same: [], skipped: [] },
    [preview]
  );

  const selectedNew = useMemo(
    () => buckets.new.filter((e) => checked[e.position_id]).length,
    [buckets, checked]
  );

  const selectedReplace = useMemo(
    () => buckets.replace.filter((e) => checked[e.position_id]).length,
    [buckets, checked]
  );

  const totalSelected = selectedNew + selectedReplace;

  const filteredSorted = useMemo(
    () =>
      preview
        ? [...preview.assignments]
            .filter((e) => filter === "all" || classify(e) === filter)
            .sort(
              (a, b) =>
                b.priority - a.priority || a.building_number - b.building_number
            )
        : [],
    [preview, filter]
  );

  const totalCount = preview ? preview.assignments.length : 0;

  const tileCountMap = useMemo<Record<OutcomeFilter, number>>(
    () => ({
      all: totalCount,
      new: buckets.new.length,
      replace: buckets.replace.length,
      same: buckets.same.length,
      skipped: buckets.skipped.length,
    }),
    [buckets, totalCount]
  );

  const tileSelectedMap = useMemo<Record<OutcomeFilter, number>>(
    () => ({
      all: 0,
      new: selectedNew,
      replace: selectedReplace,
      same: 0,
      skipped: 0,
    }),
    [selectedNew, selectedReplace]
  );

  // ── Render ──────────────────────────────────────────────────────────────────

  const isLoading = previewMutation.isPending && !preview;

  return (
    <Dialog open={open} onOpenChange={handleOpen}>
      <DialogContent className="flex max-h-[90vh] max-w-4xl flex-col gap-0 overflow-hidden p-0">
        {/* ── Header ── */}
        <DialogHeader className="flex flex-row items-start justify-between border-b border-slate-100 px-6 pb-4 pt-5">
          <div className="flex-1">
            <DialogTitle className="text-base font-semibold text-slate-900">
              Suggest post assignments
            </DialogTitle>
            <p className="mt-0.5 text-xs text-slate-500">
              {preview
                ? `${totalCount} posts reviewed · matching against post conditions`
                : "Generating suggestions…"}
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => previewMutation.mutate()}
            disabled={previewMutation.isPending}
            className="ml-4 shrink-0 text-xs"
          >
            <RefreshCw
              className={cn(
                "mr-1.5 h-3.5 w-3.5",
                previewMutation.isPending && "animate-spin"
              )}
              aria-hidden="true"
            />
            Regenerate
          </Button>
        </DialogHeader>

        {/* ── Error banner ── */}
        {errorMessage && (
          <div className="border-b border-red-100 bg-red-50 px-6 py-2 text-sm text-red-700">
            {errorMessage}
          </div>
        )}

        {/* ── Loading state ── */}
        {isLoading && <StateLoading />}

        {/* ── Stale-conflict sub-state (replaces table region) ── */}
        {!isLoading && staleEntries && staleEntries.length > 0 && preview && (
          <StateStaleConflict
            staleEntries={staleEntries}
            preview={preview}
            checked={checked}
            onClose={handleClose}
            onRegenerate={() => previewMutation.mutate()}
            onApplyRemaining={(ids) => handleApply(ids)}
            applyPending={applyMutation.isPending}
          />
        )}

        {/* ── Normal preview (filter tiles + table + footer) ── */}
        {!isLoading && !staleEntries && preview && (
          <>
            {/* Empty state */}
            {preview.assignments.length === 0 && (
              <StateEmpty onClose={handleClose} />
            )}

            {/* Populated state */}
            {preview.assignments.length > 0 && (
              <>
                {/* Filter tiles */}
                <div className="grid grid-cols-5 gap-2 border-b border-slate-100 bg-slate-50 px-6 py-4">
                  {TILE_CONFIG.map((cfg) => (
                    <SummaryTile
                      key={cfg.key}
                      config={cfg}
                      count={tileCountMap[cfg.key]}
                      selectedCount={tileSelectedMap[cfg.key]}
                      active={filter === cfg.key}
                      onClick={() => setFilter(cfg.key)}
                    />
                  ))}
                </div>

                {/* Diff table */}
                <div className="flex-1 overflow-y-auto">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 z-10 bg-white text-xs uppercase tracking-wide text-slate-400">
                      <tr className="border-b border-slate-100">
                        <th className="w-10 py-2 pl-6 text-left font-medium" />
                        <th className="w-16 py-2 text-left font-medium">
                          Post
                        </th>
                        <th className="w-20 py-2 text-left font-medium">
                          Priority
                        </th>
                        <th className="py-2 text-left font-medium">
                          Member change
                        </th>
                        <th className="py-2 pr-6 text-left font-medium">
                          Matched post condition
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredSorted.map((entry) => {
                        const cls = classify(entry);
                        const skipped = cls === "skipped";
                        const isChecked = !skipped && !!checked[entry.position_id];
                        const prio = getPriorityMeta(entry.priority);
                        return (
                          <tr
                            key={entry.position_id}
                            className={cn(
                              "border-b border-slate-100 last:border-0",
                              skipped
                                ? "opacity-60"
                                : "hover:bg-slate-50",
                              isChecked && "bg-violet-50/40"
                            )}
                          >
                            {/* Checkbox */}
                            <td className="py-1.5 pl-6">
                              <input
                                type="checkbox"
                                checked={isChecked}
                                disabled={skipped || cls === "same"}
                                onChange={() =>
                                  !skipped &&
                                  cls !== "same" &&
                                  toggleCheck(entry.position_id)
                                }
                                className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-400 disabled:cursor-not-allowed disabled:opacity-50"
                              />
                            </td>

                            {/* Post # */}
                            <td className="py-1.5">
                              <span className="font-medium text-slate-900 tabular-nums">
                                #{entry.building_number}
                              </span>
                            </td>

                            {/* Priority badge */}
                            <td className="py-1.5">
                              <span
                                className={cn(
                                  "inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-semibold ring-1 ring-inset",
                                  prio.pill
                                )}
                              >
                                {prio.label}
                              </span>
                            </td>

                            {/* Member change */}
                            <td className="py-1.5">
                              <ChangeCell entry={entry} />
                            </td>

                            {/* Matched condition / skip reason */}
                            <td className="py-1.5 pr-6">
                              <ConditionCell entry={entry} skipped={skipped} />
                            </td>
                          </tr>
                        );
                      })}

                      {filteredSorted.length === 0 && (
                        <tr>
                          <td
                            colSpan={5}
                            className="py-12 text-center text-sm text-slate-400"
                          >
                            No posts match this filter.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                {/* ── Sticky footer ── */}
                <div className="flex items-center justify-between gap-4 border-t border-slate-100 bg-slate-50 px-6 py-3">
                  <p className="text-sm text-slate-600">
                    {totalSelected === 0 ? (
                      <span className="text-slate-400">Nothing selected.</span>
                    ) : (
                      <>
                        Apply{" "}
                        <span className="font-semibold text-slate-900">
                          {totalSelected}
                        </span>{" "}
                        change{totalSelected === 1 ? "" : "s"} —{" "}
                        <span className="text-violet-700">
                          {selectedNew} new
                        </span>{" "}
                        ·{" "}
                        <span className="text-amber-700">
                          {selectedReplace} replacement
                          {selectedReplace === 1 ? "" : "s"}
                        </span>
                      </>
                    )}
                  </p>
                  <div className="flex items-center gap-2">
                    <Button variant="ghost" onClick={handleClose}>
                      Cancel
                    </Button>
                    <Button
                      onClick={() => handleApply()}
                      disabled={
                        totalSelected === 0 || applyMutation.isPending
                      }
                      className={cn(
                        totalSelected === 0 && "opacity-40"
                      )}
                    >
                      {applyMutation.isPending
                        ? "Applying…"
                        : `Apply ${totalSelected > 0 ? totalSelected : ""}`}
                    </Button>
                  </div>
                </div>
              </>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
