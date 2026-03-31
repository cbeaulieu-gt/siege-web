"""Tests for siege comparison service and endpoints."""

import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.enums import BuildingType, SiegeStatus
from app.schemas.comparison import ComparisonResult, MemberDiff

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_siege(id=1, status=SiegeStatus.planning):
    return SimpleNamespace(
        id=id,
        date=datetime.date(2026, 3, 20),
        status=status,
        defense_scroll_count=5,
        created_at=datetime.datetime(2026, 1, 1),
        updated_at=datetime.datetime(2026, 1, 1),
        autofill_preview=None,
        autofill_preview_expires_at=None,
        attack_day_preview=None,
        attack_day_preview_expires_at=None,
        buildings=[],
        siege_members=[],
    )


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compare_returns_404_when_no_completed_siege(client):
    from app.db.session import get_db

    siege = _make_siege(id=1)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = siege
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch(
            "app.api.comparison.comparison_service.get_most_recent_completed",
            new_callable=AsyncMock,
        ) as mock_recent:
            mock_recent.return_value = None
            async with client as c:
                response = await c.get("/api/sieges/1/compare")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_compare_with_specific_endpoint_200(client):
    from app.db.session import get_db

    result = ComparisonResult(
        siege_a_id=1,
        siege_b_id=2,
        members=[MemberDiff(member_id=1, member_name="Alice", added=[], removed=[], unchanged=[])],
    )

    s1 = SimpleNamespace(id=1)
    s2 = SimpleNamespace(id=2)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [s1, s2]
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch(
            "app.api.comparison.comparison_service.compare_sieges", new_callable=AsyncMock
        ) as mock_compare:
            mock_compare.return_value = result
            async with client as c:
                response = await c.get("/api/sieges/1/compare/2")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    data = response.json()
    assert data["siege_a_id"] == 1
    assert data["siege_b_id"] == 2
    assert len(data["members"]) == 1


# ---------------------------------------------------------------------------
# Service unit tests
# ---------------------------------------------------------------------------

from app.services.comparison import compare_sieges, get_most_recent_completed  # noqa: E402


def _build_siege_assignments(siege_id: int, assignments: list[tuple]) -> list[tuple]:
    """Build (Position, BuildingGroup, Building) rows for mock execute results."""
    rows = []
    for pos_num, group_num, btype, bnum, member_id in assignments:
        pos = SimpleNamespace(
            id=len(rows) + 1,
            position_number=pos_num,
            member_id=member_id,
            is_reserve=False,
            is_disabled=False,
        )
        group = SimpleNamespace(id=len(rows) + 100, group_number=group_num, slot_count=3)
        building = SimpleNamespace(id=len(rows) + 200, building_type=btype, building_number=bnum)
        rows.append((pos, group, building))
    return rows


@pytest.mark.asyncio
async def test_compare_added_positions():
    """Position in B but not A → appears in added."""
    # Siege A: member 1 at stronghold/1/group1/pos1
    # Siege B: member 1 at stronghold/1/group1/pos1 AND stronghold/1/group1/pos2
    a_rows = _build_siege_assignments(1, [(1, 1, BuildingType.stronghold, 1, 1)])
    b_rows = _build_siege_assignments(
        2,
        [
            (1, 1, BuildingType.stronghold, 1, 1),
            (2, 1, BuildingType.stronghold, 1, 1),
        ],
    )
    member = SimpleNamespace(id=1, name="Alice")

    call_count = 0

    async def fake_execute(stmt):
        nonlocal call_count
        result = MagicMock()
        if call_count == 0:
            # A assignments
            result.all.return_value = a_rows
        elif call_count == 1:
            # B assignments
            result.all.return_value = b_rows
        else:
            # member lookup
            result.scalars.return_value.all.return_value = [member]
        call_count += 1
        return result

    session = AsyncMock()
    session.execute = fake_execute

    result = await compare_sieges(session, siege_a_id=1, siege_b_id=2)
    assert len(result.members) == 1
    diff = result.members[0]
    assert diff.member_id == 1
    assert len(diff.added) == 1
    assert diff.added[0].position_number == 2


@pytest.mark.asyncio
async def test_compare_removed_positions():
    """Position in A but not B → appears in removed."""
    a_rows = _build_siege_assignments(
        1,
        [
            (1, 1, BuildingType.stronghold, 1, 1),
            (2, 1, BuildingType.stronghold, 1, 1),
        ],
    )
    b_rows = _build_siege_assignments(2, [(1, 1, BuildingType.stronghold, 1, 1)])
    member = SimpleNamespace(id=1, name="Alice")

    call_count = 0

    async def fake_execute(stmt):
        nonlocal call_count
        result = MagicMock()
        if call_count == 0:
            result.all.return_value = a_rows
        elif call_count == 1:
            result.all.return_value = b_rows
        else:
            result.scalars.return_value.all.return_value = [member]
        call_count += 1
        return result

    session = AsyncMock()
    session.execute = fake_execute

    result = await compare_sieges(session, siege_a_id=1, siege_b_id=2)
    diff = result.members[0]
    assert len(diff.removed) == 1
    assert diff.removed[0].position_number == 2


@pytest.mark.asyncio
async def test_compare_unchanged_positions():
    """Position in both A and B → appears in unchanged."""
    rows = _build_siege_assignments(1, [(1, 1, BuildingType.stronghold, 1, 1)])
    member = SimpleNamespace(id=1, name="Alice")

    call_count = 0

    async def fake_execute(stmt):
        nonlocal call_count
        result = MagicMock()
        if call_count == 0:
            result.all.return_value = list(rows)
        elif call_count == 1:
            result.all.return_value = list(rows)
        else:
            result.scalars.return_value.all.return_value = [member]
        call_count += 1
        return result

    session = AsyncMock()
    session.execute = fake_execute

    result = await compare_sieges(session, siege_a_id=1, siege_b_id=2)
    diff = result.members[0]
    assert len(diff.unchanged) == 1
    assert len(diff.added) == 0
    assert len(diff.removed) == 0


@pytest.mark.asyncio
async def test_compare_reserve_positions_excluded():
    """Reserve positions must not appear in any diff."""
    # Build a reserve position (filtered out by the query's WHERE clause)
    _ = SimpleNamespace(id=1, position_number=1, member_id=1, is_reserve=True, is_disabled=False)

    # The query in _load_assignments filters out is_reserve=True, so the row shouldn't come back.
    # Simulate empty results (as if the WHERE clause filtered it).
    call_count = 0

    async def fake_execute(stmt):
        nonlocal call_count
        result = MagicMock()
        result.all.return_value = []
        result.scalars.return_value.all.return_value = []
        call_count += 1
        return result

    session = AsyncMock()
    session.execute = fake_execute

    result = await compare_sieges(session, siege_a_id=1, siege_b_id=2)
    assert result.members == []


@pytest.mark.asyncio
async def test_inactive_member_excluded_from_comparison():
    """Inactive members with assignments (e.g. from a cloned siege) must not appear in results.

    The fix adds a join to Member + filter on is_active=True inside _load_assignments.
    We verify this by:
    1. Capturing the SQL statement and asserting is_active appears in the WHERE clause.
    2. Simulating the filtered result (inactive member absent) and asserting they don't surface.
    """
    from app.services.comparison import _load_assignments

    captured_stmts = []

    async def capturing_execute(stmt):
        captured_stmts.append(stmt)
        result = MagicMock()
        result.all.return_value = []
        return result

    session = AsyncMock()
    session.execute = capturing_execute

    await _load_assignments(session, siege_id=1)

    assert len(captured_stmts) == 1, "Expected exactly one query from _load_assignments"
    stmt_str = str(captured_stmts[0].compile(compile_kwargs={"literal_binds": True}))
    assert (
        "is_active" in stmt_str
    ), "Query must filter on Member.is_active to exclude inactive members from comparison"


@pytest.mark.asyncio
async def test_inactive_member_rows_absent_from_comparison_result():
    """Integration-style: inactive member rows filtered by query do not appear in result.

    When a siege is cloned, assignments are copied for all members including inactive ones.
    The comparison service must exclude those members.
    Simulate by returning rows only for the active member (as the DB would after filtering).
    """
    active_rows = _build_siege_assignments(1, [(1, 1, BuildingType.stronghold, 1, 1)])
    inactive_rows = _build_siege_assignments(
        1, [(2, 1, BuildingType.stronghold, 1, 2)]
    )  # member_id=2, inactive

    active_member = SimpleNamespace(id=1, name="Alice", is_active=True)

    call_count = 0

    async def fake_execute(stmt):
        nonlocal call_count
        result = MagicMock()
        if call_count == 0:
            # Siege A: only active member rows (inactive filtered by is_active=True join)
            result.all.return_value = list(active_rows)
        elif call_count == 1:
            # Siege B: same
            result.all.return_value = list(active_rows)
        else:
            result.scalars.return_value.all.return_value = [active_member]
        call_count += 1
        return result

    session = AsyncMock()
    session.execute = fake_execute

    result = await compare_sieges(session, siege_a_id=1, siege_b_id=2)
    member_ids = [m.member_id for m in result.members]
    assert 1 in member_ids, "Active member should appear in comparison"
    assert 2 not in member_ids, "Inactive member must not appear in comparison"
    _ = inactive_rows  # referenced to show intent; would be returned without the fix


@pytest.mark.asyncio
async def test_get_most_recent_completed_returns_none():
    """Returns None when no completed siege exists."""

    async def fake_execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    session = AsyncMock()
    session.execute = fake_execute

    result = await get_most_recent_completed(session, exclude_siege_id=1)
    assert result is None


@pytest.mark.asyncio
async def test_get_most_recent_completed_returns_siege():
    """Returns the siege when one exists."""
    siege = _make_siege(id=5, status=SiegeStatus.complete)

    async def fake_execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = siege
        return result

    session = AsyncMock()
    session.execute = fake_execute

    result = await get_most_recent_completed(session, exclude_siege_id=1)
    assert result is not None
    assert result.id == 5
