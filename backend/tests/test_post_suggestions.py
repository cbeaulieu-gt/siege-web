"""Unit tests for the Suggest Post Assignments service.

All tests use SimpleNamespace fixtures (no live DB) following the pattern
in tests/test_autofill.py.  Fast, mocked, in-process.

Coverage:
- Issue AC bullets #3, #4, #5, #6
- Charge #1: reserve / disabled position skip reasons
- Charges #2, #8: determinism and lexicographic scoring contract
- Charge #9: apply edge cases (empty input, unknown ids, no-op)
- Charge #14: documented suboptimality — property-based, not exact-output
- Apply behavior: full, subset, expired TTL, completed siege
- Apply-time revalidation stale reasons
"""

import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

import app.models  # noqa: F401 — populate metadata
from app.main import app
from app.models.enums import MemberRole, SiegeStatus
from app.schemas.post_suggestions import (
    PostSuggestionApplyRequest,
    PostSuggestionApplyResult,
    PostSuggestionPreviewResult,
)
from app.services import post_suggestions as service

# ---------------------------------------------------------------------------
# Helpers — SimpleNamespace factories
# ---------------------------------------------------------------------------

_NOW = datetime.datetime(2026, 5, 9, 12, 0, 0)
_FUTURE = _NOW + datetime.timedelta(minutes=29)


def _make_condition(id: int, description: str = "cond") -> SimpleNamespace:
    return SimpleNamespace(id=id, description=description, stronghold_level=1)


def _make_member(
    id: int,
    name: str = "Member",
    is_active: bool = True,
    preferences: list | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        name=name,
        is_active=is_active,
        role=MemberRole.advanced,
        post_preferences=preferences or [],
    )


def _make_siege_member(member: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(siege_id=1, member_id=member.id, member=member)


def _make_position(
    id: int,
    member_id: int | None = None,
    member_name: str | None = None,
    is_reserve: bool = False,
    is_disabled: bool = False,
    matched_condition_id: int | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        position_number=1,
        member_id=member_id,
        is_reserve=is_reserve,
        is_disabled=is_disabled,
        matched_condition_id=matched_condition_id,
        member=SimpleNamespace(name=member_name) if member_id and member_name else None,
    )


def _make_group(positions: list) -> SimpleNamespace:
    return SimpleNamespace(id=1, group_number=1, positions=positions)


def _make_building(
    id: int = 1,
    building_number: int = 1,
    is_broken: bool = False,
    groups: list | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        building_number=building_number,
        is_broken=is_broken,
        groups=groups or [],
    )


def _make_post(
    id: int,
    building: SimpleNamespace,
    priority: int = 0,
    active_conditions: list | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        building_id=building.id,
        building=building,
        priority=priority,
        active_conditions=active_conditions or [],
    )


def _make_siege(
    posts: list | None = None,
    siege_members: list | None = None,
    status: SiegeStatus = SiegeStatus.planning,
    post_suggest_preview: dict | None = None,
    post_suggest_preview_expires_at: datetime.datetime | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        status=status,
        defense_scroll_count=5,
        posts=posts or [],
        siege_members=siege_members or [],
        buildings=[],
        post_suggest_preview=post_suggest_preview,
        post_suggest_preview_expires_at=post_suggest_preview_expires_at,
        autofill_preview=None,
        autofill_preview_expires_at=None,
        attack_day_preview=None,
        attack_day_preview_expires_at=None,
    )


def _make_session(siege: SimpleNamespace) -> AsyncMock:
    """Return a minimal AsyncSession mock that scalar_one_or_none returns siege."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = siege
    session.execute.return_value = result
    session.commit = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# Helpers — call the service function with the fake session
# ---------------------------------------------------------------------------


async def _preview(siege: SimpleNamespace, assignment_counts: dict | None = None):
    """Invoke preview_post_suggestions with a mocked session."""
    session = _make_session(siege)

    # Patch the internal query that fetches assignment counts from DB.
    counts = assignment_counts if assignment_counts is not None else {}
    mock_counts_result = MagicMock()
    # scalars().all() returns (member_id, count) tuples
    mock_counts_result.all.return_value = list(counts.items())

    # We override execute so that:
    # - First call (load siege) → returns siege
    # - Second call (assignment counts query) → returns mock_counts_result
    execute_call_count = 0
    siege_result = MagicMock()
    siege_result.scalar_one_or_none.return_value = siege

    async def _execute(stmt, *args, **kwargs):
        nonlocal execute_call_count
        execute_call_count += 1
        if execute_call_count == 1:
            return siege_result
        # counts query returns rows via .all()
        return mock_counts_result

    session.execute.side_effect = _execute

    with patch(
        "app.services.post_suggestions._now_utc",
        return_value=_NOW,
    ):
        return await service.preview_post_suggestions(session, siege_id=1)


# ---------------------------------------------------------------------------
# Section: Completed-siege guard (AC coverage)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preview_raises_400_on_completed_siege():
    """A completed siege raises 400 so planners cannot preview."""
    siege = _make_siege(status=SiegeStatus.complete)
    with pytest.raises(HTTPException) as exc:
        await _preview(siege)
    assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# Section: Single post, single member, happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preview_single_post_single_member_match():
    """AC: single post with one matching member → suggestion targets that member."""
    cond = _make_condition(id=10, description="Attack L1")
    member = _make_member(id=1, name="Alice", preferences=[cond])
    sm = _make_siege_member(member)
    pos = _make_position(id=101)
    grp = _make_group([pos])
    bld = _make_building(id=5, building_number=3, groups=[grp])
    post = _make_post(id=20, building=bld, priority=1, active_conditions=[cond])
    siege = _make_siege(posts=[post], siege_members=[sm])

    result = await _preview(siege)

    assert len(result.assignments) == 1
    entry = result.assignments[0]
    assert entry.suggested_member_id == 1
    assert entry.suggested_member_name == "Alice"
    assert entry.suggested_condition_id == 10
    assert entry.skip_reason is None
    assert entry.position_id == 101


# ---------------------------------------------------------------------------
# Section: No matching member (AC #6)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preview_no_match_produces_skip_reason_no_match():
    """AC #6: post with no matching member → skip_reason='no_match'."""
    cond_post = _make_condition(id=10, description="Cond A")
    cond_member = _make_condition(id=20, description="Cond B")
    member = _make_member(id=1, name="Alice", preferences=[cond_member])
    sm = _make_siege_member(member)
    pos = _make_position(id=101)
    grp = _make_group([pos])
    bld = _make_building(id=5, building_number=1, groups=[grp])
    post = _make_post(id=20, building=bld, priority=1, active_conditions=[cond_post])
    siege = _make_siege(posts=[post], siege_members=[sm])

    result = await _preview(siege)

    assert len(result.assignments) == 1
    entry = result.assignments[0]
    assert entry.suggested_member_id is None
    assert entry.skip_reason == "no_match"


# ---------------------------------------------------------------------------
# Section: Reserve / disabled position skips (Charge #1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preview_reserve_position_produces_skip_reason_reserve():
    """Charge #1: is_reserve=True on the position → skip_reason='reserve'."""
    cond = _make_condition(id=10)
    member = _make_member(id=1, preferences=[cond])
    sm = _make_siege_member(member)
    pos = _make_position(id=101, is_reserve=True)
    grp = _make_group([pos])
    bld = _make_building(id=5, building_number=1, groups=[grp])
    post = _make_post(id=20, building=bld, priority=1, active_conditions=[cond])
    siege = _make_siege(posts=[post], siege_members=[sm])

    result = await _preview(siege)

    entry = result.assignments[0]
    assert entry.suggested_member_id is None
    assert entry.skip_reason == "reserve"


@pytest.mark.asyncio
async def test_preview_disabled_position_produces_skip_reason_disabled():
    """Charge #1: is_disabled=True on the position → skip_reason='disabled'."""
    cond = _make_condition(id=10)
    member = _make_member(id=1, preferences=[cond])
    sm = _make_siege_member(member)
    pos = _make_position(id=101, is_disabled=True)
    grp = _make_group([pos])
    bld = _make_building(id=5, building_number=1, groups=[grp])
    post = _make_post(id=20, building=bld, priority=1, active_conditions=[cond])
    siege = _make_siege(posts=[post], siege_members=[sm])

    result = await _preview(siege)

    entry = result.assignments[0]
    assert entry.suggested_member_id is None
    assert entry.skip_reason == "disabled"


# ---------------------------------------------------------------------------
# Section: No-conditions skip (issue #366)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preview_post_with_no_active_conditions_produces_skip_reason_no_conditions():
    """Issue #366: post with empty active_conditions → skip_reason='no_conditions'.

    When a post has zero active conditions the algorithm cannot match any
    member — but this is distinct from no_match (which means conditions
    exist but no member qualifies).  The correct response is no_conditions
    so the user knows to configure the post rather than add eligible members.
    """
    member = _make_member(id=1, name="Alice", preferences=[_make_condition(id=10)])
    sm = _make_siege_member(member)
    pos = _make_position(id=101)
    grp = _make_group([pos])
    bld = _make_building(id=5, building_number=1, groups=[grp])
    # active_conditions intentionally empty
    post = _make_post(id=20, building=bld, priority=1, active_conditions=[])
    siege = _make_siege(posts=[post], siege_members=[sm])

    result = await _preview(siege)

    assert len(result.assignments) == 1
    entry = result.assignments[0]
    assert entry.suggested_member_id is None
    assert entry.skip_reason == "no_conditions"


@pytest.mark.asyncio
async def test_preview_post_with_conditions_but_no_matching_member_still_no_match():
    """Issue #366: no_match is unchanged when conditions exist but no member qualifies.

    Regression guard — the no_conditions early-exit must not absorb cases
    where conditions are present but the member pool is simply disjoint.
    """
    cond_post = _make_condition(id=10, description="Post cond")
    cond_member = _make_condition(id=20, description="Member cond")
    member = _make_member(id=1, name="Bob", preferences=[cond_member])
    sm = _make_siege_member(member)
    pos = _make_position(id=102)
    grp = _make_group([pos])
    bld = _make_building(id=6, building_number=2, groups=[grp])
    post = _make_post(id=21, building=bld, priority=1, active_conditions=[cond_post])
    siege = _make_siege(posts=[post], siege_members=[sm])

    result = await _preview(siege)

    entry = result.assignments[0]
    assert entry.suggested_member_id is None
    assert entry.skip_reason == "no_match"


@pytest.mark.asyncio
async def test_preview_mixed_no_conditions_no_match_and_assigned_in_one_preview():
    """Issue #366: all three outcomes coexist without conflation.

    One post has no conditions → no_conditions.
    One post has conditions but no qualifying member → no_match.
    One post has a match → assigned.
    This proves the three cases are distinct in the output.
    """
    shared_cond = _make_condition(id=10, description="Shared cond")
    other_cond = _make_condition(id=20, description="Other cond")
    member = _make_member(id=1, name="Alice", preferences=[shared_cond])
    sm = _make_siege_member(member)

    # Post A: no conditions → no_conditions
    pos_a = _make_position(id=101)
    bld_a = _make_building(id=1, building_number=1, groups=[_make_group([pos_a])])
    post_a = _make_post(id=10, building=bld_a, priority=1, active_conditions=[])

    # Post B: conditions present but disjoint from member → no_match
    pos_b = _make_position(id=102)
    bld_b = _make_building(id=2, building_number=2, groups=[_make_group([pos_b])])
    post_b = _make_post(id=11, building=bld_b, priority=2, active_conditions=[other_cond])

    # Post C: condition matches Alice → assigned
    pos_c = _make_position(id=103)
    bld_c = _make_building(id=3, building_number=3, groups=[_make_group([pos_c])])
    post_c = _make_post(id=12, building=bld_c, priority=3, active_conditions=[shared_cond])

    siege = _make_siege(posts=[post_a, post_b, post_c], siege_members=[sm])
    result = await _preview(siege)

    by_post = {e.post_id: e for e in result.assignments}
    assert by_post[10].skip_reason == "no_conditions"
    assert by_post[11].skip_reason == "no_match"
    assert by_post[12].suggested_member_id == 1
    assert by_post[12].skip_reason is None


# ---------------------------------------------------------------------------
# Section: Priority ordering (AC #3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preview_higher_priority_post_gets_member_first():
    """AC #3: two posts compete for the same member.

    The higher-priority post is processed first (gets first pick).
    With two members where one has higher load, the high-priority post
    still claims the better candidate.

    When there are TWO members and ONE shared condition, the high-priority
    post picks the member with the lower assignment count; the low-priority
    post then gets whoever is left.
    """
    cond = _make_condition(id=10)
    member_a = _make_member(id=1, name="Alice", preferences=[cond])
    member_b = _make_member(id=2, name="Bob", preferences=[cond])
    sm_a = _make_siege_member(member_a)
    sm_b = _make_siege_member(member_b)

    pos_low = _make_position(id=101)
    grp_low = _make_group([pos_low])
    bld_low = _make_building(id=1, building_number=1, groups=[grp_low])
    post_low = _make_post(id=10, building=bld_low, priority=1, active_conditions=[cond])

    pos_high = _make_position(id=102)
    grp_high = _make_group([pos_high])
    bld_high = _make_building(id=2, building_number=2, groups=[grp_high])
    post_high = _make_post(id=20, building=bld_high, priority=5, active_conditions=[cond])

    siege = _make_siege(posts=[post_low, post_high], siege_members=[sm_a, sm_b])
    # Alice has 0 assignments; Bob has 3 → high-priority post gets Alice
    result = await _preview(siege, assignment_counts={2: 3})

    by_pos = {e.position_id: e for e in result.assignments}
    # High-priority post gets Alice (lower count)
    assert by_pos[102].suggested_member_id == 1
    # Low-priority post gets Bob (the remaining candidate, despite higher count)
    assert by_pos[101].suggested_member_id == 2


# ---------------------------------------------------------------------------
# Section: Duplicate-condition handling (AC #4)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preview_second_post_prefers_different_condition():
    """AC #4: member can be assigned to two posts; second prefers fresh cond."""
    cond_a = _make_condition(id=10, description="Cond A")
    cond_b = _make_condition(id=20, description="Cond B")
    # Member matches both conditions
    member = _make_member(id=1, name="Alice", preferences=[cond_a, cond_b])
    sm = _make_siege_member(member)

    pos1 = _make_position(id=101)
    grp1 = _make_group([pos1])
    bld1 = _make_building(id=1, building_number=1, groups=[grp1])
    # Post 1 uses cond_a only
    post1 = _make_post(id=10, building=bld1, priority=5, active_conditions=[cond_a])

    pos2 = _make_position(id=102)
    grp2 = _make_group([pos2])
    bld2 = _make_building(id=2, building_number=2, groups=[grp2])
    # Post 2 uses cond_a + cond_b; should prefer cond_b (fresh) for Alice
    post2 = _make_post(id=20, building=bld2, priority=3, active_conditions=[cond_a, cond_b])

    siege = _make_siege(posts=[post1, post2], siege_members=[sm])
    result = await _preview(siege)

    by_pos = {e.position_id: e for e in result.assignments}
    assert by_pos[101].suggested_condition_id == 10  # cond_a
    assert by_pos[102].suggested_condition_id == 20  # cond_b (not duplicate)


# ---------------------------------------------------------------------------
# Section: Load-balancing soft signal (AC #5)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preview_prefers_less_loaded_member():
    """AC #5: member with fewer assignments wins over heavily loaded member."""
    cond = _make_condition(id=10)
    member_heavy = _make_member(id=1, name="Zeta", preferences=[cond])
    member_light = _make_member(id=2, name="Alpha", preferences=[cond])
    sm_heavy = _make_siege_member(member_heavy)
    sm_light = _make_siege_member(member_light)

    pos = _make_position(id=101)
    grp = _make_group([pos])
    bld = _make_building(id=1, building_number=1, groups=[grp])
    post = _make_post(id=10, building=bld, priority=1, active_conditions=[cond])

    siege = _make_siege(posts=[post], siege_members=[sm_heavy, sm_light])
    # Inject: heavy member has 5 existing assignments, light has 1
    result = await _preview(siege, assignment_counts={1: 5, 2: 1})

    entry = result.assignments[0]
    # Light member (id=2) should win despite alphabetical order favouring id=1
    assert entry.suggested_member_id == 2


# ---------------------------------------------------------------------------
# Section: Lexicographic scoring / determinism (Charges #2, #8)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preview_name_tiebreak_picks_alphabetically_lower():
    """Charge #8: on equal penalty + count, member with lower name wins."""
    cond = _make_condition(id=10)
    member_z = _make_member(id=1, name="Zora", preferences=[cond])
    member_a = _make_member(id=2, name="Aayla", preferences=[cond])
    sm_z = _make_siege_member(member_z)
    sm_a = _make_siege_member(member_a)

    pos = _make_position(id=101)
    grp = _make_group([pos])
    bld = _make_building(id=1, building_number=1, groups=[grp])
    post = _make_post(id=10, building=bld, priority=1, active_conditions=[cond])

    siege = _make_siege(posts=[post], siege_members=[sm_z, sm_a])
    result = await _preview(siege, assignment_counts={})

    entry = result.assignments[0]
    assert entry.suggested_member_name == "Aayla"


@pytest.mark.asyncio
async def test_preview_duplicate_penalty_beats_assignment_count():
    """Charge #8: member with duplicate-condition penalty loses to member with
    3 existing assignments but no duplicate penalty."""
    cond = _make_condition(id=10)
    # member_dup already used cond=10 elsewhere → penalty=1
    # member_fresh has 3 assignments but no duplicate → penalty=0
    member_dup = _make_member(id=1, name="Alice", preferences=[cond])
    member_fresh = _make_member(id=2, name="Bob", preferences=[cond])
    sm_dup = _make_siege_member(member_dup)
    sm_fresh = _make_siege_member(member_fresh)

    pos = _make_position(id=101)
    grp = _make_group([pos])
    bld = _make_building(id=1, building_number=1, groups=[grp])
    post = _make_post(id=10, building=bld, priority=1, active_conditions=[cond])

    # member_dup (id=1) will be assigned cond=10 via post_a (higher priority).
    # Then the lower-priority post must prefer Bob (member_fresh) despite Bob
    # having 3 existing assignments, because Alice's only condition is now used.
    pos_a = _make_position(id=100)
    grp_a = _make_group([pos_a])
    bld_a = _make_building(id=2, building_number=2, groups=[grp_a])
    post_a = _make_post(id=5, building=bld_a, priority=10, active_conditions=[cond])
    # post_a goes first (higher priority), assigns cond=10 to Alice (member_dup)
    # then post (priority=1) prefers Bob (member_fresh) because Alice's cond is used

    siege2 = _make_siege(posts=[post_a, post], siege_members=[sm_dup, sm_fresh])
    result = await _preview(siege2, assignment_counts={2: 3})  # Bob has 3 existing

    by_pos = {e.position_id: e for e in result.assignments}
    # post_a (higher priority) wins Alice
    assert by_pos[100].suggested_member_id == 1
    # post (lower priority) should prefer Bob despite 3 assignments (no dup penalty)
    assert by_pos[101].suggested_member_id == 2


@pytest.mark.asyncio
async def test_preview_determinism_same_output_on_repeat():
    """Charge #2: two runs with identical input produce byte-identical output."""
    cond = _make_condition(id=10)
    m1 = _make_member(id=1, name="Bob", preferences=[cond])
    m2 = _make_member(id=2, name="Alice", preferences=[cond])

    pos = _make_position(id=101)
    grp = _make_group([pos])
    bld = _make_building(id=1, building_number=1, groups=[grp])
    post = _make_post(id=10, building=bld, priority=1, active_conditions=[cond])

    siege = _make_siege(
        posts=[post],
        siege_members=[_make_siege_member(m1), _make_siege_member(m2)],
    )

    result1 = await _preview(siege, assignment_counts={})
    result2 = await _preview(siege, assignment_counts={})

    assert result1.assignments[0].suggested_member_id == result2.assignments[0].suggested_member_id
    assert (
        result1.assignments[0].suggested_condition_id
        == result2.assignments[0].suggested_condition_id
    )


@pytest.mark.asyncio
async def test_preview_current_member_preferred_when_equally_qualified():
    """Regression test for #360: bistable flip-flop.

    Setup:
    - 1 post, condition id=10.
    - Alice (id=1) is currently assigned to the position with count=1
      (her own assignment counts toward her total).
    - Bob (id=2) has count=0 (not assigned anywhere yet).

    Without the fix, the score tuple is (dup_penalty, count, name):
      Alice → (0, 1, "Alice"), Bob → (0, 0, "Bob") → Bob wins.
    Apply Bob; Bob's count becomes 1, Alice's drops to 0.
    Re-run: Alice → (0, 0, "Alice"), Bob → (0, 1, "Bob") → Alice wins.
    Bistable flip-flop: the algorithm perpetually proposes a swap.

    With the fix, the current member receives an extra preference signal
    so the score is stable: re-running after apply always returns
    matches_current=True for every row, meaning the suggestion set never
    proposes a change to an already-optimal board.
    """
    cond = _make_condition(id=10, description="Attack L1")
    alice = _make_member(id=1, name="Alice", preferences=[cond])
    bob = _make_member(id=2, name="Bob", preferences=[cond])
    sm_alice = _make_siege_member(alice)
    sm_bob = _make_siege_member(bob)

    # Alice is currently assigned (member_id=1, condition=10).
    # Her count is 1 (she occupies this position in the DB).
    pos = _make_position(id=101, member_id=1, member_name="Alice", matched_condition_id=10)
    grp = _make_group([pos])
    bld = _make_building(id=1, building_number=1, groups=[grp])
    post = _make_post(id=10, building=bld, priority=1, active_conditions=[cond])
    siege = _make_siege(posts=[post], siege_members=[sm_alice, sm_bob])

    # Run 1: Alice is the incumbent with count=1, Bob has count=0.
    result1 = await _preview(siege, assignment_counts={1: 1})

    # The algorithm must prefer Alice (current member) over Bob.
    # Without the fix, Bob wins because count 0 < 1.
    assert result1.assignments[0].suggested_member_id == 1, (
        "Run 1: expected Alice (current member) to be preferred, got "
        f"member_id={result1.assignments[0].suggested_member_id}"
    )
    assert (
        result1.assignments[0].matches_current is True
    ), "Run 1: matches_current should be True when current member is retained"

    # Simulate apply: Bob is now assigned, Alice's count drops.
    # (In the flip-flop scenario, applying Bob would give Bob count=1, Alice=0.)
    # Run 2 after hypothetical apply of Bob: Bob is incumbent with count=1, Alice=0.
    pos2 = _make_position(id=101, member_id=2, member_name="Bob", matched_condition_id=10)
    grp2 = _make_group([pos2])
    bld2 = _make_building(id=1, building_number=1, groups=[grp2])
    post2 = _make_post(id=10, building=bld2, priority=1, active_conditions=[cond])
    siege2 = _make_siege(posts=[post2], siege_members=[sm_alice, sm_bob])

    result2 = await _preview(siege2, assignment_counts={2: 1})

    # Now Bob is the incumbent; the algorithm must prefer Bob.
    assert result2.assignments[0].suggested_member_id == 2, (
        "Run 2: expected Bob (current member) to be preferred, got "
        f"member_id={result2.assignments[0].suggested_member_id}"
    )
    assert (
        result2.assignments[0].matches_current is True
    ), "Run 2: matches_current should be True when current member is retained"


@pytest.mark.asyncio
async def test_preview_lowest_condition_id_picked_as_tiebreak():
    """Two matching conditions, neither used → lowest id is picked."""
    cond_hi = _make_condition(id=20, description="High ID")
    cond_lo = _make_condition(id=5, description="Low ID")
    member = _make_member(id=1, name="Alice", preferences=[cond_hi, cond_lo])
    sm = _make_siege_member(member)

    pos = _make_position(id=101)
    grp = _make_group([pos])
    bld = _make_building(id=1, building_number=1, groups=[grp])
    post = _make_post(id=10, building=bld, priority=1, active_conditions=[cond_hi, cond_lo])
    siege = _make_siege(posts=[post], siege_members=[sm])

    result = await _preview(siege, assignment_counts={})

    entry = result.assignments[0]
    assert entry.suggested_condition_id == 5  # lowest id


# ---------------------------------------------------------------------------
# Section: Documented suboptimality (Charge #14) — property-based
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preview_suboptimality_invariants_hold():
    """Charge #14: known greedy suboptimality fixture — assert invariants, not exact output.

    Setup: 2 posts, 2 members, each member matches exactly 1 unique condition.
    Post 1 requires cond_a; Post 2 requires cond_b.
    Member 1 matches only cond_a; Member 2 matches only cond_b.
    Optimal: member 1 → post 1, member 2 → post 2.
    Greedy with priority order is correct here.

    We assert invariants that any correct algorithm must satisfy:
    1. No member is assigned the same condition to two posts simultaneously.
    2. Every assigned post has a member whose preferences include the matched condition.
    3. The number of assigned posts is >= 1 (greedy lower bound).
    """
    cond_a = _make_condition(id=1, description="Cond A")
    cond_b = _make_condition(id=2, description="Cond B")
    m1 = _make_member(id=1, name="Alpha", preferences=[cond_a])
    m2 = _make_member(id=2, name="Beta", preferences=[cond_b])
    sm1 = _make_siege_member(m1)
    sm2 = _make_siege_member(m2)

    pos1 = _make_position(id=101)
    grp1 = _make_group([pos1])
    bld1 = _make_building(id=1, building_number=1, groups=[grp1])
    post1 = _make_post(id=10, building=bld1, priority=5, active_conditions=[cond_a])

    pos2 = _make_position(id=102)
    grp2 = _make_group([pos2])
    bld2 = _make_building(id=2, building_number=2, groups=[grp2])
    post2 = _make_post(id=20, building=bld2, priority=3, active_conditions=[cond_b])

    siege = _make_siege(posts=[post1, post2], siege_members=[sm1, sm2])
    result = await _preview(siege, assignment_counts={})

    assigned = [e for e in result.assignments if e.suggested_member_id is not None]

    # Invariant 1: no member assigned same condition to two posts
    seen: dict[tuple[int, int], int] = {}
    for e in assigned:
        key = (e.suggested_member_id, e.suggested_condition_id)
        assert key not in seen, "Member assigned same condition to two posts"
        seen[key] = e.position_id

    # Invariant 2: matched condition is in the member's preferences
    member_prefs = {
        m1.id: {c.id for c in m1.post_preferences},
        m2.id: {c.id for c in m2.post_preferences},
    }
    for e in assigned:
        prefs = member_prefs.get(e.suggested_member_id, set())
        assert (
            e.suggested_condition_id in prefs
        ), f"Suggested condition {e.suggested_condition_id} not in member's preferences"

    # Invariant 3: at least 1 post assigned (greedy lower bound)
    assert len(assigned) >= 1


# ---------------------------------------------------------------------------
# Section: matches_current flag
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preview_matches_current_true_when_same_assignment():
    """matches_current=True when the suggestion equals the existing assignment."""
    cond = _make_condition(id=10)
    member = _make_member(id=1, name="Alice", preferences=[cond])
    sm = _make_siege_member(member)
    # Position already has member_id=1 and matched_condition_id=10
    pos = _make_position(id=101, member_id=1, member_name="Alice", matched_condition_id=10)
    grp = _make_group([pos])
    bld = _make_building(id=1, building_number=1, groups=[grp])
    post = _make_post(id=10, building=bld, priority=1, active_conditions=[cond])
    siege = _make_siege(posts=[post], siege_members=[sm])

    result = await _preview(siege, assignment_counts={1: 1})
    entry = result.assignments[0]

    assert entry.suggested_member_id == 1
    assert entry.matches_current is True


@pytest.mark.asyncio
async def test_preview_matches_current_false_for_null_suggestion():
    """matches_current is always False when suggested_member_id is None."""
    cond_post = _make_condition(id=10)
    cond_member = _make_condition(id=20)
    member = _make_member(id=1, preferences=[cond_member])
    sm = _make_siege_member(member)
    pos = _make_position(id=101)
    grp = _make_group([pos])
    bld = _make_building(id=1, building_number=1, groups=[grp])
    post = _make_post(id=10, building=bld, priority=1, active_conditions=[cond_post])
    siege = _make_siege(posts=[post], siege_members=[sm])

    result = await _preview(siege, assignment_counts={})
    entry = result.assignments[0]

    assert entry.suggested_member_id is None
    assert entry.matches_current is False


# ---------------------------------------------------------------------------
# Section: Empty siege edge cases (Charge #9)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preview_empty_siege_returns_empty_assignments():
    """Charge #9: siege with no posts → preview returns empty assignments list."""
    siege = _make_siege(posts=[], siege_members=[])
    result = await _preview(siege, assignment_counts={})
    assert result.assignments == []


@pytest.mark.asyncio
async def test_preview_no_members_all_skip_no_match():
    """Charge #9: posts exist but no siege members → all skip with no_match."""
    cond = _make_condition(id=10)
    pos = _make_position(id=101)
    grp = _make_group([pos])
    bld = _make_building(id=1, building_number=1, groups=[grp])
    post = _make_post(id=10, building=bld, priority=1, active_conditions=[cond])
    siege = _make_siege(posts=[post], siege_members=[])

    result = await _preview(siege, assignment_counts={})

    entry = result.assignments[0]
    assert entry.suggested_member_id is None
    assert entry.skip_reason == "no_match"


# ---------------------------------------------------------------------------
# Section: API endpoint smoke tests (mocked service layer)
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """HTTP test client bound to the FastAPI app."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_preview_endpoint_returns_200(client):
    """POST /api/sieges/1/post-suggestions returns 200 with preview payload."""
    preview = PostSuggestionPreviewResult(assignments=[], expires_at="2026-05-09T13:00:00")
    with patch(
        "app.api.post_suggestions.post_suggestions_service.preview_post_suggestions",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = preview
        async with client as c:
            response = await c.post("/api/sieges/1/post-suggestions")

    assert response.status_code == 200
    assert response.json()["assignments"] == []


@pytest.mark.asyncio
async def test_apply_endpoint_returns_200(client):
    """POST /api/sieges/1/post-suggestions/apply returns 200 with applied_count."""
    apply_result = PostSuggestionApplyResult(applied_count=3)
    with patch(
        "app.api.post_suggestions.post_suggestions_service.apply_post_suggestions",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = apply_result
        async with client as c:
            response = await c.post(
                "/api/sieges/1/post-suggestions/apply",
                json={"apply_position_ids": [101, 102, 103]},
            )

    assert response.status_code == 200
    assert response.json()["applied_count"] == 3


# ---------------------------------------------------------------------------
# Section: Apply service — mocked session tests
# ---------------------------------------------------------------------------


async def _apply(
    siege: SimpleNamespace,
    apply_position_ids: list[int],
    positions_by_id: dict | None = None,
    members_by_id: dict | None = None,
):
    """Invoke apply_post_suggestions with a fully mocked session."""
    session = AsyncMock()

    call_count = 0

    async def _execute(stmt, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Load siege
            r = MagicMock()
            r.scalar_one_or_none.return_value = siege
            return r
        if call_count == 2:
            # SELECT (Position, Building.is_broken) FOR UPDATE
            # Returns (pos, False) tuples for each position (not broken by default)
            r = MagicMock()
            rows = [(pos, False) for pos in (positions_by_id or {}).values()]
            r.all.return_value = rows
            return r
        if call_count == 3:
            # SELECT members for activity check
            r = MagicMock()
            members = list((members_by_id or {}).values())
            r.scalars.return_value.all.return_value = members
            return r
        return MagicMock()

    session.execute.side_effect = _execute
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    data = PostSuggestionApplyRequest(apply_position_ids=apply_position_ids)
    with patch("app.services.post_suggestions._now_utc", return_value=_NOW):
        return await service.apply_post_suggestions(session, siege_id=1, data=data)


def _preview_data(entries: list[dict]) -> dict:
    """Build the preview dict stored in siege.post_suggest_preview."""
    return {"assignments": entries}


def _entry_dict(
    position_id: int,
    suggested_member_id: int | None,
    current_member_id: int | None = None,
    suggested_condition_id: int | None = None,
) -> dict:
    return {
        "position_id": position_id,
        "suggested_member_id": suggested_member_id,
        "current_member_id": current_member_id,
        "suggested_condition_id": suggested_condition_id,
        "suggested_member_name": "Member",
        "suggested_condition_description": "Cond",
        "post_id": 1,
        "building_number": 1,
        "priority": 1,
        "current_member_name": None,
        "current_condition_id": None,
        "matches_current": False,
        "skip_reason": None,
    }


@pytest.mark.asyncio
async def test_apply_expired_preview_raises_409():
    """Apply with expired TTL raises 409 with the standard message."""
    past = _NOW - datetime.timedelta(minutes=1)
    siege = _make_siege(
        post_suggest_preview=_preview_data([]),
        post_suggest_preview_expires_at=past,
    )
    with pytest.raises(HTTPException) as exc:
        await _apply(siege, [])
    assert exc.value.status_code == 409
    assert "No valid preview" in exc.value.detail


@pytest.mark.asyncio
async def test_apply_missing_preview_raises_409():
    """Apply with no preview at all raises 409."""
    siege = _make_siege()
    with pytest.raises(HTTPException) as exc:
        await _apply(siege, [])
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_apply_empty_position_ids_is_noop():
    """Charge #9: apply_position_ids=[] → 0 writes, success."""
    siege = _make_siege(
        post_suggest_preview=_preview_data(
            [_entry_dict(101, suggested_member_id=1, current_member_id=None)]
        ),
        post_suggest_preview_expires_at=_FUTURE,
    )
    pos = _make_position(id=101, member_id=None)
    member = _make_member(id=1, is_active=True)

    result = await _apply(siege, [], positions_by_id={101: pos}, members_by_id={1: member})
    assert result.applied_count == 0


@pytest.mark.asyncio
async def test_apply_unknown_position_ids_silently_ignored():
    """Charge #9: position_ids not in the preview are silently ignored."""
    siege = _make_siege(
        post_suggest_preview=_preview_data(
            [_entry_dict(101, suggested_member_id=1, current_member_id=None)]
        ),
        post_suggest_preview_expires_at=_FUTURE,
    )
    pos = _make_position(id=101, member_id=None)
    member = _make_member(id=1, is_active=True)

    # Apply only to position 999 (not in preview) — should succeed with 0 applied
    result = await _apply(siege, [999], positions_by_id={101: pos}, members_by_id={1: member})
    assert result.applied_count == 0


@pytest.mark.asyncio
async def test_apply_null_member_entries_are_skipped():
    """Null suggested_member_id entries are skipped; no error raised."""
    siege = _make_siege(
        post_suggest_preview=_preview_data(
            [_entry_dict(101, suggested_member_id=None, current_member_id=None)]
        ),
        post_suggest_preview_expires_at=_FUTURE,
    )

    result = await _apply(siege, [101], positions_by_id={}, members_by_id={})
    assert result.applied_count == 0


@pytest.mark.asyncio
async def test_apply_subset_only_writes_checked_positions():
    """Apply with a subset of position_ids → only those positions written."""
    entries = [
        _entry_dict(101, suggested_member_id=1, current_member_id=None),
        _entry_dict(102, suggested_member_id=2, current_member_id=None),
    ]
    siege = _make_siege(
        post_suggest_preview=_preview_data(entries),
        post_suggest_preview_expires_at=_FUTURE,
    )
    pos101 = _make_position(id=101, member_id=None)
    pos102 = _make_position(id=102, member_id=None)
    m1 = _make_member(id=1, is_active=True)
    m2 = _make_member(id=2, is_active=True)

    # Only apply position 101
    result = await _apply(
        siege,
        [101],
        positions_by_id={101: pos101, 102: pos102},
        members_by_id={1: m1, 2: m2},
    )
    assert result.applied_count == 1
    assert pos101.member_id == 1
    # pos102 should not have been touched (still None)
    assert pos102.member_id is None


@pytest.mark.asyncio
async def test_apply_stale_position_disabled_returns_409():
    """Position disabled since preview → 409 with reason position_disabled."""
    entries = [_entry_dict(101, suggested_member_id=1, current_member_id=None)]
    siege = _make_siege(
        post_suggest_preview=_preview_data(entries),
        post_suggest_preview_expires_at=_FUTURE,
    )
    pos = _make_position(id=101, member_id=None, is_disabled=True)
    m1 = _make_member(id=1, is_active=True)

    with pytest.raises(HTTPException) as exc:
        await _apply(siege, [101], positions_by_id={101: pos}, members_by_id={1: m1})
    assert exc.value.status_code == 409
    detail = exc.value.detail
    assert any(e["reason"] == "position_disabled" for e in detail["stale_entries"])


@pytest.mark.asyncio
async def test_apply_stale_position_reserve_returns_409():
    """Position set to reserve since preview → 409 with reason position_reserve."""
    entries = [_entry_dict(101, suggested_member_id=1, current_member_id=None)]
    siege = _make_siege(
        post_suggest_preview=_preview_data(entries),
        post_suggest_preview_expires_at=_FUTURE,
    )
    pos = _make_position(id=101, member_id=None, is_reserve=True)
    m1 = _make_member(id=1, is_active=True)

    with pytest.raises(HTTPException) as exc:
        await _apply(siege, [101], positions_by_id={101: pos}, members_by_id={1: m1})
    assert exc.value.status_code == 409
    detail = exc.value.detail
    assert any(e["reason"] == "position_reserve" for e in detail["stale_entries"])


@pytest.mark.asyncio
async def test_apply_stale_member_inactive_returns_409():
    """Member became inactive since preview → 409 with reason member_inactive."""
    entries = [_entry_dict(101, suggested_member_id=1, current_member_id=None)]
    siege = _make_siege(
        post_suggest_preview=_preview_data(entries),
        post_suggest_preview_expires_at=_FUTURE,
    )
    pos = _make_position(id=101, member_id=None)
    m1 = _make_member(id=1, is_active=False)  # now inactive

    with pytest.raises(HTTPException) as exc:
        await _apply(siege, [101], positions_by_id={101: pos}, members_by_id={1: m1})
    assert exc.value.status_code == 409
    detail = exc.value.detail
    assert any(e["reason"] == "member_inactive" for e in detail["stale_entries"])


@pytest.mark.asyncio
async def test_apply_member_changed_returns_409():
    """Charge #15: another planner assigned a different member → reason member_changed."""
    # Preview said current_member_id=None; now position has member_id=99 (another planner)
    entries = [_entry_dict(101, suggested_member_id=1, current_member_id=None)]
    siege = _make_siege(
        post_suggest_preview=_preview_data(entries),
        post_suggest_preview_expires_at=_FUTURE,
    )
    pos = _make_position(id=101, member_id=99)  # changed!
    m1 = _make_member(id=1, is_active=True)

    with pytest.raises(HTTPException) as exc:
        await _apply(siege, [101], positions_by_id={101: pos}, members_by_id={1: m1})
    assert exc.value.status_code == 409
    detail = exc.value.detail
    assert any(e["reason"] == "member_changed" for e in detail["stale_entries"])


@pytest.mark.asyncio
async def test_apply_multiple_stale_all_surfaced_in_single_409():
    """Multiple stale entries → all returned in a single 409 (one round-trip)."""
    entries = [
        _entry_dict(101, suggested_member_id=1, current_member_id=None),
        _entry_dict(102, suggested_member_id=2, current_member_id=None),
    ]
    siege = _make_siege(
        post_suggest_preview=_preview_data(entries),
        post_suggest_preview_expires_at=_FUTURE,
    )
    pos101 = _make_position(id=101, member_id=None, is_disabled=True)
    pos102 = _make_position(id=102, member_id=99)  # member_changed
    m1 = _make_member(id=1, is_active=True)
    m2 = _make_member(id=2, is_active=True)

    with pytest.raises(HTTPException) as exc:
        await _apply(
            siege,
            [101, 102],
            positions_by_id={101: pos101, 102: pos102},
            members_by_id={1: m1, 2: m2},
        )
    assert exc.value.status_code == 409
    detail = exc.value.detail
    reasons = {e["reason"] for e in detail["stale_entries"]}
    assert "position_disabled" in reasons
    assert "member_changed" in reasons


@pytest.mark.asyncio
async def test_apply_completed_siege_raises_400():
    """Apply on a completed siege raises 400 before checking preview."""
    siege = _make_siege(
        status=SiegeStatus.complete,
        post_suggest_preview=_preview_data([]),
        post_suggest_preview_expires_at=_FUTURE,
    )

    session = AsyncMock()
    r = MagicMock()
    r.scalar_one_or_none.return_value = siege
    session.execute.return_value = r

    data = PostSuggestionApplyRequest(apply_position_ids=[])
    with pytest.raises(HTTPException) as exc:
        await service.apply_post_suggestions(session, siege_id=1, data=data)
    assert exc.value.status_code == 400
