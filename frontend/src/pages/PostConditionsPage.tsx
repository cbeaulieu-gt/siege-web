import { useQuery } from '@tanstack/react-query';
import { getPostConditions } from '../api/members';
import type { PostCondition } from '../api/types';
import { Badge } from '../components/ui/badge';

function groupByLevel(conditions: PostCondition[]): Record<number, PostCondition[]> {
  const groups: Record<number, PostCondition[]> = {};
  for (const c of conditions) {
    if (!groups[c.stronghold_level]) groups[c.stronghold_level] = [];
    groups[c.stronghold_level].push(c);
  }
  return groups;
}

export default function PostConditionsPage() {
  const { data: conditions, isLoading } = useQuery({
    queryKey: ['postConditions'],
    queryFn: getPostConditions,
  });

  const groups = conditions ? groupByLevel(conditions) : {};

  return (
    <div className="max-w-2xl">
      <h1 className="mb-2 text-2xl font-bold text-slate-900">Post Conditions</h1>
      <p className="mb-6 text-sm text-slate-500">
        Reference list of all post conditions by stronghold level.
      </p>

      {isLoading ? (
        <div className="py-12 text-center text-slate-500">Loading...</div>
      ) : (
        <div className="space-y-6">
          {Object.entries(groups)
            .sort(([a], [b]) => Number(a) - Number(b))
            .map(([level, conds]) => (
              <div key={level} className="rounded-lg border border-slate-200 bg-white p-4">
                <h2 className="mb-3 text-sm font-semibold text-slate-900">
                  Stronghold Level {level}
                  <Badge variant="secondary" className="ml-2">
                    {conds.length}
                  </Badge>
                </h2>
                <ul className="space-y-1.5">
                  {conds.map((c) => (
                    <li key={c.id} className="text-sm text-slate-700">
                      {c.description}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}
