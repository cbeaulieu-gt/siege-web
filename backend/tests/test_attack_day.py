"""Tests for the attack day auto-assign algorithm."""

import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.enums import MemberRole, SiegeStatus
from app.schemas.attack_day import AttackDayApplyResult, AttackDayAssignment, AttackDayPreviewResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_siege(id=1):
    return SimpleNamespace(
        id=id,
        date=datetime.date(2026, 3, 20),
        status=SiegeStatus.planning,
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


def _make_member(id, role=MemberRole.advanced, power=None):
    return SimpleNamespace(id=id, name=f"Member{id}", role=role, is_active=True, power=power)


def _make_sm(siege_id=1, member_id=1, attack_day=None, attack_day_override=False, member=None):
    return SimpleNamespace(siege_id=siege_id, member_id=member_id, attack_day=attack_day, has_reserve_set=True, attack_day_override=attack_day_override, member=member)


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preview_attack_day_endpoint_200(client):
    preview = AttackDayPreviewResult(
        assignments=[AttackDayAssignment(member_id=1, attack_day=2)],
        expires_at="2026-03-17T12:00:00+00:00",
    )
    with patch(
        "app.api.attack_day.attack_day_service.preview_attack_day", new_callable=AsyncMock
    ) as mock:
        mock.return_value = preview
        async with client as c:
            response = await c.post("/api/sieges/1/members/auto-assign-attack-day")

    assert response.status_code == 200
    data = response.json()
    assert data["assignments"][0]["attack_day"] == 2


@pytest.mark.asyncio
async def test_apply_attack_day_endpoint_200(client):
    apply_result = AttackDayApplyResult(applied_count=10)
    with patch(
        "app.api.attack_day.attack_day_service.apply_attack_day", new_callable=AsyncMock
    ) as mock:
        mock.return_value = apply_result
        async with client as c:
            response = await c.post("/api/sieges/1/members/auto-assign-attack-day/apply")

    assert response.status_code == 200
    assert response.json()["applied_count"] == 10


# ---------------------------------------------------------------------------
# Service unit tests
# ---------------------------------------------------------------------------

from app.services.attack_day import preview_attack_day, apply_attack_day


def _session_for_siege(siege):
    async def fake_execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = siege
        return result

    session = AsyncMock()
    session.execute = fake_execute
    session.commit = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_heavy_hitters_and_advanced_always_day2():
    """Heavy hitters and advanced always get Day 2 regardless of threshold."""
    siege = _make_siege()
    members_hh = [_make_member(i, role=MemberRole.heavy_hitter) for i in range(1, 4)]
    members_adv = [_make_member(i, role=MemberRole.advanced) for i in range(4, 7)]
    siege.siege_members = [
        _make_sm(member_id=m.id, member=m)
        for m in members_hh + members_adv
    ]

    session = _session_for_siege(siege)
    result = await preview_attack_day(session, 1)

    assignment_map = {a.member_id: a.attack_day for a in result.assignments}
    for m in members_hh + members_adv:
        assert assignment_map[m.id] == 2, f"Member {m.id} should be Day 2"


@pytest.mark.asyncio
async def test_medium_promoted_when_under_10():
    """Medium members are promoted to Day 2 (by power desc) when count < 10."""
    siege = _make_siege()
    # 5 HH/ADV → 5 Day 2 so far; need 5 more from Medium
    hh_members = [_make_member(i, role=MemberRole.heavy_hitter) for i in range(1, 6)]
    medium_members = [
        _make_member(10, role=MemberRole.medium, power=1000),
        _make_member(11, role=MemberRole.medium, power=500),
        _make_member(12, role=MemberRole.medium, power=100),
    ]
    siege.siege_members = [
        _make_sm(member_id=m.id, member=m)
        for m in hh_members + medium_members
    ]

    session = _session_for_siege(siege)
    result = await preview_attack_day(session, 1)

    assignment_map = {a.member_id: a.attack_day for a in result.assignments}
    # Top 5 medium members by power promoted to Day 2 (only 3 available here)
    assert assignment_map[10] == 2  # highest power
    assert assignment_map[11] == 2
    assert assignment_map[12] == 2


@pytest.mark.asyncio
async def test_novice_promoted_when_still_under_10():
    """Novice promoted by power desc after medium if still < 10."""
    siege = _make_siege()
    # 3 HH, 3 medium promoted → 6 Day 2; need 4 novice
    hh = [_make_member(i, role=MemberRole.heavy_hitter) for i in range(1, 4)]
    med = [_make_member(i, role=MemberRole.medium, power=float(i * 100)) for i in range(10, 13)]
    novice = [
        _make_member(20, role=MemberRole.novice, power=900),
        _make_member(21, role=MemberRole.novice, power=800),
        _make_member(22, role=MemberRole.novice, power=700),
        _make_member(23, role=MemberRole.novice, power=600),
        _make_member(24, role=MemberRole.novice, power=100),
    ]
    siege.siege_members = [
        _make_sm(member_id=m.id, member=m)
        for m in hh + med + novice
    ]

    session = _session_for_siege(siege)
    result = await preview_attack_day(session, 1)

    assignment_map = {a.member_id: a.attack_day for a in result.assignments}
    # 3 HH + 3 med + top 4 novice = 10 Day 2
    day2_count = sum(1 for d in assignment_map.values() if d == 2)
    assert day2_count == 10
    assert assignment_map[20] == 2
    assert assignment_map[21] == 2
    assert assignment_map[22] == 2
    assert assignment_map[23] == 2
    assert assignment_map[24] == 1  # lowest power novice doesn't make it


@pytest.mark.asyncio
async def test_pinned_members_count_toward_threshold():
    """Overridden Day 2 members count toward the 10-threshold."""
    siege = _make_siege()
    # 8 overridden Day 2 members → only need 2 more from the rest
    overridden = [
        _make_sm(member_id=i, attack_day=2, attack_day_override=True)
        for i in range(1, 9)
    ]
    medium = [
        _make_member(10, role=MemberRole.medium, power=1000),
        _make_member(11, role=MemberRole.medium, power=500),
        _make_member(12, role=MemberRole.medium, power=100),
    ]
    non_overridden = [_make_sm(member_id=m.id, member=m) for m in medium]
    siege.siege_members = overridden + non_overridden

    session = _session_for_siege(siege)
    result = await preview_attack_day(session, 1)

    assignment_map = {a.member_id: a.attack_day for a in result.assignments}
    day2_count = sum(1 for d in assignment_map.values() if d == 2)
    assert day2_count == 10
    # Top 2 medium get Day 2
    assert assignment_map[10] == 2
    assert assignment_map[11] == 2
    # Lowest medium gets Day 1 since threshold reached
    assert assignment_map[12] == 1


@pytest.mark.asyncio
async def test_overridden_members_not_changed():
    """attack_day_override=True members keep their existing attack_day."""
    siege = _make_siege()
    pinned_day1 = _make_sm(member_id=1, attack_day=1, attack_day_override=True)
    pinned_day2 = _make_sm(member_id=2, attack_day=2, attack_day_override=True)
    siege.siege_members = [pinned_day1, pinned_day2]

    session = _session_for_siege(siege)
    result = await preview_attack_day(session, 1)

    assignment_map = {a.member_id: a.attack_day for a in result.assignments}
    assert assignment_map[1] == 1  # pinned to Day 1 — unchanged
    assert assignment_map[2] == 2  # pinned to Day 2 — unchanged


@pytest.mark.asyncio
async def test_boundary_at_exactly_10():
    """Exactly 10 HH/ADV → all remaining go to Day 1."""
    siege = _make_siege()
    hh = [_make_member(i, role=MemberRole.heavy_hitter) for i in range(1, 11)]
    medium = [_make_member(20, role=MemberRole.medium, power=9999)]
    siege.siege_members = [
        _make_sm(member_id=m.id, member=m)
        for m in hh + medium
    ]

    session = _session_for_siege(siege)
    result = await preview_attack_day(session, 1)

    assignment_map = {a.member_id: a.attack_day for a in result.assignments}
    day2_count = sum(1 for d in assignment_map.values() if d == 2)
    assert day2_count == 10
    # The medium member should NOT be Day 2 since threshold was already met
    assert assignment_map[20] == 1


@pytest.mark.asyncio
async def test_apply_attack_day_commits():
    """Apply reads stored preview and updates siege_member attack_day values."""
    from datetime import timezone, timedelta

    expires = datetime.datetime.now(timezone.utc) + timedelta(hours=1)
    sm = _make_sm(member_id=1, attack_day=None)

    siege = _make_siege()
    siege.attack_day_preview = {
        "assignments": [{"member_id": 1, "attack_day": 2}]
    }
    siege.attack_day_preview_expires_at = expires
    siege.siege_members = [sm]

    call_count = 0

    async def fake_execute(stmt):
        nonlocal call_count
        result = MagicMock()
        result.scalar_one_or_none.return_value = siege
        call_count += 1
        return result

    session = AsyncMock()
    session.execute = fake_execute
    session.commit = AsyncMock()

    result = await apply_attack_day(session, 1)
    assert result.applied_count == 1
    assert sm.attack_day == 2


@pytest.mark.asyncio
async def test_apply_attack_day_409_no_preview():
    """Returns 409 when no preview exists."""
    from fastapi import HTTPException

    siege = _make_siege()
    siege.attack_day_preview = None
    siege.attack_day_preview_expires_at = None
    siege.siege_members = []

    async def fake_execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = siege
        return result

    session = AsyncMock()
    session.execute = fake_execute

    with pytest.raises(HTTPException) as exc_info:
        await apply_attack_day(session, 1)
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_apply_attack_day_409_expired():
    """Returns 409 when preview has expired."""
    from fastapi import HTTPException
    from datetime import timezone, timedelta

    expires = datetime.datetime.now(timezone.utc) - timedelta(hours=1)

    siege = _make_siege()
    siege.attack_day_preview = {"assignments": [{"member_id": 1, "attack_day": 2}]}
    siege.attack_day_preview_expires_at = expires
    siege.siege_members = []

    async def fake_execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = siege
        return result

    session = AsyncMock()
    session.execute = fake_execute

    with pytest.raises(HTTPException) as exc_info:
        await apply_attack_day(session, 1)
    assert exc_info.value.status_code == 409
