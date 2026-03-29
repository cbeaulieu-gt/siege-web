"""Endpoint tests for /api/sieges — mocks the service layer directly."""

import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401  — populate metadata
from app.db.base import Base
from app.main import app
from app.models.building import Building
from app.models.building_group import BuildingGroup
from app.models.enums import BuildingType, SiegeStatus
from app.models.position import Position
from app.models.siege import Siege


def _make_siege(
    id: int = 1,
    status: SiegeStatus = SiegeStatus.planning,
    defense_scroll_count: int = 5,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        date=datetime.date(2026, 3, 20),
        status=status,
        defense_scroll_count=defense_scroll_count,
        created_at=datetime.datetime(2026, 1, 1, 0, 0, 0),
        updated_at=datetime.datetime(2026, 1, 1, 0, 0, 0),
    )


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# 1. list_sieges returns empty list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_sieges_returns_empty_list(client):
    with patch("app.api.sieges.sieges_service.list_sieges", new_callable=AsyncMock) as mock:
        mock.return_value = []
        async with client as c:
            response = await c.get("/api/sieges")

    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# 2. create_siege returns 201
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_siege_returns_201(client):
    siege = _make_siege()
    with (
        patch("app.api.sieges.sieges_service.create_siege", new_callable=AsyncMock) as mock,
        patch(
            "app.api.sieges.sieges_service.compute_scroll_count", new_callable=AsyncMock
        ) as mock_scroll,
    ):
        mock.return_value = siege
        mock_scroll.return_value = 0
        async with client as c:
            response = await c.post(
                "/api/sieges",
                json={"date": "2026-03-20", "defense_scroll_count": 5},
            )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 1
    assert data["date"] == "2026-03-20"
    assert data["status"] == "planning"
    assert data["defense_scroll_count"] == 5


# ---------------------------------------------------------------------------
# 3. get_siege not found returns 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_siege_not_found_returns_404(client):
    with patch("app.api.sieges.sieges_service.get_siege", new_callable=AsyncMock) as mock:
        mock.side_effect = HTTPException(status_code=404, detail="Siege not found")
        async with client as c:
            response = await c.get("/api/sieges/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Siege not found"


# ---------------------------------------------------------------------------
# 4. delete planning siege returns 204
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_planning_siege_returns_204(client):
    with patch("app.api.sieges.sieges_service.delete_siege", new_callable=AsyncMock) as mock:
        mock.return_value = None
        async with client as c:
            response = await c.delete("/api/sieges/1")

    assert response.status_code == 204


# ---------------------------------------------------------------------------
# 5. delete active siege returns 400
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_active_siege_returns_400(client):
    with patch("app.api.sieges.sieges_service.delete_siege", new_callable=AsyncMock) as mock:
        mock.side_effect = HTTPException(
            status_code=400, detail="Only planning sieges can be deleted"
        )
        async with client as c:
            response = await c.delete("/api/sieges/2")

    assert response.status_code == 400
    assert "planning" in response.json()["detail"]


# ---------------------------------------------------------------------------
# 6. compute_scroll_count — real integration tests (issue #94)
#
# These tests use an in-memory SQLite DB so that the WHERE clauses in
# compute_scroll_count are actually evaluated.  A mock-based test cannot
# verify that Building.is_broken == False is present in the query — it only
# confirms that whatever scalar the DB returns is passed through unchanged.
# ---------------------------------------------------------------------------


from app.services.sieges import compute_scroll_count  # noqa: E402


def _enable_sqlite_fk(dbapi_conn, _connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    event.listen(engine.sync_engine, "connect", _enable_sqlite_fk)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _seed_siege_with_buildings(
    session: AsyncSession,
    *,
    healthy_position_count: int,
    broken_position_count: int,
    disabled_position_count: int = 0,
) -> int:
    """Insert a siege with two buildings and return the siege id.

    - Building 1: healthy, ``healthy_position_count`` enabled positions
    - Building 2: broken, ``broken_position_count`` positions
    - Building 3 (optional): healthy, ``disabled_position_count`` disabled positions
    """
    siege = Siege(date=datetime.date(2026, 3, 20), status=SiegeStatus.planning, defense_scroll_count=0)
    session.add(siege)
    await session.flush()

    # --- healthy building ---
    b1 = Building(
        siege_id=siege.id,
        building_type=BuildingType.stronghold,
        building_number=1,
        level=1,
        is_broken=False,
    )
    session.add(b1)
    await session.flush()
    if healthy_position_count > 0:
        g1 = BuildingGroup(building_id=b1.id, group_number=1, slot_count=min(healthy_position_count, 3))
        session.add(g1)
        await session.flush()
        for i in range(1, healthy_position_count + 1):
            session.add(Position(building_group_id=g1.id, position_number=i, is_disabled=False))

    # --- broken building ---
    b2 = Building(
        siege_id=siege.id,
        building_type=BuildingType.stronghold,
        building_number=2,
        level=1,
        is_broken=True,
    )
    session.add(b2)
    await session.flush()
    if broken_position_count > 0:
        g2 = BuildingGroup(building_id=b2.id, group_number=1, slot_count=min(broken_position_count, 3))
        session.add(g2)
        await session.flush()
        for i in range(1, broken_position_count + 1):
            session.add(Position(building_group_id=g2.id, position_number=i, is_disabled=False))

    # --- healthy building with disabled positions ---
    if disabled_position_count > 0:
        b3 = Building(
            siege_id=siege.id,
            building_type=BuildingType.stronghold,
            building_number=3,
            level=1,
            is_broken=False,
        )
        session.add(b3)
        await session.flush()
        g3 = BuildingGroup(building_id=b3.id, group_number=1, slot_count=min(disabled_position_count, 3))
        session.add(g3)
        await session.flush()
        for i in range(1, disabled_position_count + 1):
            session.add(Position(building_group_id=g3.id, position_number=i, is_disabled=True))

    await session.flush()
    return siege.id


async def test_compute_scroll_count_counts_healthy_positions(db_session: AsyncSession):
    """compute_scroll_count counts enabled positions from non-broken buildings (issue #94).

    Healthy building: 3 positions.  Broken building: 3 positions.
    Expected result: 3 (broken building excluded by WHERE Building.is_broken == False).

    This test FAILS if the is_broken filter is removed from the query — without it, the
    count would be 6 instead of 3.
    """
    siege_id = await _seed_siege_with_buildings(
        db_session, healthy_position_count=3, broken_position_count=3
    )
    count = await compute_scroll_count(db_session, siege_id)
    assert count == 3, (
        f"Expected 3 (healthy building only), got {count}. "
        "Broken building positions must be excluded by Building.is_broken == False filter."
    )


async def test_compute_scroll_count_returns_zero_for_all_broken(db_session: AsyncSession):
    """compute_scroll_count returns 0 when the only building is broken (issue #94).

    With no healthy buildings, no positions should count toward the scroll budget.
    """
    siege_id = await _seed_siege_with_buildings(
        db_session, healthy_position_count=0, broken_position_count=3
    )
    count = await compute_scroll_count(db_session, siege_id)
    assert count == 0, f"Expected 0 (all buildings broken), got {count}."


async def test_compute_scroll_count_excludes_disabled_positions(db_session: AsyncSession):
    """compute_scroll_count also excludes disabled positions from healthy buildings.

    Healthy enabled: 3, healthy disabled: 2, broken enabled: 3.
    Expected: 3 (only the healthy+enabled positions).
    """
    siege_id = await _seed_siege_with_buildings(
        db_session,
        healthy_position_count=3,
        broken_position_count=3,
        disabled_position_count=2,
    )
    count = await compute_scroll_count(db_session, siege_id)
    assert count == 3, (
        f"Expected 3 (healthy+enabled only), got {count}. "
        "Both broken buildings and disabled positions must be excluded."
    )
