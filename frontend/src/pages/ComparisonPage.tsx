import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getSieges, compareSieges, compareSiegesSpecific } from "../api/sieges";
import type { PositionKey, MemberDiff } from "../api/types";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { Label } from "../components/ui/label";
import { ArrowLeft } from "lucide-react";
import { cn } from "../lib/utils";

function formatPosition(pos: PositionKey): string {
  return `${pos.building_type.replace(/_/g, " ")} #${pos.building_number} G${pos.group_number} P${pos.position_number}`;
}

interface PositionTagProps {
  pos: PositionKey;
  variant: "added" | "removed" | "unchanged";
}

function PositionTag({ pos, variant }: PositionTagProps) {
  return (
    <span
      className={cn(
        "inline-block rounded px-1.5 py-0.5 text-xs font-medium capitalize",
        variant === "added" && "bg-green-100 text-green-800",
        variant === "removed" && "bg-red-100 text-red-800",
        variant === "unchanged" && "bg-slate-100 text-slate-600"
      )}
    >
      {formatPosition(pos)}
    </span>
  );
}

function MemberPositionsCell({ diff }: { diff: MemberDiff }) {
  return (
    <div className="flex flex-col gap-1">
      {diff.removed.map((pos, i) => (
        <PositionTag key={`removed-${i}`} pos={pos} variant="removed" />
      ))}
      {diff.unchanged.map((pos, i) => (
        <PositionTag key={`unchanged-${i}`} pos={pos} variant="unchanged" />
      ))}
    </div>
  );
}

function MemberNewPositionsCell({ diff }: { diff: MemberDiff }) {
  return (
    <div className="flex flex-col gap-1">
      {diff.added.map((pos, i) => (
        <PositionTag key={`added-${i}`} pos={pos} variant="added" />
      ))}
      {diff.unchanged.map((pos, i) => (
        <PositionTag key={`unchanged-${i}`} pos={pos} variant="unchanged" />
      ))}
    </div>
  );
}

export default function ComparisonPage() {
  const { id } = useParams<{ id: string }>();
  const siegeId = Number(id);
  const [compareToId, setCompareToId] = useState<string>("default");
  const [diffsOnly, setDiffsOnly] = useState(false);

  const { data: completedSieges } = useQuery({
    queryKey: ["sieges", "complete"],
    queryFn: () => getSieges({ status: "complete" }),
  });

  const otherSieges = completedSieges?.filter((s) => s.id !== siegeId) ?? [];

  const isSpecific = compareToId !== "default";
  const specificId = isSpecific ? Number(compareToId) : undefined;

  const {
    data: comparison,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["comparison", siegeId, compareToId],
    queryFn: () =>
      isSpecific && specificId != null
        ? compareSiegesSpecific(siegeId, specificId)
        : compareSieges(siegeId),
    enabled: true,
  });

  const membersWithChanges =
    comparison?.members.filter(
      (m) => m.added.length > 0 || m.removed.length > 0
    ) ?? [];
  const totalAdded =
    comparison?.members.reduce((acc, m) => acc + m.added.length, 0) ?? 0;
  const totalRemoved =
    comparison?.members.reduce((acc, m) => acc + m.removed.length, 0) ?? 0;
  const visibleMembers = diffsOnly
    ? membersWithChanges
    : (comparison?.members ?? []);

  return (
    <div className="max-w-5xl">
      <Link
        to="/sieges"
        className="mb-4 flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Sieges
      </Link>

      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Comparison</h1>
      </div>

      {/* Siege selector */}
      <div className="mb-6 rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex items-end gap-4">
          <div className="space-y-1.5">
            <Label>Compare against</Label>
            <Select value={compareToId} onValueChange={setCompareToId}>
              <SelectTrigger className="w-56">
                <SelectValue placeholder="Most recent completed" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="default">Most recent completed</SelectItem>
                {otherSieges.map((s) => (
                  <SelectItem key={s.id} value={String(s.id)}>
                    {s.date ? `Siege ${s.date}` : `Siege #${s.id}`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {comparison && (
            <p className="mb-1 text-sm text-slate-500">
              Siege #{comparison.siege_a_id} vs Siege #{comparison.siege_b_id}
            </p>
          )}
        </div>
      </div>

      {/* Summary */}
      {comparison && (
        <div className="mb-4 flex items-center justify-between rounded-md border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
          <span>
            <strong>{membersWithChanges.length}</strong> members with changes
            &bull;{" "}
            <span className="text-green-700">
              <strong>{totalAdded}</strong> positions added
            </span>{" "}
            &bull;{" "}
            <span className="text-red-700">
              <strong>{totalRemoved}</strong> positions removed
            </span>
          </span>
          <label className="flex cursor-pointer select-none items-center gap-2">
            <input
              type="checkbox"
              checked={diffsOnly}
              onChange={(e) => setDiffsOnly(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300 accent-slate-700"
            />
            Show diffs only
          </label>
        </div>
      )}

      {/* Loading / error */}
      {isLoading && (
        <div className="py-12 text-center text-slate-500">
          Loading comparison...
        </div>
      )}
      {error && (
        <div className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">
          Failed to load comparison. The siege may not have a previous completed
          siege to compare against.
        </div>
      )}

      {/* Table */}
      {comparison && (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="px-4 py-3 text-left font-semibold text-slate-700">
                  Member
                </th>
                <th className="px-4 py-3 text-left font-semibold text-slate-700">
                  Old Positions (Siege #{comparison.siege_a_id})
                </th>
                <th className="px-4 py-3 text-left font-semibold text-slate-700">
                  New Positions (Siege #{comparison.siege_b_id})
                </th>
              </tr>
            </thead>
            <tbody>
              {visibleMembers.length === 0 && (
                <tr>
                  <td
                    colSpan={3}
                    className="px-4 py-8 text-center text-slate-500"
                  >
                    {diffsOnly
                      ? "No members with changes."
                      : "No members to compare."}
                  </td>
                </tr>
              )}
              {visibleMembers.map((diff) => (
                <tr
                  key={diff.member_id}
                  className={cn(
                    "border-b border-slate-100 last:border-0",
                    (diff.added.length > 0 || diff.removed.length > 0) &&
                      "bg-amber-50/40"
                  )}
                >
                  <td className="px-4 py-3 font-medium text-slate-900">
                    {diff.member_name}
                  </td>
                  <td className="px-4 py-3">
                    <MemberPositionsCell diff={diff} />
                  </td>
                  <td className="px-4 py-3">
                    <MemberNewPositionsCell diff={diff} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Legend */}
      <div className="mt-4 flex gap-4 text-xs text-slate-500">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-3 w-3 rounded bg-green-100" />
          Added
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-3 w-3 rounded bg-red-100" />
          Removed
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-3 w-3 rounded bg-slate-100" />
          Unchanged
        </span>
      </div>
    </div>
  );
}
