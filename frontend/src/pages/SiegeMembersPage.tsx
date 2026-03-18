import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import {
  getSiege,
  getSiegeMembers,
  updateSiegeMember,
  previewAttackDay,
  applyAttackDay,
} from '../api/sieges';
import type { SiegeMember, AttackDayPreviewResult } from '../api/types';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import { Button } from '../components/ui/button';
import { Checkbox } from '../components/ui/checkbox';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '../components/ui/dialog';
import { ArrowLeft, Lock, LayoutGrid, MessageSquare, Users, GitCompare, Settings } from 'lucide-react';

function AttackDaySelect({
  value,
  onChange,
}: {
  value: number | null;
  onChange: (v: number | null) => void;
}) {
  return (
    <Select
      value={value != null ? String(value) : 'none'}
      onValueChange={(v) => onChange(v === 'none' ? null : Number(v))}
    >
      <SelectTrigger className="h-7 w-20 text-xs">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="none">-</SelectItem>
        <SelectItem value="1">Day 1</SelectItem>
        <SelectItem value="2">Day 2</SelectItem>
      </SelectContent>
    </Select>
  );
}

function SiegeMemberRow({ member, siegeId, isLocked }: { member: SiegeMember; siegeId: number; isLocked?: boolean }) {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (data: {
      attack_day?: number | null;
      has_reserve_set?: boolean | null;
      attack_day_override?: boolean;
    }) => updateSiegeMember(siegeId, member.member_id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['siegeMembers', siegeId] });
    },
  });

  return (
    <TableRow>
      <TableCell className="font-medium">{member.member_name}</TableCell>
      <TableCell>
        <div className="flex items-center gap-1.5">
          {isLocked ? (
            <span className="text-sm text-slate-600">
              {member.attack_day ? `Day ${member.attack_day}` : '-'}
            </span>
          ) : (
            <AttackDaySelect
              value={member.attack_day}
              onChange={(v) => mutation.mutate({ attack_day: v })}
            />
          )}
          {member.attack_day_override && (
            <Lock className="h-3.5 w-3.5 text-slate-500" aria-label="Pinned" />
          )}
        </div>
      </TableCell>
      <TableCell>
        <Checkbox
          checked={Boolean(member.attack_day_override)}
          disabled={isLocked}
          onCheckedChange={isLocked ? undefined : (v) => mutation.mutate({ attack_day_override: Boolean(v) })}
        />
      </TableCell>
      <TableCell>
        <Checkbox
          checked={Boolean(member.has_reserve_set)}
          disabled={isLocked}
          onCheckedChange={isLocked ? undefined : (v) => mutation.mutate({ has_reserve_set: Boolean(v) })}
        />
      </TableCell>
    </TableRow>
  );
}

export default function SiegeMembersPage() {
  const { id } = useParams<{ id: string }>();
  const siegeId = Number(id);
  const queryClient = useQueryClient();
  const [previewOpen, setPreviewOpen] = useState(false);
  const [preview, setPreview] = useState<AttackDayPreviewResult | null>(null);

  const { data: siege } = useQuery({
    queryKey: ['siege', siegeId],
    queryFn: () => getSiege(siegeId),
  });

  const { data: members, isLoading, error } = useQuery({
    queryKey: ['siegeMembers', siegeId],
    queryFn: () => getSiegeMembers(siegeId),
  });

  const previewMutation = useMutation({
    mutationFn: () => previewAttackDay(siegeId),
    onSuccess: (data) => {
      setPreview(data);
      setPreviewOpen(true);
    },
  });

  const applyMutation = useMutation({
    mutationFn: () => applyAttackDay(siegeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['siegeMembers', siegeId] });
      setPreviewOpen(false);
      setPreview(null);
    },
  });

  // Build a quick name lookup for the preview dialog
  const nameLookup: Record<number, string> = {};
  for (const m of members ?? []) {
    nameLookup[m.member_id] = m.member_name;
  }

  return (
    <div>
      <div className="mb-6 flex items-start justify-between">
        <div>
          <Link
            to="/sieges"
            className="mb-2 flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Sieges
          </Link>
          <h1 className="text-2xl font-bold text-slate-900">
            Members — Siege {siege?.date ?? `#${siegeId}`}
          </h1>
        </div>
        <div className="flex flex-col items-end gap-2">
          <div className="flex gap-2 text-sm">
            <Link
              to={`/sieges/${siegeId}/board`}
              className="flex items-center gap-1 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-slate-700 hover:bg-slate-50"
            >
              <LayoutGrid className="h-4 w-4" />
              Board
            </Link>
            <Link
              to={`/sieges/${siegeId}/posts`}
              className="flex items-center gap-1 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-slate-700 hover:bg-slate-50"
            >
              <MessageSquare className="h-4 w-4" />
              Posts
            </Link>
            <span className="flex items-center gap-1 rounded-md border border-slate-300 bg-slate-100 px-3 py-1.5 text-slate-700 font-medium">
              <Users className="h-4 w-4" />
              Members
            </span>
            <Link
              to={`/sieges/${siegeId}/compare`}
              className="flex items-center gap-1 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-slate-700 hover:bg-slate-50"
            >
              <GitCompare className="h-4 w-4" />
              Compare
            </Link>
            <Link
              to={`/sieges/${siegeId}`}
              className="flex items-center gap-1 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-slate-700 hover:bg-slate-50"
            >
              <Settings className="h-4 w-4" />
              Settings
            </Link>
          </div>
          <Button
            size="sm"
            onClick={() => previewMutation.mutate()}
            disabled={previewMutation.isPending || siege?.status === 'complete'}
          >
            {previewMutation.isPending ? 'Loading...' : 'Auto-Assign Attack Days'}
          </Button>
        </div>
      </div>

      {siege?.status === 'complete' && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-800">
          <Lock className="h-4 w-4 shrink-0" />
          This siege is closed. Assignments are read-only.
        </div>
      )}

      {error && (
        <div className="mb-4 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">
          Failed to load members.
        </div>
      )}

      {isLoading ? (
        <div className="py-12 text-center text-slate-500">Loading...</div>
      ) : (
        <div className="rounded-lg border border-slate-200 bg-white">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Attack Day</TableHead>
                <TableHead>Override (Pinned)</TableHead>
                <TableHead>Reserve Set</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {members?.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="py-8 text-center text-slate-500">
                    No members in this siege.
                  </TableCell>
                </TableRow>
              )}
              {members?.map((m) => (
                <SiegeMemberRow key={m.member_id} member={m} siegeId={siegeId} isLocked={siege?.status === 'complete'} />
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Attack Day Preview Dialog */}
      <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
        <DialogContent className="max-h-[80vh] max-w-md overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Attack Day Preview</DialogTitle>
            <DialogDescription>
              {preview?.assignments.length ?? 0} members will be assigned.
            </DialogDescription>
          </DialogHeader>
          {preview && (() => {
            const day1 = preview.assignments.filter((a) => a.attack_day === 1);
            const day2 = preview.assignments.filter((a) => a.attack_day === 2);
            const rows = Math.max(day1.length, day2.length);
            return (
              <div className="grid grid-cols-2 divide-x divide-slate-200 rounded-md border border-slate-200">
                <div>
                  <div className="border-b border-slate-200 px-3 py-2 text-center text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Day 1 ({day1.length})
                  </div>
                  {Array.from({ length: rows }).map((_, i) => (
                    <div
                      key={i}
                      className="px-3 py-1.5 text-sm odd:bg-slate-50"
                    >
                      {day1[i] ? (nameLookup[day1[i].member_id] ?? `Member ${day1[i].member_id}`) : ''}
                    </div>
                  ))}
                </div>
                <div>
                  <div className="border-b border-slate-200 px-3 py-2 text-center text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Day 2 ({day2.length})
                  </div>
                  {Array.from({ length: rows }).map((_, i) => (
                    <div
                      key={i}
                      className="px-3 py-1.5 text-sm odd:bg-slate-50"
                    >
                      {day2[i] ? (nameLookup[day2[i].member_id] ?? `Member ${day2[i].member_id}`) : ''}
                    </div>
                  ))}
                </div>
              </div>
            );
          })()}
          <DialogFooter>
            <Button variant="outline" onClick={() => setPreviewOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => applyMutation.mutate()} disabled={applyMutation.isPending}>
              {applyMutation.isPending ? 'Applying...' : 'Apply'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
