import { useParams, Outlet } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getSiege } from '../api/sieges';
import { Lock } from 'lucide-react';

export default function SiegeLayout() {
  const { id } = useParams<{ id: string }>();
  const siegeId = Number(id);

  const { data: siege } = useQuery({
    queryKey: ['siege', siegeId],
    queryFn: () => getSiege(siegeId),
    enabled: Boolean(siegeId),
  });

  return (
    <>
      {siege?.status === 'complete' && (
        <div className="mb-6 flex items-center gap-2 rounded-lg bg-red-600 px-4 py-3 text-sm font-medium text-white">
          <Lock className="h-4 w-4 shrink-0" />
          This siege is locked — no changes allowed
        </div>
      )}
      <Outlet />
    </>
  );
}
