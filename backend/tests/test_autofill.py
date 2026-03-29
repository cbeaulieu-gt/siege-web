"""Tests for auto-fill preview and apply."""

import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.enums import BuildingType, MemberRole, SiegeStatus
from app.schemas.autofill import AutofillApplyResult, AutofillAssignment, AutofillPreviewResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_siege(id=1, defense_scroll_count=5):
    return SimpleNamespace(
        id=id,
        date=datetime.date(2026, 3, 20),
        status=SiegeStatus.planning,
        defense_scroll_count=defense_scroll_count,
        created_at=datetime.datetime(2026, 1, 1),
        updated_at=datetime.datetime(2026, 1, 1),
        autofill_preview=None,
        autofill_preview_expires_at=None,
        attack_day_preview=None,
        attack_day_preview_expires_at=None,
        buildings=[],
        siege_members=[],
    )


def _make_member(id, name="M", is_active=True):
    return SimpleNamespace(
        id=id, name=name, role=MemberRole.advanced, is_active=is_active, power=None
    )


def _make_building(id=1):
    return SimpleNamespace(
        id=id,
        siege_id=1,
        building_type=BuildingType.stronghold,
        building_number=1,
        level=1,
        is_broken=False,
        groups=[],
    )


def _make_group(id=1, slot_count=3):
    return SimpleNamespace(
        id=id, building_id=1, group_number=1, slot_count=slot_count, positions=[]
    )


def _make_position(id, position_number=1, member_id=None, is_reserve=False, is_disabled=False):
    return SimpleNamespace(
        id=id,
        building_group_id=1,
        position_number=position_number,
        member_id=member_id,
        is_reserve=is_reserve,
        is_disabled=is_disabled,
        member=None,
    )


def _make_sm(member_id, member=None):
    return SimpleNamespace(
        siege_id=1,
        member_id=member_id,
        attack_day=1,
        has_reserve_set=True,
        attack_day_override=False,
        member=member,
    )


# ---------------------------------------------------------------------------
# API fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# Endpoint tests (mocking service layer)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preview_endpoint_returns_200(client):
    preview = AutofillPreviewResult(
        assignments=[AutofillAssignment(position_id=1, member_id=2, is_reserve=False)],
        expires_at="2026-03-17T12:00:00+00:00",
    )
    with patch(
        "app.api.autofill.autofill_service.preview_autofill", new_callable=AsyncMock
    ) as mock:
        mock.return_value = preview
        async with client as c:
            response = await c.post("/api/sieges/1/auto-fill")

    assert response.status_code == 200
    data = response.json()
    assert len(data["assignments"]) == 1
    assert data["assignments"][0]["member_id"] == 2


@pytest.mark.asyncio
async def test_apply_endpoint_returns_200(client):
    apply_result = AutofillApplyResult(applied_count=3, reserve_count=1)
    with patch("app.api.autofill.autofill_service.apply_autofill", new_callable=AsyncMock) as mock:
        mock.return_value = apply_result
        async with client as c:
            response = await c.post("/api/sieges/1/auto-fill/apply")

    assert response.status_code == 200
    data = response.json()
    assert data["applied_count"] == 3
    assert data["reserve_count"] == 1


# ---------------------------------------------------------------------------
# Service unit tests
# ---------------------------------------------------------------------------

from app.services.autofill import apply_autofill, preview_autofill  # noqa: E402


@pytest.mark.asyncio
async def test_preview_respects_scroll_count():
    """With 3 members, 10 positions, and <90 total positions, limit=3.

    All 10 positions are distributed across 3 members in round-robin fashion,
    so no member should exceed 3 assignments (scrolls_per_player returns 3
    for position_count < 90).  With 10 positions / 3 members the most any
    member can receive is ceil(10/3) = 4, but the scroll cap of 3 means the
    last position overflows to reserve instead.
    """
    members = [_make_member(i) for i in range(1, 4)]  # 3 members
    positions = [_make_position(id=i, position_number=i) for i in range(1, 11)]  # 10 positions
    group = _make_group(id=1, slot_count=10)
    group.positions = positions
    building = _make_building()
    building.groups = [group]

    siege = _make_siege()
    siege.buildings = [building]
    siege.siege_members = [_make_sm(m.id, m) for m in members]

    # position_count=10 → scrolls_per_player(10) = 3
    session = _make_session_for_preview(siege, position_count=10)
    result = await preview_autofill(session, 1)

    counts = {}
    for a in result.assignments:
        if a.member_id is not None:
            counts[a.member_id] = counts.get(a.member_id, 0) + 1

    for count in counts.values():
        assert count <= 3


@pytest.mark.asyncio
async def test_preview_marks_leftover_as_reserve():
    """With 1 member, 5 positions, and position_count=5 (<90), limit=3.

    The member fills 3 slots and the remaining 2 become reserve because
    the member has hit the scroll cap.
    """
    members = [_make_member(1)]
    positions = [_make_position(id=i, position_number=i) for i in range(1, 6)]  # 5 positions
    group = _make_group(id=1, slot_count=5)
    group.positions = positions
    building = _make_building()
    building.groups = [group]

    siege = _make_siege()
    siege.buildings = [building]
    siege.siege_members = [_make_sm(1, members[0])]

    # position_count=5 → scrolls_per_player(5) = 3
    session = _make_session_for_preview(siege, position_count=5)
    result = await preview_autofill(session, 1)

    reserve_assignments = [a for a in result.assignments if a.is_reserve]
    member_assignments = [
        a for a in result.assignments if not a.is_reserve and a.member_id is not None
    ]
    assert len(member_assignments) == 3
    assert len(reserve_assignments) == 2


@pytest.mark.asyncio
async def test_apply_commits_preview():
    """Apply reads the stored preview and updates positions."""
    from datetime import timedelta

    expires = datetime.datetime.now(datetime.UTC) + timedelta(hours=1)
    pos = _make_position(id=1)

    siege = _make_siege()
    siege.autofill_preview = {
        "assignments": [{"position_id": 1, "member_id": 42, "is_reserve": False}]
    }
    siege.autofill_preview_expires_at = expires

    positions_result = MagicMock()
    positions_result.scalars.return_value.all.return_value = [pos]

    call_count = 0

    async def fake_execute(stmt):
        nonlocal call_count
        result = MagicMock()
        if call_count == 0:
            result.scalar_one_or_none.return_value = siege
        else:
            result.scalars.return_value.all.return_value = [pos]
        call_count += 1
        return result

    session = AsyncMock()
    session.execute = fake_execute
    session.commit = AsyncMock()

    result = await apply_autofill(session, 1)
    assert result.applied_count == 1
    assert result.reserve_count == 0
    assert pos.member_id == 42


@pytest.mark.asyncio
async def test_apply_returns_409_when_no_preview():
    """Apply returns 409 when no preview exists."""
    from fastapi import HTTPException

    siege = _make_siege()
    siege.autofill_preview = None
    siege.autofill_preview_expires_at = None

    async def fake_execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = siege
        return result

    session = AsyncMock()
    session.execute = fake_execute

    with pytest.raises(HTTPException) as exc_info:
        await apply_autofill(session, 1)
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_apply_returns_409_when_preview_expired():
    """Apply returns 409 when preview has expired."""
    from datetime import timedelta

    from fastapi import HTTPException

    expires = datetime.datetime.now(datetime.UTC) - timedelta(hours=1)  # past

    siege = _make_siege()
    siege.autofill_preview = {"assignments": []}
    siege.autofill_preview_expires_at = expires

    async def fake_execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = siege
        return result

    session = AsyncMock()
    session.execute = fake_execute

    with pytest.raises(HTTPException) as exc_info:
        await apply_autofill(session, 1)
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_preview_skips_broken_building_positions():
    """Broken building positions are excluded from autofill (issue #94).

    Siege has one normal building (2 empty positions) and one broken building (2 empty
    positions).  preview_autofill must only fill the 2 positions on the healthy building;
    the broken building's positions must not appear in the result at all.
    """
    member = _make_member(1)

    # Normal building: positions 10, 11
    normal_positions = [
        _make_position(id=10, position_number=1),
        _make_position(id=11, position_number=2),
    ]
    normal_group = _make_group(id=1, slot_count=2)
    normal_group.positions = normal_positions
    normal_building = _make_building(id=1)
    normal_building.groups = [normal_group]

    # Broken building: positions 20, 21
    broken_positions = [
        _make_position(id=20, position_number=1),
        _make_position(id=21, position_number=2),
    ]
    broken_group = _make_group(id=2, slot_count=2)
    broken_group.positions = broken_positions
    broken_building = _make_building(id=2)
    broken_building.is_broken = True
    broken_building.groups = [broken_group]

    siege = _make_siege()
    siege.buildings = [normal_building, broken_building]
    siege.siege_members = [_make_sm(member.id, member)]

    # position_count=2 (only the normal building's 2 positions count)
    session = _make_session_for_preview(siege, position_count=2)
    result = await preview_autofill(session, 1)

    assigned_position_ids = {a.position_id for a in result.assignments}
    assert assigned_position_ids == {10, 11}, (
        "Only normal-building positions should be auto-filled; "
        f"broken positions 20 and 21 must not appear. Got: {assigned_position_ids}"
    )


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------


def _make_session_for_preview(siege, position_count: int = 5):
    """Return a mock AsyncSession that handles the two execute calls in preview_autofill.

    Call 1 — siege lookup: result.scalar_one_or_none() returns the siege object.
    Call 2 — COUNT query from compute_scroll_count: result.scalar() returns position_count.
    """
    call_count = 0

    async def fake_execute(stmt):
        nonlocal call_count
        result = MagicMock()
        if call_count == 0:
            # First call: select(Siege).where(...) in preview_autofill
            result.scalar_one_or_none.return_value = siege
        else:
            # Second call: select(func.count()) in compute_scroll_count
            result.scalar.return_value = position_count
        call_count += 1
        return result

    session = AsyncMock()
    session.execute = fake_execute
    session.commit = AsyncMock()
    return session
