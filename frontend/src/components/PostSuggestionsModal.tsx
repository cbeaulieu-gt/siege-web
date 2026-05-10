import { useState, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
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
  DialogFooter,
} from "./ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "./ui/table";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Checkbox } from "./ui/checkbox";
import { priorityLabel, priorityBadgeColor } from "../lib/post-priority";

interface Props {
  open: boolean;
  onClose: () => void;
  siegeId: number;
}

const SKIP_REASON_LABEL: Record<
  NonNullable<PostSuggestionEntry["skip_reason"]>,
  string
> = {
  no_match: "No match found",
  reserve: "Position is in reserve mode",
  disabled: "Position is disabled",
};

const STALE_REASON_LABEL: Record<PostSuggestionStaleEntry["reason"], string> = {
  position_missing: "position was removed",
  position_disabled: "position was disabled",
  position_reserve: "position was set to reserve",
  member_inactive: "member became inactive",
  member_changed: "another planner assigned a different member",
};

export default function PostSuggestionsModal({
  open,
  onClose,
  siegeId,
}: Props) {
  const queryClient = useQueryClient();

  const [preview, setPreview] = useState<PostSuggestionPreviewResult | null>(
    null
  );
  // Keyed by position_id; true = include in apply payload
  const [checked, setChecked] = useState<Record<number, boolean>>({});
  const [staleEntries, setStaleEntries] = useState<
    PostSuggestionStaleEntry[] | null
  >(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const previewMutation = useMutation({
    mutationFn: () => previewPostSuggestions(siegeId),
    onSuccess: (data) => {
      setPreview(data);
      setStaleEntries(null);
      setErrorMessage(null);
      // Default: check all rows that have a suggestion
      const initial: Record<number, boolean> = {};
      for (const entry of data.assignments) {
        initial[entry.position_id] = entry.suggested_member_id !== null;
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
      // Invalidate board and posts queries so UI reflects new assignments
      queryClient.invalidateQueries({ queryKey: ["board", siegeId] });
      queryClient.invalidateQueries({ queryKey: ["posts", siegeId] });
      handleClose();
    },
    onError: (err: unknown) => {
      // Check for structured 409 stale_entries response
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
    onClose();
  }

  // Auto-fire preview when the dialog opens (open prop transitions to true).
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

  function handleApply() {
    if (!preview) return;
    const selectedIds = preview.assignments
      .filter((e) => e.suggested_member_id !== null && checked[e.position_id])
      .map((e) => e.position_id);
    applyMutation.mutate(selectedIds);
  }

  function handleRegeneratePreview() {
    previewMutation.mutate();
  }

  // Build a lookup from position_id → stale reason for inline row highlighting
  const staleByPositionId: Record<number, PostSuggestionStaleEntry> = {};
  if (staleEntries) {
    for (const entry of staleEntries) {
      staleByPositionId[entry.position_id] = entry;
    }
  }

  const selectedCount = preview
    ? preview.assignments.filter(
        (e) => e.suggested_member_id !== null && checked[e.position_id]
      ).length
    : 0;

  return (
    <Dialog open={open} onOpenChange={handleOpen}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle>Suggest Post Assignments</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Error banner */}
          {errorMessage && (
            <div className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-700">
              {errorMessage}
            </div>
          )}

          {/* Stale-entries banner (409 response) */}
          {staleEntries && staleEntries.length > 0 && (
            <div className="space-y-2 rounded-md border border-amber-200 bg-amber-50 px-4 py-3">
              <p className="text-sm font-medium text-amber-800">
                Some positions changed since the preview was generated:
              </p>
              <ul className="list-inside list-disc space-y-1 text-sm text-amber-700">
                {staleEntries.map((se) => {
                  const entry = preview?.assignments.find(
                    (a) => a.position_id === se.position_id
                  );
                  const label = entry
                    ? `Post ${entry.building_number}`
                    : `Position ${se.position_id}`;
                  return (
                    <li key={se.position_id}>
                      {label} — {STALE_REASON_LABEL[se.reason]}
                    </li>
                  );
                })}
              </ul>
              <Button
                variant="outline"
                size="sm"
                onClick={handleRegeneratePreview}
                disabled={previewMutation.isPending}
                className="mt-2"
              >
                <RefreshCw
                  className={`mr-2 h-4 w-4 ${previewMutation.isPending ? "animate-spin" : ""}`}
                />
                Regenerate preview
              </Button>
            </div>
          )}

          {/* Loading state */}
          {previewMutation.isPending && !preview && (
            <p className="text-sm text-slate-500">Generating suggestions…</p>
          )}

          {/* Assignment table — sorted by post number for stable scan order */}
          {preview && preview.assignments.length > 0 && (
            <div className="max-h-[28rem] overflow-y-auto rounded-lg border border-slate-200">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-8"></TableHead>
                    <TableHead>Post #</TableHead>
                    <TableHead>Priority</TableHead>
                    <TableHead>Current</TableHead>
                    <TableHead>Suggested</TableHead>
                    <TableHead></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {[...preview.assignments]
                    .sort((a, b) => a.building_number - b.building_number)
                    .map((entry) => {
                      const isSkipped = entry.suggested_member_id === null;
                      const isStale = !!staleByPositionId[entry.position_id];
                      // Row tint:
                      //   stale (post-409)        → amber
                      //   suggestion = current    → muted slate (no change)
                      //   suggestion ≠ current    → emerald (new assignment)
                      //   skipped                 → default
                      let rowClass: string | undefined;
                      if (isStale) {
                        rowClass = "bg-amber-50";
                      } else if (isSkipped) {
                        rowClass = undefined;
                      } else if (entry.matches_current) {
                        rowClass = "bg-slate-50 text-slate-500";
                      } else {
                        rowClass = "bg-emerald-50";
                      }
                      return (
                        <TableRow key={entry.position_id} className={rowClass}>
                          <TableCell>
                            <Checkbox
                              checked={
                                !isSkipped && !!checked[entry.position_id]
                              }
                              disabled={isSkipped}
                              onCheckedChange={() =>
                                !isSkipped && toggleCheck(entry.position_id)
                              }
                            />
                          </TableCell>

                          <TableCell className="font-medium">
                            {entry.building_number}
                          </TableCell>

                          <TableCell>
                            <span
                              className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium ${priorityBadgeColor(entry.priority)}`}
                            >
                              {priorityLabel(entry.priority)}
                            </span>
                          </TableCell>

                          {/* Current cell: member name on top, condition smaller below */}
                          <TableCell className="text-sm">
                            {entry.current_member_name ? (
                              <div className="leading-tight">
                                <div className="text-slate-700">
                                  {entry.current_member_name}
                                </div>
                                {entry.current_condition_description && (
                                  <div className="text-xs text-slate-400">
                                    {entry.current_condition_description}
                                  </div>
                                )}
                              </div>
                            ) : (
                              <span className="italic text-slate-400">—</span>
                            )}
                          </TableCell>

                          {/* Suggested cell: same vertical stack, or skip reason */}
                          <TableCell className="text-sm">
                            {isSkipped ? (
                              <span className="italic text-slate-400">
                                {SKIP_REASON_LABEL[entry.skip_reason!]}
                              </span>
                            ) : (
                              <div className="leading-tight">
                                <div className="font-medium text-slate-800">
                                  {entry.suggested_member_name}
                                </div>
                                {entry.suggested_condition_description && (
                                  <div className="text-xs text-slate-500">
                                    {entry.suggested_condition_description}
                                  </div>
                                )}
                              </div>
                            )}
                          </TableCell>

                          <TableCell>
                            {isStale && (
                              <Badge variant="yellow" className="text-xs">
                                stale
                              </Badge>
                            )}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                </TableBody>
              </Table>
            </div>
          )}

          {preview && preview.assignments.length === 0 && (
            <p className="text-sm text-slate-500">
              No posts found on this siege.
            </p>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>
            Cancel
          </Button>
          {preview && preview.assignments.length > 0 && (
            <Button
              onClick={handleApply}
              disabled={selectedCount === 0 || applyMutation.isPending}
            >
              {applyMutation.isPending
                ? "Applying…"
                : `Apply Selected (${selectedCount})`}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
