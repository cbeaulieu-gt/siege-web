import { useState, useEffect } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getMember,
  createMember,
  updateMember,
  getPostConditions,
  getMemberPreferences,
  updateMemberPreferences,
} from '../api/members';
import type { MemberRole, PostCondition } from '../api/types';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
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
import { ArrowLeft } from 'lucide-react';
import { isAxiosError } from 'axios';

const ROLE_OPTIONS: { value: MemberRole; label: string }[] = [
  { value: 'heavy_hitter', label: 'Heavy Hitter' },
  { value: 'advanced', label: 'Advanced' },
  { value: 'medium', label: 'Medium' },
  { value: 'novice', label: 'Novice' },
];

function groupByLevel(conditions: PostCondition[]) {
  const groups: Record<number, PostCondition[]> = {};
  for (const c of conditions) {
    if (!groups[c.stronghold_level]) groups[c.stronghold_level] = [];
    groups[c.stronghold_level].push(c);
  }
  return groups;
}

export default function MemberDetailPage() {
  const { id } = useParams<{ id: string }>();
  const isNew = id === undefined || id === 'new';
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [name, setName] = useState('');
  const [discord, setDiscord] = useState('');
  const [role, setRole] = useState<MemberRole>('novice');
  const [power, setPower] = useState('');
  const [sortValue, setSortValue] = useState('0');
  const [deactivateOpen, setDeactivateOpen] = useState(false);
  const [selectedConditions, setSelectedConditions] = useState<Set<number>>(new Set());
  const [saveError, setSaveError] = useState('');

  const memberId = isNew ? null : Number(id);

  const { data: member, isLoading: memberLoading } = useQuery({
    queryKey: ['member', memberId],
    queryFn: () => getMember(memberId!),
    enabled: memberId != null,
  });

  const { data: allConditions } = useQuery({
    queryKey: ['postConditions'],
    queryFn: getPostConditions,
    enabled: !isNew,
  });

  const { data: preferences } = useQuery({
    queryKey: ['memberPreferences', memberId],
    queryFn: () => getMemberPreferences(memberId!),
    enabled: memberId != null,
  });

  useEffect(() => {
    if (member) {
      setName(member.name);
      setDiscord(member.discord_username ?? '');
      setRole(member.role);
      setPower(member.power != null ? String(member.power) : '');
      setSortValue(String(member.sort_value));
    }
  }, [member]);

  useEffect(() => {
    if (preferences) {
      setSelectedConditions(new Set(preferences.map((p) => p.id)));
    }
  }, [preferences]);

  const createMutation = useMutation({
    mutationFn: () =>
      createMember({
        name,
        discord_username: discord || null,
        role,
        power: power ? Number(power) : null,
        sort_value: Number(sortValue),
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['members'] });
      navigate(`/members/${data.id}`);
    },
    onError: (err) => {
      setSaveError(isAxiosError(err) ? (err.response?.data?.detail ?? 'Save failed') : 'Save failed');
    },
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      updateMember(memberId!, {
        name,
        discord_username: discord || null,
        role,
        power: power ? Number(power) : null,
        sort_value: Number(sortValue),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['members'] });
      queryClient.invalidateQueries({ queryKey: ['member', memberId] });
    },
    onError: (err) => {
      setSaveError(isAxiosError(err) ? (err.response?.data?.detail ?? 'Save failed') : 'Save failed');
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: () => updateMember(memberId!, { is_active: false }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['members'] });
      queryClient.invalidateQueries({ queryKey: ['member', memberId] });
      setDeactivateOpen(false);
    },
  });

  const prefMutation = useMutation({
    mutationFn: (ids: number[]) => updateMemberPreferences(memberId!, ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['memberPreferences', memberId] });
    },
  });

  function handleSave() {
    setSaveError('');
    if (isNew) {
      createMutation.mutate();
    } else {
      updateMutation.mutate();
    }
  }

  function toggleCondition(id: number) {
    setSelectedConditions((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function handleSavePreferences() {
    prefMutation.mutate(Array.from(selectedConditions));
  }

  if (!isNew && memberLoading) {
    return <div className="py-12 text-center text-slate-500">Loading...</div>;
  }

  const conditionGroups = allConditions ? groupByLevel(allConditions) : {};

  return (
    <div className="max-w-2xl">
      <Link
        to="/members"
        className="mb-6 flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Members
      </Link>

      <h1 className="mb-6 text-2xl font-bold text-slate-900">
        {isNew ? 'Add Member' : member?.name ?? 'Edit Member'}
      </h1>

      <div className="rounded-lg border border-slate-200 bg-white p-6">
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Member name"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="discord">Discord Username</Label>
            <Input
              id="discord"
              value={discord}
              onChange={(e) => setDiscord(e.target.value)}
              placeholder="Optional"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="role">Role</Label>
            <Select value={role} onValueChange={(v) => setRole(v as MemberRole)}>
              <SelectTrigger id="role">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ROLE_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="power">Power</Label>
            <Input
              id="power"
              type="number"
              value={power}
              onChange={(e) => setPower(e.target.value)}
              placeholder="Optional"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="sort">Sort Value</Label>
            <Input
              id="sort"
              type="number"
              value={sortValue}
              onChange={(e) => setSortValue(e.target.value)}
            />
          </div>

          {saveError && (
            <p className="text-sm text-red-600">{saveError}</p>
          )}

          <div className="flex gap-3 pt-2">
            <Button
              onClick={handleSave}
              disabled={createMutation.isPending || updateMutation.isPending}
            >
              {createMutation.isPending || updateMutation.isPending ? 'Saving...' : 'Save'}
            </Button>
            {!isNew && member?.is_active && (
              <Button
                variant="destructive"
                onClick={() => setDeactivateOpen(true)}
              >
                Deactivate
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Post Preferences (only for existing members) */}
      {!isNew && allConditions && (
        <div className="mt-6 rounded-lg border border-slate-200 bg-white p-6">
          <h2 className="mb-4 text-lg font-semibold text-slate-900">Post Preferences</h2>
          <p className="mb-4 text-sm text-slate-500">
            Select the post conditions this member prefers to fill.
          </p>

          {Object.entries(conditionGroups)
            .sort(([a], [b]) => Number(a) - Number(b))
            .map(([level, conds]) => (
              <div key={level} className="mb-4">
                <h3 className="mb-2 text-sm font-medium text-slate-700">
                  Stronghold Level {level}
                </h3>
                <div className="space-y-2">
                  {conds.map((c) => (
                    <div key={c.id} className="flex items-center gap-2">
                      <Checkbox
                        id={`cond-${c.id}`}
                        checked={selectedConditions.has(c.id)}
                        onCheckedChange={() => toggleCondition(c.id)}
                      />
                      <Label htmlFor={`cond-${c.id}`} className="font-normal">
                        {c.description}
                      </Label>
                    </div>
                  ))}
                </div>
              </div>
            ))}

          <Button
            className="mt-4"
            onClick={handleSavePreferences}
            disabled={prefMutation.isPending}
          >
            {prefMutation.isPending ? 'Saving...' : 'Save Preferences'}
          </Button>
          {prefMutation.isSuccess && (
            <p className="mt-2 text-sm text-green-600">Preferences saved.</p>
          )}
        </div>
      )}

      <Dialog open={deactivateOpen} onOpenChange={setDeactivateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Deactivate Member</DialogTitle>
            <DialogDescription>
              Are you sure you want to deactivate {member?.name}? They will no longer appear
              in active member lists.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeactivateOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => deactivateMutation.mutate()}
              disabled={deactivateMutation.isPending}
            >
              Deactivate
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
