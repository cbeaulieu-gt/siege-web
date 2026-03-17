import { useQuery } from '@tanstack/react-query';
import { useNavigate, Link } from 'react-router-dom';
import { getSieges } from '../api/sieges';
import type { SiegeStatus } from '../api/types';
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
import { PlusCircle } from 'lucide-react';

type StatusBadgeVariant = 'blue' | 'green' | 'gray';

const STATUS_VARIANTS: Record<SiegeStatus, StatusBadgeVariant> = {
  planning: 'blue',
  active: 'green',
  complete: 'gray',
};

const STATUS_LABELS: Record<SiegeStatus, string> = {
  planning: 'Planning',
  active: 'Active',
  complete: 'Complete',
};

export default function SiegesPage() {
  const navigate = useNavigate();
  const { data: sieges, isLoading, error } = useQuery({
    queryKey: ['sieges'],
    queryFn: () => getSieges(),
  });

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Sieges</h1>
        <Button onClick={() => navigate('/sieges/new')}>
          <PlusCircle className="h-4 w-4" />
          New Siege
        </Button>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">
          Failed to load sieges.
        </div>
      )}

      {isLoading ? (
        <div className="py-12 text-center text-slate-500">Loading...</div>
      ) : (
        <div className="rounded-lg border border-slate-200 bg-white">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Scrolls</TableHead>
                <TableHead>Links</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sieges?.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="py-8 text-center text-slate-500">
                    No sieges yet. Create one to get started.
                  </TableCell>
                </TableRow>
              )}
              {sieges?.map((s) => (
                <TableRow
                  key={s.id}
                  className="cursor-pointer"
                  onClick={() => navigate(`/sieges/${s.id}`)}
                >
                  <TableCell className="font-medium">
                    {s.date ?? <span className="text-slate-400">No date</span>}
                  </TableCell>
                  <TableCell>
                    <Badge variant={STATUS_VARIANTS[s.status]}>
                      {STATUS_LABELS[s.status]}
                    </Badge>
                  </TableCell>
                  <TableCell>{s.defense_scroll_count}</TableCell>
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <div className="flex gap-3 text-sm">
                      <Link
                        to={`/sieges/${s.id}/board`}
                        className="text-violet-600 hover:underline"
                      >
                        Board
                      </Link>
                      <Link
                        to={`/sieges/${s.id}/posts`}
                        className="text-violet-600 hover:underline"
                      >
                        Posts
                      </Link>
                      <Link
                        to={`/sieges/${s.id}/members`}
                        className="text-violet-600 hover:underline"
                      >
                        Members
                      </Link>
                    </div>
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
