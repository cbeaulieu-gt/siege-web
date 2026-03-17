import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import {
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
import { Badge } from '../components/ui/badge';
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
import { ArrowLeft, Lock } from 'lucide-react';

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

function SiegeMemberRow({ member, siegeId }: { member: SiegeMember; siegeId: number }) {
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
          <AttackDaySelect
            value={member.attack_day}
            onChange={(v) => mutation.mutate({ attack_day: v })}
          />
          {member.attack_day_override && (
            <Lock className="h-3.5 w-3.5 text-slate-500" aria-label="Pinned" />
          )}
        </div>
      </TableCell>
      <TableCell>
        <Checkbox
          checked={Boolean(member.attack_day_override)}
          onCheckedChange={(v) => mutation.mutate({ attack_day_override: Boolean(v) })}
        />
      </TableCell>
      <TableCell>
        <Checkbox
          checked={Boolean(member.has_reserve_set)}
          onCheckedChange={(v) =>
            mutation.mutate({ has_reserve_set: Boolean(v) })
          }
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
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            to={`/sieges/${siegeId}`}
            className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </Link>
          <h1 className="text-2xl font-bold text-slate-900">Members — Siege #{siegeId}</h1>
        </div>
        <Button
          size="sm"
          onClick={() => previewMutation.mutate()}
          disabled={previewMutation.isPending}
        >
          {previewMutation.isPending ? 'Loading...' : 'Auto-Assign Attack Days'}
        </Button>
      </div>

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
                <SiegeMemberRow key={m.member_id} member={m} siegeId={siegeId} />
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
          <div className="space-y-1">
            {preview?.assignments.map((a) => (
              <div
                key={a.member_id}
                className="flex items-center justify-between rounded-sm px-2 py-1 hover:bg-slate-50"
              >
                <span className="text-sm">{nameLookup[a.member_id] ?? `Member ${a.member_id}`}</span>
                <Badge variant={a.attack_day === 1 ? 'blue' : 'orange'}>
                  Day {a.attack_day}
                </Badge>
              </div>
            ))}
          </div>
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
