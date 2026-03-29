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
from app.models.enums import BuildingType, SiegeStatus
from app.models.siege import Siege
from app.services.building_capacity import _LEVEL_TEAMS


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


async def _seed_siege(session: AsyncSession, buildings: list[dict]) -> int:
    """Insert a siege with the given buildings and return the siege id.

    Each dict in ``buildings`` must have keys: ``building_type``, ``level``,
    ``building_number``, and optionally ``is_broken`` (default False).
    No Position or BuildingGroup records are created — compute_scroll_count no
    longer touches them.
    """
    siege = Siege(
        date=datetime.date(2026, 3, 20), status=SiegeStatus.planning, defense_scroll_count=0
    )
    session.add(siege)
    await session.flush()

    for spec in buildings:
        session.add(
            Building(
                siege_id=siege.id,
                building_type=spec["building_type"],
                building_number=spec["building_number"],
                level=spec["level"],
                is_broken=spec.get("is_broken", False),
            )
        )

    await session.flush()
    return siege.id


# ---------------------------------------------------------------------------
# compute_scroll_count integration tests (issue #94)
#
# The count is derived from theoretical capacity (_LEVEL_TEAMS) per building
# type+level.  Position records are not consulted, and is_broken is ignored.
# ---------------------------------------------------------------------------


async def test_compute_scroll_count_sums_theoretical_capacity(db_session: AsyncSession):
    """compute_scroll_count returns the sum of _LEVEL_TEAMS capacities for all buildings.

    Two stronghold level-1 buildings: 12 + 12 = 24.
    One mana_shrine level-2 building: 7.
    Expected total: 31.
    """
    siege_id = await _seed_siege(
        db_session,
        buildings=[
            {"building_type": BuildingType.stronghold, "level": 1, "building_number": 1},
            {"building_type": BuildingType.stronghold, "level": 1, "building_number": 2},
            {"building_type": BuildingType.mana_shrine, "level": 2, "building_number": 1},
        ],
    )
    expected = (
        _LEVEL_TEAMS["stronghold"][1]
        + _LEVEL_TEAMS["stronghold"][1]
        + _LEVEL_TEAMS["mana_shrine"][2]
    )  # 12 + 12 + 7 = 31
    count = await compute_scroll_count(db_session, siege_id)
    assert count == expected, f"Expected {expected}, got {count}."


async def test_compute_scroll_count_broken_building_unchanged(db_session: AsyncSession):
    """Breaking a building must NOT change the scroll count (regression guard for issue #94).

    One stronghold level-1 (healthy) and one stronghold level-1 (broken).
    Both contribute their theoretical capacity: 12 + 12 = 24.
    If is_broken were incorrectly used to filter, the broken building would be excluded
    and the result would be 12 instead of 24.
    """
    siege_id = await _seed_siege(
        db_session,
        buildings=[
            {
                "building_type": BuildingType.stronghold,
                "level": 1,
                "building_number": 1,
                "is_broken": False,
            },
            {
                "building_type": BuildingType.stronghold,
                "level": 1,
                "building_number": 2,
                "is_broken": True,
            },
        ],
    )
    expected = _LEVEL_TEAMS["stronghold"][1] * 2  # 24
    count = await compute_scroll_count(db_session, siege_id)
    assert count == expected, (
        f"Expected {expected} (broken building still counts), got {count}. "
        "is_broken must not filter buildings out of the scroll count."
    )


async def test_compute_scroll_count_level_change_updates_count(db_session: AsyncSession):
    """A level change must update the scroll count.

    One defense_tower at level 1 (capacity 2) vs level 6 (capacity 12).
    After updating the building's level in-place, compute_scroll_count must
    return the new capacity.
    """
    siege_id = await _seed_siege(
        db_session,
        buildings=[
            {"building_type": BuildingType.defense_tower, "level": 1, "building_number": 1},
        ],
    )
    count_l1 = await compute_scroll_count(db_session, siege_id)
    assert count_l1 == _LEVEL_TEAMS["defense_tower"][1], f"Level-1 count wrong: {count_l1}"

    # Simulate a level upgrade by mutating the building row directly
    from sqlalchemy import select as sa_select

    result = await db_session.execute(sa_select(Building).where(Building.siege_id == siege_id))
    building = result.scalar_one()
    building.level = 6
    await db_session.flush()

    count_l6 = await compute_scroll_count(db_session, siege_id)
    assert (
        count_l6 == _LEVEL_TEAMS["defense_tower"][6]
    ), f"Expected {_LEVEL_TEAMS['defense_tower'][6]} after level 6 upgrade, got {count_l6}."


async def test_compute_scroll_count_post_buildings_contribute_one(db_session: AsyncSession):
    """Post buildings (not in _LEVEL_TEAMS) must contribute 1 position each.

    One stronghold level-1 (12) + one post (1) = 13.
    """
    siege_id = await _seed_siege(
        db_session,
        buildings=[
            {"building_type": BuildingType.stronghold, "level": 1, "building_number": 1},
            {"building_type": BuildingType.post, "level": 1, "building_number": 1},
        ],
    )
    expected = _LEVEL_TEAMS["stronghold"][1] + 1  # 13
    count = await compute_scroll_count(db_session, siege_id)
    assert count == expected, f"Expected {expected} (post contributes 1), got {count}."
