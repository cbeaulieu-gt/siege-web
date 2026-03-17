import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createSiege, cloneSiege, getSieges } from '../api/sieges';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { ArrowLeft } from 'lucide-react';
import { isAxiosError } from 'axios';

/** Returns the next Tuesday that is at least `daysAhead` days from today (local time). */
function nextTuesdayFrom(from: Date): Date {
  const d = new Date(from);
  // Tuesday = 2; advance until we land on one
  const diff = (2 - d.getDay() + 7) % 7 || 7;
  d.setDate(d.getDate() + diff);
  return d;
}

function formatDateLocal(d: Date): string {
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

function suggestNextSiegeDate(recentDate: string | null): string {
  if (recentDate) {
    // Parse the ISO date string as local date to avoid UTC offset shifting the day
    const [y, m, day] = recentDate.split('-').map(Number);
    const last = new Date(y, m - 1, day);
    const twoWeeksLater = new Date(last);
    twoWeeksLater.setDate(last.getDate() + 14);
    return formatDateLocal(twoWeeksLater);
  }
  return formatDateLocal(nextTuesdayFrom(new Date()));
}

export default function SiegeCreatePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [scrollCount, setScrollCount] = useState('3');
  const [cloneFromId, setCloneFromId] = useState<string>('none');

  const { data: sieges } = useQuery({
    queryKey: ['sieges'],
    queryFn: () => getSieges(),
  });

  // Derive the suggested date once sieges have loaded; fall back to '' while loading
  const mostRecentDate = sieges && sieges.length > 0 ? (sieges[0].date ?? null) : null;
  const suggestedDate =
    sieges !== undefined ? suggestNextSiegeDate(mostRecentDate) : '';

  const [date, setDate] = useState('');
  // Once the suggestion is ready and the user hasn't typed yet, apply it
  const effectiveDate = date || suggestedDate;
  const [error, setError] = useState('');

  const createMutation = useMutation({
    mutationFn: () =>
      createSiege({
        date: effectiveDate || undefined,
        defense_scroll_count: Number(scrollCount),
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['sieges'] });
      navigate(`/sieges/${data.id}`);
    },
    onError: (err) => {
      setError(isAxiosError(err) ? (err.response?.data?.detail ?? 'Failed to create siege') : 'Failed to create siege');
    },
  });

  const cloneMutation = useMutation({
    mutationFn: (sourceId: number) => cloneSiege(sourceId),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['sieges'] });
      navigate(`/sieges/${data.id}`);
    },
    onError: (err) => {
      setError(isAxiosError(err) ? (err.response?.data?.detail ?? 'Failed to clone siege') : 'Failed to clone siege');
    },
  });

  const isCloning = cloneFromId !== 'none';
  const isPending = createMutation.isPending || cloneMutation.isPending;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    if (isCloning) {
      cloneMutation.mutate(Number(cloneFromId));
    } else {
      createMutation.mutate();
    }
  }

  return (
    <div className="max-w-md">
      <Link
        to="/sieges"
        className="mb-6 flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Sieges
      </Link>

      <h1 className="mb-6 text-2xl font-bold text-slate-900">New Siege</h1>

      <div className="rounded-lg border border-slate-200 bg-white p-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="clone-from">Clone from existing siege (optional)</Label>
            <Select value={cloneFromId} onValueChange={setCloneFromId}>
              <SelectTrigger id="clone-from">
                <SelectValue placeholder="No — create blank siege" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">No — create blank siege</SelectItem>
                {sieges?.map((s) => (
                  <SelectItem key={s.id} value={String(s.id)}>
                    {s.date ?? `Siege #${s.id}`} ({s.status})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {isCloning && (
              <p className="text-xs text-slate-500">
                Buildings and member assignments will be copied from the selected siege. Date and status will be reset to planning.
              </p>
            )}
          </div>

          {!isCloning && (
            <>
              <div className="space-y-1.5">
                <Label htmlFor="date">Date</Label>
                <Input
                  id="date"
                  type="date"
                  value={effectiveDate}
                  onChange={(e) => setDate(e.target.value)}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="scrolls">Defense Scroll Count</Label>
                <Input
                  id="scrolls"
                  type="number"
                  min="0"
                  value={scrollCount}
                  onChange={(e) => setScrollCount(e.target.value)}
                />
              </div>
            </>
          )}

          {error && <p className="text-sm text-red-600">{error}</p>}

          <div className="flex gap-3 pt-2">
            <Button type="submit" disabled={isPending}>
              {isPending
                ? isCloning ? 'Cloning...' : 'Creating...'
                : isCloning ? 'Clone Siege' : 'Create Siege'}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => navigate('/sieges')}
            >
              Cancel
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
