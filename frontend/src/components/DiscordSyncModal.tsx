import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { previewDiscordSync, applyDiscordSync } from "../api/members";
import type { SyncMatch, SyncApplyItem } from "../api/types";
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

interface Props {
  open: boolean;
  onClose: () => void;
  onApplied: () => void;
}

type ConfidenceVariant = "green" | "yellow" | "red";

const CONFIDENCE_VARIANT: Record<SyncMatch["confidence"], ConfidenceVariant> = {
  exact: "green",
  suggested: "yellow",
  ambiguous: "red",
};

const CONFIDENCE_LABEL: Record<SyncMatch["confidence"], string> = {
  exact: "Exact",
  suggested: "Suggested",
  ambiguous: "Ambiguous",
};

export default function DiscordSyncModal({ open, onClose, onApplied }: Props) {
  // null = not yet previewed; [] = previewed but empty
  const [preview, setPreview] = useState<{
    matches: SyncMatch[];
    unmatched_guild_members: string[];
    unmatched_clan_members: string[];
  } | null>(null);

  // Track which match rows are checked for apply. Keyed by member_id.
  const [checked, setChecked] = useState<Record<number, boolean>>({});

  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const previewMutation = useMutation({
    mutationFn: previewDiscordSync,
    onSuccess: (data) => {
      setPreview(data);
      setSuccessMessage(null);
      setErrorMessage(null);
      // Default: check exact and suggested; leave ambiguous unchecked.
      const initial: Record<number, boolean> = {};
      for (const m of data.matches) {
        initial[m.member_id] = m.confidence !== "ambiguous";
      }
      setChecked(initial);
    },
    onError: () => {
      setErrorMessage("Failed to fetch sync preview. Is the bot reachable?");
    },
  });

  const applyMutation = useMutation({
    mutationFn: (items: SyncApplyItem[]) => applyDiscordSync(items),
    onSuccess: (data) => {
      setSuccessMessage(
        `Updated ${data.updated} member${data.updated !== 1 ? "s" : ""}.`
      );
      setErrorMessage(null);
      onApplied();
    },
    onError: () => {
      setErrorMessage("Failed to apply sync changes.");
    },
  });

  function handleClose() {
    setPreview(null);
    setChecked({});
    setSuccessMessage(null);
    setErrorMessage(null);
    onClose();
  }

  function toggleCheck(memberId: number) {
    setChecked((prev) => ({ ...prev, [memberId]: !prev[memberId] }));
  }

  function handleApply() {
    if (!preview) return;
    const selected: SyncApplyItem[] = preview.matches
      .filter((m) => checked[m.member_id])
      .map((m) => ({
        member_id: m.member_id,
        discord_username: m.proposed_discord_username,
        discord_id: m.proposed_discord_id,
      }));
    applyMutation.mutate(selected);
  }

  const selectedCount = Object.values(checked).filter(Boolean).length;

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!v) handleClose();
      }}
    >
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Sync Discord Usernames</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Actions row */}
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              onClick={() => previewMutation.mutate()}
              disabled={previewMutation.isPending}
            >
              <RefreshCw
                className={`h-4 w-4 ${previewMutation.isPending ? "animate-spin" : ""}`}
              />
              {previewMutation.isPending ? "Loading..." : "Fetch Preview"}
            </Button>
            {preview && (
              <span className="text-sm text-slate-500">
                {preview.matches.length} match
                {preview.matches.length !== 1 ? "es" : ""} found
              </span>
            )}
          </div>

          {/* Error/success banners */}
          {errorMessage && (
            <div className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-700">
              {errorMessage}
            </div>
          )}
          {successMessage && (
            <div className="rounded-md bg-green-50 px-4 py-2 text-sm text-green-700">
              {successMessage}
            </div>
          )}

          {/* Match table */}
          {preview && preview.matches.length > 0 && (
            <div className="max-h-96 overflow-y-auto rounded-lg border border-slate-200">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-8"></TableHead>
                    <TableHead>Clan Member</TableHead>
                    <TableHead>Current Discord</TableHead>
                    <TableHead>Proposed Discord</TableHead>
                    <TableHead>Confidence</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {preview.matches.map((m) => (
                    <TableRow key={m.member_id}>
                      <TableCell>
                        <Checkbox
                          checked={!!checked[m.member_id]}
                          onCheckedChange={() => toggleCheck(m.member_id)}
                        />
                      </TableCell>
                      <TableCell className="font-medium">
                        {m.member_name}
                      </TableCell>
                      <TableCell className="text-slate-500">
                        {m.current_discord_username ?? (
                          <span className="italic text-slate-400">none</span>
                        )}
                      </TableCell>
                      <TableCell>{m.proposed_discord_username}</TableCell>
                      <TableCell>
                        <Badge variant={CONFIDENCE_VARIANT[m.confidence]}>
                          {CONFIDENCE_LABEL[m.confidence]}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}

          {preview && preview.matches.length === 0 && (
            <p className="text-sm text-slate-500">No matches found.</p>
          )}

          {/* Unmatched counts */}
          {preview &&
            (preview.unmatched_guild_members.length > 0 ||
              preview.unmatched_clan_members.length > 0) && (
              <div className="space-y-1 rounded-md bg-slate-50 px-4 py-3 text-sm text-slate-600">
                {preview.unmatched_guild_members.length > 0 && (
                  <div>
                    <span className="font-medium">
                      {preview.unmatched_guild_members.length}
                    </span>{" "}
                    guild member
                    {preview.unmatched_guild_members.length !== 1
                      ? "s"
                      : ""}{" "}
                    not matched to any clan member
                  </div>
                )}
                {preview.unmatched_clan_members.length > 0 && (
                  <div>
                    <span className="font-medium">
                      {preview.unmatched_clan_members.length}
                    </span>{" "}
                    clan member
                    {preview.unmatched_clan_members.length !== 1 ? "s" : ""} not
                    matched to any guild member
                  </div>
                )}
              </div>
            )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>
            Close
          </Button>
          {preview && preview.matches.length > 0 && (
            <Button
              onClick={handleApply}
              disabled={selectedCount === 0 || applyMutation.isPending}
            >
              {applyMutation.isPending
                ? "Applying..."
                : `Apply Selected (${selectedCount})`}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
