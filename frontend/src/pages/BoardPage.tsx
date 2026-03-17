import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getBoard, updatePosition } from '../api/board';
import { getSiege, getSiegeMembers, previewAutofill, applyAutofill, validateSiege } from '../api/sieges';
import type {
  BuildingType,
  BuildingResponse,
  PositionResponse,
  SiegeMember,
  AutofillPreviewResult,
  ValidationResult,
} from '../api/types';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '../components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { ArrowLeft, ChevronDown } from 'lucide-react';

type BuildingColorClass = {
  header: string;
  border: string;
  bg: string;
};

const BUILDING_COLORS: Record<BuildingType, BuildingColorClass> = {
  stronghold: { header: 'bg-violet-600', border: 'border-violet-200', bg: 'bg-violet-50' },
  mana_shrine: { header: 'bg-blue-600', border: 'border-blue-200', bg: 'bg-blue-50' },
  magic_tower: { header: 'bg-orange-600', border: 'border-orange-200', bg: 'bg-orange-50' },
  defense_tower: { header: 'bg-green-600', border: 'border-green-200', bg: 'bg-green-50' },
  post: { header: 'bg-red-600', border: 'border-red-200', bg: 'bg-red-50' },
};

const BUILDING_LABELS: Record<BuildingType, string> = {
  stronghold: 'Stronghold',
  mana_shrine: 'Mana Shrine',
  magic_tower: 'Magic Tower',
  defense_tower: 'Defense Tower',
  post: 'Post',
};

function PositionCell({
  position,
  siegeId,
  siegeMembers,
  onUpdate,
}: {
  position: PositionResponse;
  siegeId: number;
  siegeMembers: SiegeMember[];
  onUpdate: () => void;
}) {
  const queryClient = useQueryClient();
  const [menuOpen, setMenuOpen] = useState(false);
  const [assignOpen, setAssignOpen] = useState(false);
  const [selectedMemberId, setSelectedMemberId] = useState<string>('');

  const mutation = useMutation({
    mutationFn: (data: {
      member_id?: number | null;
      is_reserve?: boolean;
      has_no_assignment?: boolean;
    }) => updatePosition(siegeId, position.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['board', siegeId] });
      onUpdate();
      setMenuOpen(false);
      setAssignOpen(false);
    },
  });

  function handleAssign() {
    if (selectedMemberId) {
      mutation.mutate({
        member_id: Number(selectedMemberId),
        is_reserve: false,
        has_no_assignment: false,
      });
    }
  }

  function cellContent() {
    if (position.is_disabled) {
      return (
        <span className="text-xs text-slate-400 line-through">DISABLED</span>
      );
    }
    if (position.is_reserve) {
      return <Badge variant="yellow" className="text-xs">RESERVE</Badge>;
    }
    if (position.has_no_assignment) {
      return <span className="text-xs text-slate-400">N/A</span>;
    }
    if (position.member_id != null) {
      return (
        <span className="truncate text-xs font-medium text-slate-800">
          {position.member_name}
        </span>
      );
    }
    return <span className="text-xs text-slate-300">-</span>;
  }

  const isEmpty =
    !position.is_disabled &&
    !position.is_reserve &&
    !position.has_no_assignment &&
    position.member_id == null;

  const cellBg = position.is_disabled
    ? 'bg-slate-100'
    : position.member_id != null
      ? 'bg-white'
      : isEmpty
        ? 'bg-white border-dashed'
        : 'bg-white';

  return (
    <>
      <div
        className={`group relative flex min-h-[32px] items-center justify-between rounded border border-slate-200 px-2 py-1 ${cellBg}`}
      >
        <span className="mr-1 shrink-0 text-xs text-slate-400">{position.position_number}.</span>
        <div className="flex min-w-0 flex-1 items-center">{cellContent()}</div>
        {!position.is_disabled && (
          <button
            className="ml-1 shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
            onClick={() => setMenuOpen(true)}
          >
            <ChevronDown className="h-3 w-3 text-slate-400" />
          </button>
        )}
      </div>

      <Dialog open={menuOpen} onOpenChange={setMenuOpen}>
        <DialogContent className="max-w-xs">
          <DialogHeader>
            <DialogTitle>Position {position.position_number}</DialogTitle>
            <DialogDescription>
              {position.member_name ?? 'Unassigned'}
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setMenuOpen(false);
                setAssignOpen(true);
              }}
            >
              Assign Member
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => mutation.mutate({ is_reserve: true, has_no_assignment: false, member_id: null })}
              disabled={mutation.isPending}
            >
              Mark RESERVE
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => mutation.mutate({ has_no_assignment: true, is_reserve: false, member_id: null })}
              disabled={mutation.isPending}
            >
              Mark No Assignment
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => mutation.mutate({ member_id: null, is_reserve: false, has_no_assignment: false })}
              disabled={mutation.isPending}
            >
              Clear
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={assignOpen} onOpenChange={setAssignOpen}>
        <DialogContent className="max-w-xs">
          <DialogHeader>
            <DialogTitle>Assign Member</DialogTitle>
            <DialogDescription>
              Select a member for position {position.position_number}.
            </DialogDescription>
          </DialogHeader>
          <Select value={selectedMemberId} onValueChange={setSelectedMemberId}>
            <SelectTrigger>
              <SelectValue placeholder="Select member..." />
            </SelectTrigger>
            <SelectContent>
              {siegeMembers.map((m) => (
                <SelectItem key={m.member_id} value={String(m.member_id)}>
                  {m.member_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAssignOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleAssign}
              disabled={!selectedMemberId || mutation.isPending}
            >
              Assign
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function BuildingCard({
  building,
  siegeId,
  siegeMembers,
  onUpdate,
}: {
  building: BuildingResponse;
  siegeId: number;
  siegeMembers: SiegeMember[];
  onUpdate: () => void;
}) {
  const colors = BUILDING_COLORS[building.building_type];

  return (
    <div className={`rounded-lg border ${colors.border} overflow-hidden`}>
      <div className={`${colors.header} px-3 py-2 text-white`}>
        <p className="text-xs font-semibold uppercase tracking-wide">
          {BUILDING_LABELS[building.building_type]} {building.building_number}
        </p>
        <p className="text-xs opacity-75">
          Lvl {building.level}
          {building.is_broken ? ' · Broken' : ''}
        </p>
      </div>
      <div className={`${colors.bg} p-2 space-y-2`}>
        {building.groups.map((group) => (
          <div key={group.id} className="space-y-1">
            <p className="text-xs font-medium text-slate-500">Group {group.group_number}</p>
            {group.positions.map((pos) => (
              <PositionCell
                key={pos.id}
                position={pos}
                siegeId={siegeId}
                siegeMembers={siegeMembers}
                onUpdate={onUpdate}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function BoardPage() {
  const { id } = useParams<{ id: string }>();
  const siegeId = Number(id);
  const queryClient = useQueryClient();
  const [autofillPreview, setAutofillPreview] = useState<AutofillPreviewResult | null>(null);
  const [autofillOpen, setAutofillOpen] = useState(false);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [validationOpen, setValidationOpen] = useState(false);

  const { data: board, isLoading: boardLoading } = useQuery({
    queryKey: ['board', siegeId],
    queryFn: () => getBoard(siegeId),
  });

  const { data: siegeMembers } = useQuery({
    queryKey: ['siegeMembers', siegeId],
    queryFn: () => getSiegeMembers(siegeId),
  });

  const { data: siege } = useQuery({
    queryKey: ['siege', siegeId],
    queryFn: () => getSiege(siegeId),
  });

  const previewMutation = useMutation({
    mutationFn: () => previewAutofill(siegeId),
    onSuccess: (data) => {
      setAutofillPreview(data);
      setAutofillOpen(true);
    },
  });

  const applyMutation = useMutation({
    mutationFn: () => applyAutofill(siegeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['board', siegeId] });
      setAutofillOpen(false);
      setAutofillPreview(null);
    },
  });

  const validateMutation = useMutation({
    mutationFn: () => validateSiege(siegeId),
    onSuccess: (data) => {
      setValidation(data);
      setValidationOpen(true);
    },
  });

  function refreshBoard() {
    // no-op: board is already invalidated in PositionCell mutation
  }

  // Compute summary stats
  const allPositions =
    board?.buildings.flatMap((b) => b.groups.flatMap((g) => g.positions)) ?? [];
  const totalSlots = allPositions.length;
  const assignedCount = allPositions.filter(
    (p) => !p.is_disabled && !p.is_reserve && !p.has_no_assignment && p.member_id != null,
  ).length;
  const reserveCount = allPositions.filter((p) => p.is_reserve).length;
  const noAssignCount = allPositions.filter((p) => p.has_no_assignment).length;
  const emptyCount = allPositions.filter(
    (p) => !p.is_disabled && !p.is_reserve && !p.has_no_assignment && p.member_id == null,
  ).length;
  const disabledCount = allPositions.filter((p) => p.is_disabled).length;

  // Build a lookup of position_id → member name for autofill preview
  const positionLookup: Record<number, PositionResponse> = {};
  for (const pos of allPositions) {
    positionLookup[pos.id] = pos;
  }
  const memberLookup: Record<number, string> = {};
  for (const m of siegeMembers ?? []) {
    memberLookup[m.member_id] = m.member_name;
  }

  if (boardLoading) {
    return <div className="py-12 text-center text-slate-500">Loading board...</div>;
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            to={`/sieges/${siegeId}`}
            className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </Link>
          <h1 className="text-xl font-bold text-slate-900">
            Board — Siege {siege?.date ?? `#${siegeId}`}
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => validateMutation.mutate()}
            disabled={validateMutation.isPending}
          >
            {validateMutation.isPending ? 'Validating...' : 'Validate'}
          </Button>
          <Button
            size="sm"
            onClick={() => previewMutation.mutate()}
            disabled={previewMutation.isPending}
          >
            {previewMutation.isPending ? 'Loading...' : 'Preview Auto-fill'}
          </Button>
        </div>
      </div>

      {/* Summary bar */}
      <div className="mb-4 flex flex-wrap gap-3 rounded-lg border border-slate-200 bg-white px-4 py-2.5">
        <span className="text-sm text-slate-600">
          <span className="font-semibold text-slate-900">{totalSlots}</span> total
        </span>
        <span className="text-sm text-slate-600">
          <span className="font-semibold text-green-700">{assignedCount}</span> assigned
        </span>
        <span className="text-sm text-slate-600">
          <span className="font-semibold text-amber-600">{reserveCount}</span> reserve
        </span>
        <span className="text-sm text-slate-600">
          <span className="font-semibold text-slate-500">{noAssignCount}</span> N/A
        </span>
        <span className="text-sm text-slate-600">
          <span className="font-semibold text-orange-600">{emptyCount}</span> empty
        </span>
        <span className="text-sm text-slate-600">
          <span className="font-semibold text-slate-400">{disabledCount}</span> disabled
        </span>
      </div>

      {board?.buildings.length === 0 && (
        <div className="py-12 text-center text-slate-500">
          No buildings configured.{' '}
          <Link to={`/sieges/${siegeId}`} className="text-violet-600 hover:underline">
            Add buildings
          </Link>{' '}
          in siege settings.
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
        {board?.buildings.map((building) => (
          <BuildingCard
            key={building.id}
            building={building}
            siegeId={siegeId}
            siegeMembers={siegeMembers ?? []}
            onUpdate={refreshBoard}
          />
        ))}
      </div>

      {/* Autofill preview dialog */}
      <Dialog open={autofillOpen} onOpenChange={setAutofillOpen}>
        <DialogContent className="max-h-[80vh] max-w-lg overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Auto-fill Preview</DialogTitle>
            <DialogDescription>
              {autofillPreview?.assignments.length ?? 0} assignments proposed.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-1">
            {autofillPreview?.assignments.map((a) => {
              const member = a.member_id != null ? memberLookup[a.member_id] : null;
              const pos = positionLookup[a.position_id];
              return (
                <div
                  key={a.position_id}
                  className="flex items-center justify-between rounded-sm px-2 py-1 hover:bg-slate-50"
                >
                  <span className="text-sm text-slate-600">Position {pos?.position_number ?? a.position_id}</span>
                  <span className="text-sm font-medium">
                    {a.is_reserve ? (
                      <Badge variant="yellow">RESERVE</Badge>
                    ) : member ? (
                      member
                    ) : (
                      <span className="text-slate-400">Unassigned</span>
                    )}
                  </span>
                </div>
              );
            })}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAutofillOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => applyMutation.mutate()} disabled={applyMutation.isPending}>
              {applyMutation.isPending ? 'Applying...' : 'Apply'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Validation dialog */}
      <Dialog open={validationOpen} onOpenChange={setValidationOpen}>
        <DialogContent className="max-h-[80vh] max-w-lg overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Validation Results</DialogTitle>
          </DialogHeader>
          {validation && (
            <div className="space-y-2">
              {validation.errors.length === 0 && validation.warnings.length === 0 && (
                <p className="text-sm text-green-600">No issues found.</p>
              )}
              {validation.errors.map((e, i) => (
                <div key={i} className="flex items-start gap-2 rounded-md bg-red-50 px-3 py-2">
                  <Badge variant="destructive" className="mt-0.5 shrink-0">
                    Error {e.rule}
                  </Badge>
                  <p className="text-sm text-red-700">{e.message}</p>
                </div>
              ))}
              {validation.warnings.map((w, i) => (
                <div
                  key={i}
                  className="flex items-start gap-2 rounded-md bg-yellow-50 px-3 py-2"
                >
                  <Badge variant="yellow" className="mt-0.5 shrink-0">
                    Warning {w.rule}
                  </Badge>
                  <p className="text-sm text-yellow-800">{w.message}</p>
                </div>
              ))}
            </div>
          )}
          <DialogFooter>
            <Button onClick={() => setValidationOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
