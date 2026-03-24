"""Schema constraint and seed data tests using in-memory SQLite."""

from datetime import date

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Import all models so metadata is populated
import app.models  # noqa: F401
from app.db.base import Base
from app.db.seeds import seed_building_type_config, seed_post_conditions
from app.models.building_group import BuildingGroup
from app.models.enums import MemberRole, SiegeStatus
from app.models.member import Member
from app.models.siege import Siege
from app.models.siege_member import SiegeMember


def _enable_sqlite_fk(dbapi_conn, _connection_record):
    """Enable SQLite foreign key enforcement."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    # Enable FK enforcement for every connection
    event.listen(engine.sync_engine, "connect", _enable_sqlite_fk)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False)
    async with AsyncSessionFactory() as session:
        yield session

    await engine.dispose()


# ---------------------------------------------------------------------------
# 1. Member name uniqueness
# ---------------------------------------------------------------------------


async def test_member_name_unique(db_session: AsyncSession):
    """Inserting two members with the same name must raise IntegrityError."""
    db_session.add(Member(name="Alice", role=MemberRole.advanced))
    await db_session.flush()

    db_session.add(Member(name="Alice", role=MemberRole.novice))
    with pytest.raises(IntegrityError):
        await db_session.flush()


# ---------------------------------------------------------------------------
# 2. Position state consistency — reserve with member
# ---------------------------------------------------------------------------


async def test_position_reserve_and_member_constraint_defined():
    """The check constraint preventing is_reserve=True with a member_id is defined."""
    from app.models.position import Position

    constraint_names = {c.name for c in Position.__table__.constraints if hasattr(c, "name")}
    assert "reserve_position_cannot_have_member" in constraint_names


# ---------------------------------------------------------------------------
# 3. BuildingGroup slot_count bounds
# ---------------------------------------------------------------------------


async def test_building_group_slot_count_bounds():
    """slot_count check constraints (1–3) are declared on the table."""
    constraint_names = {c.name for c in BuildingGroup.__table__.constraints if hasattr(c, "name")}
    assert "slot_count_range" in constraint_names


# ---------------------------------------------------------------------------
# 4. seed_post_conditions inserts exactly 36 rows
# ---------------------------------------------------------------------------


async def test_post_condition_count(db_session: AsyncSession):
    """seed_post_conditions populates exactly 36 rows."""
    await seed_post_conditions(db_session)
    await db_session.flush()

    result = await db_session.execute(text("SELECT COUNT(*) FROM post_condition"))
    count = result.scalar()
    assert count == 36


# ---------------------------------------------------------------------------
# 5. seed_building_type_config inserts exactly 5 rows
# ---------------------------------------------------------------------------


async def test_building_type_config_count(db_session: AsyncSession):
    """seed_building_type_config populates exactly 5 rows."""
    await seed_building_type_config(db_session)
    await db_session.flush()

    result = await db_session.execute(text("SELECT COUNT(*) FROM building_type_config"))
    count = result.scalar()
    assert count == 5


# ---------------------------------------------------------------------------
# 6. SiegeMember composite PK prevents duplicates
# ---------------------------------------------------------------------------


async def test_siege_member_pk(db_session: AsyncSession):
    """Inserting a duplicate (siege_id, member_id) pair raises IntegrityError."""
    member = Member(name="Bob", role=MemberRole.medium)
    siege = Siege(date=date(2026, 3, 16), status=SiegeStatus.planning, defense_scroll_count=10)
    db_session.add(member)
    db_session.add(siege)
    await db_session.flush()

    db_session.add(SiegeMember(siege_id=siege.id, member_id=member.id))
    await db_session.flush()

    db_session.add(SiegeMember(siege_id=siege.id, member_id=member.id))
    with pytest.raises(IntegrityError):
        await db_session.flush()
