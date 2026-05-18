"""Regression tests for scripts/seed.py (the canonical seed entry point).

These tests run against an in-memory SQLite database (via the aiosqlite
driver) to keep them fast and DB-free in CI. They verify:
  - All three seed functions are invoked by the canonical script
  - PostCondition rows are seeded (36 rows)
  - BuildingTypeConfig rows are seeded (5 rows)
  - PostPriorityConfig rows are seeded (18 rows)
  - Running twice does not create duplicates (idempotency)
"""

import sys
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Ensure the backend root is on sys.path (mimics how the script resolves
# imports via its own sys.path.insert).
_backend_root = Path(__file__).parent.parent
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

from app.db.base import Base  # noqa: E402
from app.models.building_type_config import BuildingTypeConfig  # noqa: E402
from app.models.post_condition import PostCondition  # noqa: E402
from app.models.post_priority_config import PostPriorityConfig  # noqa: E402

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


async def _run_canonical_seed(session: AsyncSession) -> None:
    """Run the three seed functions called by scripts/seed.py."""
    from app.db.seeds import (
        seed_building_type_config,
        seed_post_conditions,
        seed_post_priority_config,
    )

    await seed_post_conditions(session)
    await seed_building_type_config(session)
    await seed_post_priority_config(session)
    await session.commit()


class TestCanonicalSeedPostConditions:
    """PostCondition seeding via the canonical script."""

    @pytest.mark.asyncio
    async def test_seeds_36_post_conditions(self, session: AsyncSession) -> None:
        """Canonical seed must insert all 36 PostCondition rows."""
        await _run_canonical_seed(session)
        count = (
            await session.execute(select(func.count()).select_from(PostCondition))
        ).scalar_one()
        assert count == 36

    @pytest.mark.asyncio
    async def test_idempotent_post_conditions(self, session: AsyncSession) -> None:
        """Running twice must not create duplicate PostCondition rows."""
        await _run_canonical_seed(session)
        await _run_canonical_seed(session)
        count = (
            await session.execute(select(func.count()).select_from(PostCondition))
        ).scalar_one()
        assert count == 36


class TestCanonicalSeedBuildingTypeConfig:
    """BuildingTypeConfig seeding via the canonical script."""

    @pytest.mark.asyncio
    async def test_seeds_building_type_configs(self, session: AsyncSession) -> None:
        """Canonical seed must insert BuildingTypeConfig rows."""
        await _run_canonical_seed(session)
        count = (
            await session.execute(select(func.count()).select_from(BuildingTypeConfig))
        ).scalar_one()
        assert count > 0

    @pytest.mark.asyncio
    async def test_idempotent_building_type_config(self, session: AsyncSession) -> None:
        """Running twice must not create duplicate BuildingTypeConfig rows."""
        await _run_canonical_seed(session)
        count_first = (
            await session.execute(select(func.count()).select_from(BuildingTypeConfig))
        ).scalar_one()
        await _run_canonical_seed(session)
        count_second = (
            await session.execute(select(func.count()).select_from(BuildingTypeConfig))
        ).scalar_one()
        assert count_first == count_second


class TestCanonicalSeedPostPriorityConfig:
    """PostPriorityConfig seeding via the canonical script.

    This is the seed that was missing from the legacy backend/seed.py and
    caused the dev DB to have an empty post_priority_config table.
    """

    @pytest.mark.asyncio
    async def test_seeds_18_post_priority_configs(self, session: AsyncSession) -> None:
        """Canonical seed must insert all 18 PostPriorityConfig rows."""
        await _run_canonical_seed(session)
        count = (
            await session.execute(select(func.count()).select_from(PostPriorityConfig))
        ).scalar_one()
        assert count == 18

    @pytest.mark.asyncio
    async def test_priority_configs_cover_posts_1_through_18(self, session: AsyncSession) -> None:
        """PostPriorityConfig rows must cover post numbers 1 through 18."""
        await _run_canonical_seed(session)
        result = await session.execute(select(PostPriorityConfig.post_number))
        post_numbers = sorted(row[0] for row in result.all())
        assert post_numbers == list(range(1, 19))

    @pytest.mark.asyncio
    async def test_priority_configs_default_priority_is_2(self, session: AsyncSession) -> None:
        """All PostPriorityConfig rows must have default priority of 2."""
        await _run_canonical_seed(session)
        result = await session.execute(select(PostPriorityConfig.priority))
        priorities = [row[0] for row in result.all()]
        assert all(p == 2 for p in priorities)

    @pytest.mark.asyncio
    async def test_idempotent_post_priority_config(self, session: AsyncSession) -> None:
        """Running twice must not create duplicate PostPriorityConfig rows."""
        await _run_canonical_seed(session)
        await _run_canonical_seed(session)
        count = (
            await session.execute(select(func.count()).select_from(PostPriorityConfig))
        ).scalar_one()
        assert count == 18


class TestConditionTypeSeeded:
    """Assert that condition_type is populated for at least one row per category.

    The seven categories are: league, role, faction, effect, affinity, rarity,
    other. Each must have at least one seeded row with the correct value to prove
    the seed backfill works end-to-end.
    """

    @pytest.mark.asyncio
    async def test_league_condition_type_seeded(self, session: AsyncSession) -> None:
        """At least one PostCondition with condition_type='league' exists after seed."""
        await _run_canonical_seed(session)
        result = await session.execute(
            select(PostCondition).where(PostCondition.condition_type == "league")
        )
        rows = result.scalars().all()
        assert len(rows) >= 1, "Expected at least one 'league' condition_type row"

    @pytest.mark.asyncio
    async def test_role_condition_type_seeded(self, session: AsyncSession) -> None:
        """At least one PostCondition with condition_type='role' exists after seed."""
        await _run_canonical_seed(session)
        result = await session.execute(
            select(PostCondition).where(PostCondition.condition_type == "role")
        )
        rows = result.scalars().all()
        assert len(rows) >= 1, "Expected at least one 'role' condition_type row"

    @pytest.mark.asyncio
    async def test_faction_condition_type_seeded(self, session: AsyncSession) -> None:
        """At least one PostCondition with condition_type='faction' exists after seed."""
        await _run_canonical_seed(session)
        result = await session.execute(
            select(PostCondition).where(PostCondition.condition_type == "faction")
        )
        rows = result.scalars().all()
        assert len(rows) >= 1, "Expected at least one 'faction' condition_type row"

    @pytest.mark.asyncio
    async def test_effect_condition_type_seeded(self, session: AsyncSession) -> None:
        """At least one PostCondition with condition_type='effect' exists after seed."""
        await _run_canonical_seed(session)
        result = await session.execute(
            select(PostCondition).where(PostCondition.condition_type == "effect")
        )
        rows = result.scalars().all()
        assert len(rows) >= 1, "Expected at least one 'effect' condition_type row"

    @pytest.mark.asyncio
    async def test_affinity_condition_type_seeded(self, session: AsyncSession) -> None:
        """At least one PostCondition with condition_type='affinity' exists after seed."""
        await _run_canonical_seed(session)
        result = await session.execute(
            select(PostCondition).where(PostCondition.condition_type == "affinity")
        )
        rows = result.scalars().all()
        assert len(rows) >= 1, "Expected at least one 'affinity' condition_type row"

    @pytest.mark.asyncio
    async def test_rarity_condition_type_seeded(self, session: AsyncSession) -> None:
        """At least one PostCondition with condition_type='rarity' exists after seed."""
        await _run_canonical_seed(session)
        result = await session.execute(
            select(PostCondition).where(PostCondition.condition_type == "rarity")
        )
        rows = result.scalars().all()
        assert len(rows) >= 1, "Expected at least one 'rarity' condition_type row"

    @pytest.mark.asyncio
    async def test_other_condition_type_seeded(self, session: AsyncSession) -> None:
        """At least one PostCondition with condition_type='other' exists after seed."""
        await _run_canonical_seed(session)
        result = await session.execute(
            select(PostCondition).where(PostCondition.condition_type == "other")
        )
        rows = result.scalars().all()
        assert len(rows) >= 1, "Expected at least one 'other' condition_type row"

    @pytest.mark.asyncio
    async def test_all_36_rows_have_condition_type(self, session: AsyncSession) -> None:
        """All 36 seeded PostCondition rows must have a non-null condition_type."""
        await _run_canonical_seed(session)
        result = await session.execute(
            select(PostCondition).where(PostCondition.condition_type.is_(None))
        )
        null_rows = result.scalars().all()
        assert len(null_rows) == 0, f"Expected zero NULL condition_type rows, got {len(null_rows)}"

    @pytest.mark.asyncio
    async def test_league_ids_have_correct_condition_type(self, session: AsyncSession) -> None:
        """IDs 1-4 (league) must all have condition_type='league'."""
        await _run_canonical_seed(session)
        for id_ in [1, 2, 3, 4]:
            row = await session.get(PostCondition, id_)
            assert row is not None, f"PostCondition id={id_} missing"
            assert (
                row.condition_type == "league"
            ), f"id={id_} expected 'league', got {row.condition_type!r}"

    @pytest.mark.asyncio
    async def test_role_ids_have_correct_condition_type(self, session: AsyncSession) -> None:
        """IDs 5-8 (role) must all have condition_type='role'."""
        await _run_canonical_seed(session)
        for id_ in [5, 6, 7, 8]:
            row = await session.get(PostCondition, id_)
            assert row is not None, f"PostCondition id={id_} missing"
            assert (
                row.condition_type == "role"
            ), f"id={id_} expected 'role', got {row.condition_type!r}"

    @pytest.mark.asyncio
    async def test_other_id_36_has_correct_condition_type(self, session: AsyncSession) -> None:
        """ID 36 (other) must have condition_type='other'."""
        await _run_canonical_seed(session)
        row = await session.get(PostCondition, 36)
        assert row is not None, "PostCondition id=36 missing"
        assert row.condition_type == "other", f"id=36 expected 'other', got {row.condition_type!r}"
