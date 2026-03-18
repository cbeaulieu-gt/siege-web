import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getPosts, updatePost, setPostConditions } from '../api/posts';
import { getPostConditions } from '../api/members';
import type { Post, PostConditionRef } from '../api/types';
import { Button } from '../components/ui/button';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Checkbox } from '../components/ui/checkbox';
import { Badge } from '../components/ui/badge';
import { ArrowLeft, ChevronDown, ChevronUp, LayoutGrid, MessageSquare, Users, GitCompare, Settings } from 'lucide-react';

const PRIORITY_LABELS: Record<number, string> = { 1: 'Low', 2: 'Medium', 3: 'High' };

function groupConditionsByLevel(conditions: PostConditionRef[]) {
  const groups: Record<number, PostConditionRef[]> = {};
  for (const c of conditions) {
    if (!groups[c.stronghold_level]) groups[c.stronghold_level] = [];
    groups[c.stronghold_level].push(c);
  }
  return groups;
}

function PostRow({ post, siegeId }: { post: Post; siegeId: number }) {
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const [description, setDescription] = useState(post.description ?? '');
  const [selectedConditions, setSelectedConditions] = useState<Set<number>>(
    new Set(post.active_conditions.map((c) => c.id)),
  );

  const { data: allConditions } = useQuery({
    queryKey: ['postConditions'],
    queryFn: getPostConditions,
    enabled: expanded,
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      updatePost(siegeId, post.id, {
        description: description || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['posts', siegeId] });
    },
  });

  const condMutation = useMutation({
    mutationFn: () => setPostConditions(siegeId, post.id, Array.from(selectedConditions)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['posts', siegeId] });
    },
  });

  function toggleCondition(id: number) {
    setSelectedConditions((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else if (next.size < 3) {
        next.add(id);
      }
      return next;
    });
  }

  const condGroups = allConditions ? groupConditionsByLevel(allConditions) : {};

  return (
    <div className="rounded-lg border border-slate-200 bg-white">
      <div className="flex items-center gap-4 px-4 py-3">
        <span className="text-sm font-semibold text-slate-900">
          Post {post.building_number}
        </span>
        <span className="text-sm text-slate-500">Priority: {PRIORITY_LABELS[post.priority] ?? post.priority}</span>
        {post.description && (
          <span className="text-sm text-slate-600 truncate">{post.description}</span>
        )}
        <div className="ml-auto flex items-center gap-2">
          {post.active_conditions.map((c) => (
            <Badge key={c.id} variant="secondary" className="text-xs">
              {c.description}
            </Badge>
          ))}
          <button
            className="rounded p-1 hover:bg-slate-100"
            onClick={() => setExpanded((v) => !v)}
          >
            {expanded ? (
              <ChevronUp className="h-4 w-4 text-slate-500" />
            ) : (
              <ChevronDown className="h-4 w-4 text-slate-500" />
            )}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-slate-100 px-4 py-4 space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor={`desc-${post.id}`}>Description</Label>
            <Textarea
              id={`desc-${post.id}`}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              placeholder="Optional description"
            />
          </div>
          <Button
            size="sm"
            onClick={() => updateMutation.mutate()}
            disabled={updateMutation.isPending}
          >
            Save Details
          </Button>

          <div>
            <h4 className="mb-2 text-sm font-medium text-slate-700">
              Conditions (max 3)
            </h4>
            {Object.entries(condGroups)
              .sort(([a], [b]) => Number(a) - Number(b))
              .map(([level, conds]) => (
                <div key={level} className="mb-3">
                  <p className="mb-1 text-xs font-medium text-slate-500">
                    Stronghold Level {level}
                  </p>
                  <div className="grid grid-cols-2 gap-1.5">
                    {conds.map((c) => {
                      const checked = selectedConditions.has(c.id);
                      const disabled = !checked && selectedConditions.size >= 3;
                      return (
                        <div key={c.id} className="flex items-center gap-2">
                          <Checkbox
                            id={`cond-${post.id}-${c.id}`}
                            checked={checked}
                            disabled={disabled}
                            onCheckedChange={() => toggleCondition(c.id)}
                          />
                          <Label
                            htmlFor={`cond-${post.id}-${c.id}`}
                            className="text-xs font-normal"
                          >
                            {c.description}
                          </Label>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            <Button
              size="sm"
              variant="secondary"
              onClick={() => condMutation.mutate()}
              disabled={condMutation.isPending}
            >
              Save Conditions
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function PostsPage() {
  const { id } = useParams<{ id: string }>();
  const siegeId = Number(id);

  const { data: posts, isLoading, error } = useQuery({
    queryKey: ['posts', siegeId],
    queryFn: () => getPosts(siegeId),
  });

  const sorted = posts?.slice().sort((a, b) => a.priority - b.priority);

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
          <h1 className="text-2xl font-bold text-slate-900">Posts — Siege #{siegeId}</h1>
          <p className="mt-1 text-sm text-slate-500">
            Set post conditions and priority for each post in this siege.
          </p>
        </div>
        <div className="flex gap-2 text-sm">
          <Link
            to={`/sieges/${siegeId}/board`}
            className="flex items-center gap-1 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-slate-700 hover:bg-slate-50"
          >
            <LayoutGrid className="h-4 w-4" />
            Board
          </Link>
          <span className="flex items-center gap-1 rounded-md border border-slate-300 bg-slate-100 px-3 py-1.5 text-slate-700 font-medium">
            <MessageSquare className="h-4 w-4" />
            Posts
          </span>
          <Link
            to={`/sieges/${siegeId}/members`}
            className="flex items-center gap-1 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-slate-700 hover:bg-slate-50"
          >
            <Users className="h-4 w-4" />
            Members
          </Link>
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
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">
          Failed to load posts.
        </div>
      )}

      {isLoading ? (
        <div className="py-12 text-center text-slate-500">Loading...</div>
      ) : sorted?.length === 0 ? (
        <div className="py-12 text-center text-slate-500">
          No posts found for this siege.
        </div>
      ) : (
        <div className="space-y-3">
          {sorted?.map((post) => (
            <PostRow key={post.id} post={post} siegeId={siegeId} />
          ))}
        </div>
      )}
    </div>
  );
}
