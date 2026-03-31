import { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ChevronDown, ChevronRight, AlertTriangle, Check, ExternalLink, BookmarkCheck } from 'lucide-react';
import { getPosts } from '../api/posts';
import { getSiegeMemberPreferences } from '../api/sieges';
import { updatePosition } from '../api/board';
import type { BuildingResponse, SiegeMember, PostConditionRef } from '../api/types';
import { Button } from './ui/button';

// ─── Constants (duplicated from BoardPage to keep this file self-contained) ───

const ROLE_LABELS: Record<string, string> = {
  heavy_hitter: 'HH',
  advanced: 'Adv',
  medium: 'Med',
  novice: 'Nov',
};

const ROLE_PRIORITY: Record<string, number> = {
  heavy_hitter: 0,
  advanced: 1,
  medium: 2,
  novice: 3,
};

const ROLE_BADGE_COLORS: Record<string, string> = {
  heavy_hitter: 'bg-red-100 text-red-700',
  advanced: 'bg-amber-100 text-amber-700',
  medium: 'bg-green-100 text-green-700',
  novice: 'bg-blue-100 text-blue-700',
};

const POWER_LABELS: Record<string, string> = {
  lt_10m: '<10M',
  '10_15m': '10-15M',
  '16_20m': '16-20M',
  '21_25m': '21-25M',
  gt_25m: '>25M',
};

const PRIORITY_LABELS: Record<number, string> = {
  0: 'Unset',
  1: 'Low',
  2: 'Medium',
  3: 'High',
};

const PRIORITY_BADGE_COLORS: Record<number, string> = {
  0: 'bg-slate-100 text-slate-400',
  1: 'bg-slate-100 text-slate-600',
  2: 'bg-amber-100 text-amber-700',
  3: 'bg-red-100 text-red-700',
};

// ─── Types ────────────────────────────────────────────────────────────────────

interface MemberWithMatches {
  member: SiegeMember;
  matchedConditions: PostConditionRef[];
  matchScore: number;
}

// Map of { memberId_conditionId } → post number — for duplicate warnings
type DuplicateConditionMap = Map<string, number>;

// ─── Helpers ──────────────────────────────────────────────────────────────────

function buildDuplicateConditionMap(postBuildings: BuildingResponse[]): DuplicateConditionMap {
  const map: DuplicateConditionMap = new Map();
  for (const building of postBuildings) {
    for (const group of building.groups) {
      for (const pos of group.positions) {
        if (pos.member_id != null && pos.matched_condition_id != null) {
          const key = `${pos.member_id}_${pos.matched_condition_id}`;
          map.set(key, building.building_number);
        }
      }
    }
  }
  return map;
}

function findPostPosition(building: BuildingResponse): { positionId: number } | null {
  for (const group of building.groups) {
    for (const pos of group.positions) {
      if (!pos.is_disabled) {
        return { positionId: pos.id };
      }
    }
  }
  return null;
}

// ─── MemberAssignRow ──────────────────────────────────────────────────────────

function MemberAssignRow({
  memberWithMatches,
  hasConditions,
  postNumber,
  siegeId,
  positionId,
  duplicateMap,
  onAssigned,
  isLocked,
}: {
  memberWithMatches: MemberWithMatches;
  hasConditions: boolean;
  postNumber: number;
  siegeId: number;
  positionId: number;
  duplicateMap: DuplicateConditionMap;
  onAssigned: () => void;
  isLocked: boolean;
}) {
  const { member, matchedConditions } = memberWithMatches;
  const queryClient = useQueryClient();

  // Which condition is selected for the match radio
  const [selectedConditionId, setSelectedConditionId] = useState<number | null>(
    matchedConditions.length > 0 ? matchedConditions[0].id : null,
  );
  const [confirmPending, setConfirmPending] = useState(false);

  const mutation = useMutation({
    mutationFn: (data: { member_id: number; matched_condition_id: number | null }) =>
      updatePosition(siegeId, positionId, {
        member_id: data.member_id,
        is_reserve: false,
        has_no_assignment: false,
        matched_condition_id: data.matched_condition_id,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['board', siegeId] });
      setConfirmPending(false);
      onAssigned();
    },
  });

  function handleAssignClick() {
    // Check for duplicate condition assignment
    if (selectedConditionId != null) {
      const key = `${member.member_id}_${selectedConditionId}`;
      if (duplicateMap.has(key) && duplicateMap.get(key) !== postNumber) {
        setConfirmPending(true);
        return;
      }
    }
    doAssign();
  }

  function doAssign() {
    mutation.mutate({
      member_id: member.member_id,
      matched_condition_id: selectedConditionId,
    });
  }

  const role = member.member_role;
  const badgeColor = ROLE_BADGE_COLORS[role] ?? 'bg-slate-100 text-slate-600';
  const powerLabel = member.member_power_level
    ? (POWER_LABELS[member.member_power_level] ?? member.member_power_level)
    : null;

  // Check for duplicate warning
  const duplicatePostNumber =
    selectedConditionId != null
      ? duplicateMap.get(`${member.member_id}_${selectedConditionId}`)
      : undefined;
  const hasDuplicate =
    duplicatePostNumber != null && duplicatePostNumber !== postNumber;

  // Find the condition name for warning
  const selectedCondition =
    matchedConditions.find((c) => c.id === selectedConditionId) ?? null;

  return (
    <div className="rounded border border-slate-100 bg-white px-3 py-2">
      <div className="flex items-start gap-3">
        {/* Member info */}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-slate-800">{member.member_name}</span>
            <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${badgeColor}`}>
              {ROLE_LABELS[role] ?? role}
            </span>
            {powerLabel && (
              <span className="text-xs text-slate-500">{powerLabel}</span>
            )}
            {member.attack_day && (
              <span className="text-xs text-slate-500">Day {member.attack_day}</span>
            )}
          </div>

          {/* Condition radio buttons (only for matched members with conditions) */}
          {hasConditions && matchedConditions.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-2">
              {matchedConditions.map((c) => (
                <label key={c.id} className="flex cursor-pointer items-center gap-1.5">
                  <input
                    type="radio"
                    name={`condition-${member.member_id}-${postNumber}`}
                    value={c.id}
                    checked={selectedConditionId === c.id}
                    onChange={() => {
                      setSelectedConditionId(c.id);
                      setConfirmPending(false);
                    }}
                    className="h-3.5 w-3.5 accent-violet-600"
                  />
                  <span className="flex items-center gap-1 text-xs text-slate-700">
                    <Check className="h-3 w-3 text-green-600" />
                    {c.description}
                  </span>
                </label>
              ))}
            </div>
          )}

          {/* Duplicate warning */}
          {hasDuplicate && confirmPending && selectedCondition && (
            <div className="mt-1.5 flex items-center gap-2 rounded bg-amber-50 px-2 py-1 text-xs text-amber-800">
              <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-amber-500" />
              <span>
                Already matched on "{selectedCondition.description}" at Post{' '}
                {duplicatePostNumber}
              </span>
            </div>
          )}
        </div>

        {/* Assign / Confirm button */}
        {!isLocked && (
          <div className="shrink-0">
            {confirmPending ? (
              <div className="flex gap-1.5">
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 px-2 text-xs"
                  onClick={() => setConfirmPending(false)}
                >
                  Cancel
                </Button>
                <Button
                  size="sm"
                  className="h-7 bg-amber-600 px-2 text-xs hover:bg-amber-700"
                  onClick={doAssign}
                  disabled={mutation.isPending}
                >
                  Confirm anyway
                </Button>
              </div>
            ) : (
              <Button
                size="sm"
                variant="outline"
                className="h-7 px-2 text-xs"
                onClick={handleAssignClick}
                disabled={mutation.isPending}
              >
                {mutation.isPending ? 'Assigning...' : 'Assign'}
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── PostRow ──────────────────────────────────────────────────────────────────

function PostRow({
  postBuilding,
  siegeId,
  siegeMembers,
  preferenceMap,
  duplicateMap,
  isLocked,
  postNumber,
  priority,
  priorityDescription,
  activeConditions,
}: {
  postBuilding: BuildingResponse;
  siegeId: number;
  siegeMembers: SiegeMember[];
  preferenceMap: Map<number, number[]>; // member_id → condition ids
  duplicateMap: DuplicateConditionMap;
  isLocked: boolean;
  postNumber: number;
  priority: number;
  priorityDescription: string | null;
  activeConditions: PostConditionRef[];
}) {
  const [expanded, setExpanded] = useState(false);
  const queryClient = useQueryClient();

  // Find the position for this post building
  const postPosition = findPostPosition(postBuilding);
  const positionId = postPosition?.positionId ?? null;

  // Currently assigned member / reserve status (first non-disabled position)
  const assignedPosition = postBuilding.groups
    .flatMap((g) => g.positions)
    .find((p) => !p.is_disabled);
  const assignedMemberName = assignedPosition?.member_name ?? null;
  const isReserve = assignedPosition?.is_reserve ?? false;

  const reserveMutation = useMutation({
    mutationFn: (posId: number) =>
      updatePosition(siegeId, posId, {
        member_id: null,
        is_reserve: true,
        has_no_assignment: false,
        matched_condition_id: null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['board', siegeId] });
    },
  });

  const hasConditions = activeConditions.length > 0;

  // Build matched / unmatched member lists
  const { matched, unmatched } = useMemo(() => {
    const matchedList: MemberWithMatches[] = [];
    const unmatchedList: MemberWithMatches[] = [];

    for (const member of siegeMembers) {
      const memberCondIds = preferenceMap.get(member.member_id) ?? [];
      if (hasConditions) {
        const matchedConditions = activeConditions.filter((c) => memberCondIds.includes(c.id));
        if (matchedConditions.length > 0) {
          matchedList.push({
            member,
            matchedConditions,
            matchScore: matchedConditions.length,
          });
        } else {
          unmatchedList.push({ member, matchedConditions: [], matchScore: 0 });
        }
      } else {
        // No conditions — all members go in "all" (rendered as unmatched)
        unmatchedList.push({ member, matchedConditions: [], matchScore: 0 });
      }
    }

    // Sort matched: by matchScore desc, then role priority
    matchedList.sort((a, b) => {
      const scoreDiff = b.matchScore - a.matchScore;
      if (scoreDiff !== 0) return scoreDiff;
      return (
        (ROLE_PRIORITY[a.member.member_role] ?? 99) -
        (ROLE_PRIORITY[b.member.member_role] ?? 99)
      );
    });

    // Sort unmatched: by role priority, then name
    unmatchedList.sort((a, b) => {
      const roleDiff =
        (ROLE_PRIORITY[a.member.member_role] ?? 99) -
        (ROLE_PRIORITY[b.member.member_role] ?? 99);
      if (roleDiff !== 0) return roleDiff;
      return a.member.member_name.localeCompare(b.member.member_name);
    });

    return { matched: matchedList, unmatched: unmatchedList };
  }, [siegeMembers, preferenceMap, activeConditions, hasConditions]);

  const priorityLabel = PRIORITY_LABELS[priority] ?? String(priority);
  const priorityBadgeColor = PRIORITY_BADGE_COLORS[priority] ?? 'bg-slate-100 text-slate-600';

  return (
    <div className="rounded border border-slate-200 bg-white">
      {/* Collapsed header — always visible */}
      <button
        className="flex w-full items-center gap-3 px-4 py-3 text-left"
        onClick={() => setExpanded((v) => !v)}
      >
        <span className="shrink-0 text-slate-400">
          {expanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </span>

        {/* Post number */}
        <span className="shrink-0 text-sm font-semibold text-slate-700">
          Post {postNumber}
        </span>

        {/* Priority badge */}
        <span className={`shrink-0 rounded px-1.5 py-0.5 text-xs font-medium ${priorityBadgeColor}`}>
          {priorityLabel}
        </span>

        {/* Description */}
        {priorityDescription && (
          <span className="min-w-0 flex-1 truncate text-sm text-slate-600">
            {priorityDescription}
          </span>
        )}
        {!priorityDescription && <span className="flex-1" />}

        {/* Condition count */}
        {activeConditions.length > 0 ? (
          <span className="shrink-0 rounded bg-violet-100 px-1.5 py-0.5 text-xs font-medium text-violet-700">
            {activeConditions.length} {activeConditions.length === 1 ? 'condition' : 'conditions'}
          </span>
        ) : (
          <span className="shrink-0 text-xs text-slate-400">No conditions</span>
        )}

        {/* Assigned member / reserve status */}
        {isReserve ? (
          <span className="ml-2 flex shrink-0 items-center gap-1 text-sm font-medium text-teal-700">
            <BookmarkCheck className="h-3.5 w-3.5" />
            RESERVE
          </span>
        ) : (
          <span
            className={`ml-2 shrink-0 text-sm ${
              assignedMemberName ? 'font-medium text-slate-800' : 'text-slate-400'
            }`}
          >
            {assignedMemberName ?? 'Unassigned'}
          </span>
        )}
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-slate-100 px-4 pb-4 pt-3">
          {/* Active conditions (read-only) */}
          <div className="mb-3 flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Active Conditions
            </span>
            {activeConditions.length === 0 ? (
              <span className="text-xs text-slate-400">None</span>
            ) : (
              <div className="flex flex-wrap gap-1">
                {activeConditions.map((c) => (
                  <span
                    key={c.id}
                    className="rounded bg-violet-100 px-1.5 py-0.5 text-xs text-violet-700"
                  >
                    {c.description}
                  </span>
                ))}
              </div>
            )}
            <Link
              to={`/sieges/${siegeId}/posts?post=${postNumber}`}
              className="ml-auto flex shrink-0 items-center gap-1 text-xs text-slate-400 hover:text-violet-600"
              onClick={(e) => e.stopPropagation()}
            >
              <ExternalLink className="h-3 w-3" />
              Edit conditions
            </Link>
          </div>

          {positionId == null ? (
            <p className="text-sm text-slate-400">No active position for this post.</p>
          ) : (
            <>
              {/* Mark RESERVE action */}
              {!isLocked && (
                <div className="mb-3 flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 gap-1.5 px-2 text-xs text-teal-700 hover:bg-teal-50 hover:text-teal-800"
                    onClick={() => reserveMutation.mutate(positionId)}
                    disabled={reserveMutation.isPending || isReserve}
                  >
                    <BookmarkCheck className="h-3.5 w-3.5" />
                    {isReserve ? 'Marked RESERVE' : reserveMutation.isPending ? 'Saving...' : 'Mark RESERVE'}
                  </Button>
                  {isReserve && (
                    <span className="text-xs text-slate-400">
                      Assign a member above to clear reserve status
                    </span>
                  )}
                </div>
              )}
              {/* Matched members */}
              {hasConditions && matched.length > 0 && (
                <div className="mb-3">
                  <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-green-700">
                    Matched Members ({matched.length})
                  </p>
                  <div className="space-y-1.5">
                    {matched.map((mwm) => (
                      <MemberAssignRow
                        key={mwm.member.member_id}
                        memberWithMatches={mwm}
                        hasConditions={hasConditions}
                        postNumber={postNumber}
                        siegeId={siegeId}
                        positionId={positionId}
                        duplicateMap={duplicateMap}
                        onAssigned={() => setExpanded(false)}
                        isLocked={isLocked}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* Unmatched / all members */}
              {unmatched.length > 0 && (
                <div>
                  <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    {hasConditions
                      ? `Other Members (${unmatched.length})`
                      : `All Members (${unmatched.length})`}
                  </p>
                  <div className="space-y-1.5">
                    {unmatched.map((mwm) => (
                      <MemberAssignRow
                        key={mwm.member.member_id}
                        memberWithMatches={mwm}
                        hasConditions={hasConditions}
                        postNumber={postNumber}
                        siegeId={siegeId}
                        positionId={positionId}
                        duplicateMap={duplicateMap}
                        onAssigned={() => setExpanded(false)}
                        isLocked={isLocked}
                      />
                    ))}
                  </div>
                </div>
              )}

              {matched.length === 0 && unmatched.length === 0 && (
                <p className="text-sm text-slate-400">No members in this siege.</p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ─── PostsTab ─────────────────────────────────────────────────────────────────

export function PostsTab({
  buildings,
  siegeId,
  siegeMembers,
  isLocked,
}: {
  buildings: BuildingResponse[];
  siegeId: number;
  siegeMembers: SiegeMember[];
  isLocked: boolean;
  memberRoleMap?: Record<number, string>; // accepted for API compatibility, used by callers
}) {
  const { data: preferences, isLoading: prefLoading } = useQuery({
    queryKey: ['memberPreferences', siegeId],
    queryFn: () => getSiegeMemberPreferences(siegeId),
  });

  const { data: posts, isLoading: postsLoading, isError: postsError } = useQuery({
    queryKey: ['posts', siegeId],
    queryFn: () => getPosts(siegeId),
  });

  // Build preference map: member_id → array of condition ids
  const preferenceMap = useMemo(() => {
    const map = new Map<number, number[]>();
    for (const p of preferences ?? []) {
      map.set(
        p.member_id,
        p.preferences.map((c) => c.id),
      );
    }
    return map;
  }, [preferences]);

  // Build duplicate condition map from post buildings
  const postBuildings = useMemo(
    () => buildings.filter((b) => b.building_type === 'post'),
    [buildings],
  );

  const duplicateMap = useMemo(
    () => buildDuplicateConditionMap(postBuildings),
    [postBuildings],
  );

  // Build a map from building_number → Post (for priority/description/conditions)
  const postByNumber = useMemo(() => {
    const map = new Map<number, NonNullable<typeof posts>[0]>();
    if (!posts) return map;
    for (const p of posts) {
      map.set(p.building_number, p);
    }
    return map;
  }, [posts]);

  // Sort post buildings by building_number
  const sortedPostBuildings = useMemo(
    () => [...postBuildings].sort((a, b) => a.building_number - b.building_number),
    [postBuildings],
  );

  if (prefLoading || postsLoading) {
    return <div className="py-12 text-center text-sm text-slate-500">Loading posts...</div>;
  }

  if (postsError) {
    return (
      <div className="py-12 text-center text-sm text-red-500">
        Failed to load posts. Check that the backend is running.
      </div>
    );
  }

  if (sortedPostBuildings.length === 0) {
    return (
      <div className="py-12 text-center text-slate-500">
        No posts configured.{' '}
        <Link to={`/sieges/${siegeId}`} className="text-violet-600 hover:underline">
          Add buildings
        </Link>{' '}
        in siege settings.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {sortedPostBuildings.map((building) => {
        const post = postByNumber.get(building.building_number);
        return (
          <PostRow
            key={building.id}
            postBuilding={building}
            siegeId={siegeId}
            siegeMembers={siegeMembers}
            preferenceMap={preferenceMap}
            duplicateMap={duplicateMap}
            isLocked={isLocked}
            postNumber={building.building_number}
            priority={post?.priority ?? 1}
            priorityDescription={post?.description ?? null}
            activeConditions={post?.active_conditions ?? []}
          />
        );
      })}
    </div>
  );
}
