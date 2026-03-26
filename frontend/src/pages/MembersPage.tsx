import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, Link } from 'react-router-dom';
import { getMembers } from '../api/members';
import type { MemberRole } from '../api/types';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { Checkbox } from '../components/ui/checkbox';
import { Label } from '../components/ui/label';
import { UserPlus, ChevronRight, RefreshCw } from 'lucide-react';
import DiscordSyncModal from '../components/DiscordSyncModal';

const POWER_LABELS: Record<string, string> = {
  lt_10m: '< 10M',
  '10_15m': '10-15M',
  '16_20m': '16-20M',
  '21_25m': '21-25M',
  gt_25m: '> 25M',
};

const ROLE_LABELS: Record<MemberRole, string> = {
  heavy_hitter: 'Heavy Hitter',
  advanced: 'Advanced',
  medium: 'Medium',
  novice: 'Novice',
};

type RoleBadgeVariant = 'red' | 'orange' | 'blue' | 'gray';

const ROLE_VARIANTS: Record<MemberRole, RoleBadgeVariant> = {
  heavy_hitter: 'red',
  advanced: 'orange',
  medium: 'blue',
  novice: 'gray',
};

export default function MembersPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [roleFilter, setRoleFilter] = useState<string>('all');
  const [activeOnly, setActiveOnly] = useState(true);
  const [syncOpen, setSyncOpen] = useState(false);

  const { data: members, isLoading, error } = useQuery({
    queryKey: ['members', activeOnly],
    queryFn: () => getMembers({ is_active: activeOnly ? true : undefined }),
  });

  const filtered = members
    ?.filter((m) => roleFilter !== 'all' ? m.role === roleFilter : true)
    .sort((a, b) => a.name.localeCompare(b.name));

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Members</h1>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => setSyncOpen(true)}>
            <RefreshCw className="h-4 w-4" />
            Sync Discord
          </Button>
          <Button onClick={() => navigate('/members/new')}>
            <UserPlus className="h-4 w-4" />
            Add Member
          </Button>
        </div>
      </div>

      <DiscordSyncModal
        open={syncOpen}
        onClose={() => setSyncOpen(false)}
        onApplied={() => {
          setSyncOpen(false);
          queryClient.invalidateQueries({ queryKey: ['members'] });
        }}
      />

      <div className="mb-4 flex items-center gap-4">
        <div className="w-48">
          <Select value={roleFilter} onValueChange={setRoleFilter}>
            <SelectTrigger>
              <SelectValue placeholder="Filter by role" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Roles</SelectItem>
              <SelectItem value="heavy_hitter">Heavy Hitter</SelectItem>
              <SelectItem value="advanced">Advanced</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
              <SelectItem value="novice">Novice</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-2">
          <Checkbox
            id="active-only"
            checked={activeOnly}
            onCheckedChange={(v) => setActiveOnly(Boolean(v))}
          />
          <Label htmlFor="active-only">Active only</Label>
        </div>
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
                <TableHead>Role</TableHead>
                <TableHead>Power</TableHead>
                <TableHead>Status</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered?.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="py-8 text-center text-slate-500">
                    No members found.
                  </TableCell>
                </TableRow>
              )}
              {filtered?.map((m) => (
                <TableRow
                  key={m.id}
                  className="cursor-pointer"
                  onClick={() => navigate(`/members/${m.id}`)}
                >
                  <TableCell className="font-medium">{m.name}</TableCell>
                  <TableCell>
                    <Badge variant={ROLE_VARIANTS[m.role]}>
                      {ROLE_LABELS[m.role]}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {m.power_level ? POWER_LABELS[m.power_level] ?? m.power_level : '-'}
                  </TableCell>
                  <TableCell>
                    <Badge variant={m.is_active ? 'green' : 'gray'}>
                      {m.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Link
                      to={`/members/${m.id}`}
                      onClick={(e) => e.stopPropagation()}
                      className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-700"
                    >
                      Edit / Preferences
                      <ChevronRight className="h-3.5 w-3.5" />
                    </Link>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
