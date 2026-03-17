import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { createSiege } from '../api/sieges';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { ArrowLeft } from 'lucide-react';
import { isAxiosError } from 'axios';

export default function SiegeCreatePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [date, setDate] = useState('');
  const [scrollCount, setScrollCount] = useState('3');
  const [error, setError] = useState('');

  const mutation = useMutation({
    mutationFn: () =>
      createSiege({
        date: date || undefined,
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

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    mutation.mutate();
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
            <Label htmlFor="date">Date</Label>
            <Input
              id="date"
              type="date"
              value={date}
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

          {error && <p className="text-sm text-red-600">{error}</p>}

          <div className="flex gap-3 pt-2">
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? 'Creating...' : 'Create Siege'}
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
