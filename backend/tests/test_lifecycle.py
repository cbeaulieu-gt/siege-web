"""Endpoint tests for siege lifecycle transitions: activate, complete, clone."""

import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.enums import BuildingType, SiegeStatus
from app.services import lifecycle as lifecycle_service


def _make_siege(
    id: int = 1,
    status: SiegeStatus = SiegeStatus.planning,
    defense_scroll_count: int = 5,
    date: datetime.date | None = datetime.date(2026, 3, 20),
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        date=date,
        status=status,
        defense_scroll_count=defense_scroll_count,
        created_at=datetime.datetime(2026, 1, 1, 0, 0, 0),
        updated_at=datetime.datetime(2026, 1, 1, 0, 0, 0),
    )


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# 1. activate planning siege returns 200 with status=active
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activate_planning_siege(client):
    siege = _make_siege(status=SiegeStatus.active)
    with (
        patch("app.api.lifecycle.lifecycle_service.activate_siege", new_callable=AsyncMock) as mock,
        patch(
            "app.api.lifecycle.sieges_service.compute_scroll_count", new_callable=AsyncMock
        ) as mock_scroll,
    ):
        mock.return_value = siege
        mock_scroll.return_value = 0
        async with client as c:
            response = await c.post("/api/sieges/1/activate")

    assert response.status_code == 200
    assert response.json()["status"] == "active"


# ---------------------------------------------------------------------------
# 2. activating an already-active siege returns 400
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activate_already_active_returns_400(client):
    with patch(
        "app.api.lifecycle.lifecycle_service.activate_siege", new_callable=AsyncMock
    ) as mock:
        mock.side_effect = HTTPException(
            status_code=400, detail="Cannot activate a siege with status 'active'"
        )
        async with client as c:
            response = await c.post("/api/sieges/2/activate")

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# 3. complete an active siege returns 200 with status=complete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_complete_active_siege(client):
    siege = _make_siege(status=SiegeStatus.complete)
    with (
        patch("app.api.lifecycle.lifecycle_service.complete_siege", new_callable=AsyncMock) as mock,
        patch(
            "app.api.lifecycle.sieges_service.compute_scroll_count", new_callable=AsyncMock
        ) as mock_scroll,
    ):
        mock.return_value = siege
        mock_scroll.return_value = 0
        async with client as c:
            response = await c.post("/api/sieges/1/complete")

    assert response.status_code == 200
    assert response.json()["status"] == "complete"


# ---------------------------------------------------------------------------
# 4. completing a planning siege returns 400
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_complete_planning_siege_returns_400(client):
    with patch(
        "app.api.lifecycle.lifecycle_service.complete_siege", new_callable=AsyncMock
    ) as mock:
        mock.side_effect = HTTPException(
            status_code=400, detail="Cannot complete a siege with status 'planning'"
        )
        async with client as c:
            response = await c.post("/api/sieges/1/complete")

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# 5. clone returns 201 with new siege id, status=planning, date=None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clone_siege_returns_201(client):
    cloned = _make_siege(id=99, status=SiegeStatus.planning, date=None)
    with (
        patch("app.api.lifecycle.lifecycle_service.clone_siege", new_callable=AsyncMock) as mock,
        patch(
            "app.api.lifecycle.sieges_service.compute_scroll_count", new_callable=AsyncMock
        ) as mock_scroll,
    ):
        mock.return_value = cloned
        mock_scroll.return_value = 0
        async with client as c:
            response = await c.post("/api/sieges/1/clone")

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 99
    assert data["status"] == "planning"
    assert data["date"] is None


# ---------------------------------------------------------------------------
# 6. clone_siege uses PostPriorityConfig priority, not the source post priority
#    Regression test for bug #194: cloning a siege whose posts have priority=0
#    (predating PostPriorityConfig seeds) must not propagate that stale value.
# ---------------------------------------------------------------------------


def _make_post_ns(priority: int, description: str | None = None):
    return SimpleNamespace(
        priority=priority,
        description=description,
        active_conditions=[],
    )


def _make_post_priority_config_ns(post_number: int, priority: int):
    return SimpleNamespace(post_number=post_number, priority=priority)


def _make_src_position_ns(position_number=1, member_id=None, member=None, is_reserve=False):
    return SimpleNamespace(
        position_number=position_number,
        member_id=member_id,
        member=member,
        is_reserve=is_reserve,
        is_disabled=False,
    )


def _make_src_group_ns(group_number=1, slot_count=1, positions=None):
    return SimpleNamespace(
        group_number=group_number,
        slot_count=slot_count,
        positions=positions or [],
    )


def _make_src_building_ns(building_type, building_number, groups=None, post=None):
    return SimpleNamespace(
        building_type=building_type,
        building_number=building_number,
        level=1,
        is_broken=False,
        groups=groups or [],
        post=post,
    )


@pytest.mark.asyncio
async def test_clone_uses_post_priority_config_not_source_priority():
    """Cloning a siege with stale priority=0 posts must use PostPriorityConfig.priority.

    Regression for bug #194: clone_siege was copying src_post.priority verbatim.
    Sieges created before PostPriorityConfig seeds had priority=0, so every clone
    perpetuated the stale value. The fix queries PostPriorityConfig by post_number,
    matching the behavior of create_siege.
    """
    # Source siege: one post building whose post carries the stale priority=0
    stale_post = _make_post_ns(priority=0, description="Old post")
    src_group = _make_src_group_ns(
        group_number=1,
        slot_count=1,
        positions=[_make_src_position_ns(position_number=1)],
    )
    src_building = _make_src_building_ns(
        building_type=BuildingType.post,
        building_number=3,
        groups=[src_group],
        post=stale_post,
    )
    source_siege = SimpleNamespace(
        id=1,
        date=datetime.date(2025, 1, 1),
        status=SiegeStatus.complete,
        defense_scroll_count=5,
        buildings=[src_building],
        siege_members=[],
    )

    # PostPriorityConfig seed says post 3 has priority=4 (not 0)
    ppc = _make_post_priority_config_ns(post_number=3, priority=4)

    # The session mock drives clone_siege through its execute calls.
    # clone_siege makes these execute calls in order:
    #   call 0 — SELECT Siege (load source, with selectinload options)
    #   call 1 — SELECT PostPriorityConfig WHERE post_number == 3
    # All ORM constructors (Siege, Building, BuildingGroup, Position, Post) run for real;
    # only session.flush is stubbed so we can inject .id values on the new objects.
    added_objects: list = []
    execute_call_count = 0
    flush_call_count = 0

    # IDs assigned during flush, in the order flush is called:
    # flush 0 → new Siege gets id=99
    # flush 1 → new Building gets id=10
    # flush 2 → new BuildingGroup gets id=20
    flush_id_map = {0: ("siege", 99), 1: ("building", 10), 2: ("group", 20)}
    async def fake_execute(stmt):
        nonlocal execute_call_count
        result = MagicMock()
        if execute_call_count == 0:
            result.scalar_one_or_none.return_value = source_siege
        else:
            # PostPriorityConfig lookup
            result.scalar_one_or_none.return_value = ppc
        execute_call_count += 1
        return result

    async def fake_flush():
        nonlocal flush_call_count
        if flush_call_count < len(flush_id_map):
            # Assign the id to the last object that was session.add()-ed
            if added_objects:
                added_objects[-1].id = flush_id_map[flush_call_count][1]
        flush_call_count += 1

    session = AsyncMock()
    session.execute = fake_execute
    session.flush = fake_flush
    session.commit = AsyncMock()
    session.add = lambda obj: added_objects.append(obj)
    session.refresh = AsyncMock()

    await lifecycle_service.clone_siege(session, 1)

    # Find all Post instances that were added to the session
    from app.models.post import Post as PostModel

    posts_added = [obj for obj in added_objects if isinstance(obj, PostModel)]

    assert len(posts_added) == 1, f"Expected exactly 1 Post to be cloned, got {len(posts_added)}"

    cloned_post = posts_added[0]

    # Core assertion: priority must come from PostPriorityConfig (4), not the stale source (0)
    assert cloned_post.priority == 4, (
        f"Expected priority=4 from PostPriorityConfig, got priority={cloned_post.priority}. "
        "Bug #194: clone_siege was copying src_post.priority (0) instead of querying config."
    )
    # Description is still copied from the source post, not from config
    assert cloned_post.description == "Old post"
