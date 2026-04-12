"""Smoke tests for scripts/seed_demo.py.

These tests run against an in-memory SQLite database (via the aiosqlite driver)
to keep them fast and DB-free in CI. They verify:
  - All 28 demo members are created on first run
  - The demo siege is created with correct status
  - Running twice does not create duplicates
  - Buildings and positions are populated
  - Siege members are enrolled with attack day assignments
"""

import sys
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Ensure the backend root is on sys.path (mimics how the script resolves imports).
_backend_root = Path(__file__).parent.parent
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

from app.db.base import Base  # noqa: E402
from app.models.building import Building  # noqa: E402
from app.models.enums import SiegeStatus  # noqa: E402
from app.models.member import Member  # noqa: E402
from app.models.position import Position  # noqa: E402
from app.models.siege import Siege  # noqa: E402
from app.models.siege_member import SiegeMember  # noqa: E402

# ---------------------------------------------------------------------------
# Shared async SQLite fixture
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def session():
    """Provide a fresh in-memory SQLite session for each test."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s

    await engine.dispose()


# ---------------------------------------------------------------------------
# Import seed helpers after sys.path is set
# ---------------------------------------------------------------------------


async def _run_seed(session: AsyncSession) -> None:
    """Run the demo seed functions against the provided session."""
    from app.db.seeds import (
        seed_building_type_config,
        seed_post_conditions,
        seed_post_priority_config,
    )
    from scripts.seed_demo import (
        get_or_create_demo_siege,
        get_or_create_members,
        seed_buildings_and_positions,
        seed_siege_members,
    )

    await seed_post_conditions(session)
    await seed_building_type_config(session)
    await seed_post_priority_config(session)
    await session.commit()

    members = await get_or_create_members(session)
    await session.commit()

    siege = await get_or_create_demo_siege(session)
    await session.commit()

    await seed_buildings_and_positions(session, siege, members)
    await session.commit()

    await seed_siege_members(session, siege, members)
    await session.commit()


class TestSeedDemoMembers:
    """Demo member creation."""

    @pytest.mark.asyncio
    async def test_creates_25_members(self, session):
        await _run_seed(session)
        count = (await session.execute(select(func.count()).select_from(Member))).scalar_one()
        assert count == 28

    @pytest.mark.asyncio
    async def test_members_have_demo_names(self, session):
        await _run_seed(session)
        result = await session.execute(select(Member.name))
        names = [row[0] for row in result.all()]
        assert "Grimmaw" in names
        assert "Noll" in names

    @pytest.mark.asyncio
    async def test_idempotent_member_creation(self, session):
        """Running twice must not create duplicate members."""
        await _run_seed(session)
        await _run_seed(session)
        count = (await session.execute(select(func.count()).select_from(Member))).scalar_one()
        assert count == 28


class TestSeedDemoSiege:
    """Demo siege creation."""

    @pytest.mark.asyncio
    async def test_creates_one_siege(self, session):
        await _run_seed(session)
        count = (await session.execute(select(func.count()).select_from(Siege))).scalar_one()
        assert count == 1

    @pytest.mark.asyncio
    async def test_siege_has_active_status(self, session):
        await _run_seed(session)
        siege = (await session.execute(select(Siege))).scalar_one()
        assert siege.status == SiegeStatus.active

    @pytest.mark.asyncio
    async def test_idempotent_siege_creation(self, session):
        """Running twice must not create a second siege."""
        await _run_seed(session)
        await _run_seed(session)
        count = (await session.execute(select(func.count()).select_from(Siege))).scalar_one()
        assert count == 1


class TestSeedDemoBuildingsAndPositions:
    """Buildings and positions."""

    @pytest.mark.asyncio
    async def test_creates_buildings(self, session):
        await _run_seed(session)
        count = (await session.execute(select(func.count()).select_from(Building))).scalar_one()
        assert count > 0

    @pytest.mark.asyncio
    async def test_creates_positions(self, session):
        await _run_seed(session)
        count = (await session.execute(select(func.count()).select_from(Position))).scalar_one()
        assert count > 0

    @pytest.mark.asyncio
    async def test_some_positions_have_members(self, session):
        """Most positions should be filled with demo members."""
        await _run_seed(session)
        filled = (
            await session.execute(
                select(func.count()).select_from(Position).where(Position.member_id.is_not(None))
            )
        ).scalar_one()
        assert filled > 0

    @pytest.mark.asyncio
    async def test_idempotent_position_creation(self, session):
        """Running twice must not double the building/position count."""
        await _run_seed(session)
        count_first = (
            await session.execute(select(func.count()).select_from(Position))
        ).scalar_one()
        await _run_seed(session)
        count_second = (
            await session.execute(select(func.count()).select_from(Position))
        ).scalar_one()
        assert count_first == count_second


class TestSeedDemosiegeMembers:
    """Siege member enrollments."""

    @pytest.mark.asyncio
    async def test_enrolls_all_members(self, session):
        await _run_seed(session)
        count = (await session.execute(select(func.count()).select_from(SiegeMember))).scalar_one()
        assert count == 28

    @pytest.mark.asyncio
    async def test_members_have_attack_days(self, session):
        await _run_seed(session)
        result = await session.execute(select(SiegeMember.attack_day))
        days = [row[0] for row in result.all()]
        assert 1 in days
        assert 2 in days

    @pytest.mark.asyncio
    async def test_idempotent_siege_member_enrollment(self, session):
        """Running twice must not double the siege_member count."""
        await _run_seed(session)
        await _run_seed(session)
        count = (await session.execute(select(func.count()).select_from(SiegeMember))).scalar_one()
        assert count == 28
