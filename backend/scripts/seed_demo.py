#!/usr/bin/env python
"""Seed demo data for local development.

Creates 28 fictional clan members, one siege with those members enrolled,
and fills most building positions so the board is populated and clickable.

Idempotent: safe to run multiple times — existing rows are left unchanged.

Usage (from backend/):
    python scripts/seed_demo.py
"""

import asyncio
import sys
from datetime import date, timedelta
from itertools import cycle
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.seeds import seed_building_type_config, seed_post_conditions, seed_post_priority_config
from app.models.building import Building
from app.models.building_group import BuildingGroup
from app.models.enums import BuildingType, MemberRole, SiegeStatus
from app.models.member import Member
from app.models.position import Position
from app.models.post import Post
from app.models.post_priority_config import PostPriorityConfig
from app.models.siege import Siege
from app.models.siege_member import SiegeMember

# ---------------------------------------------------------------------------
# Demo member pool — 28 fully fictional names
# ---------------------------------------------------------------------------

DEMO_MEMBERS: list[tuple[str, MemberRole, str]] = [
    # Heavy Hitters (5) — gt_25m
    ("Grimmaw",   MemberRole.heavy_hitter, "gt_25m"),
    ("Valdris",   MemberRole.heavy_hitter, "gt_25m"),
    ("Korath",    MemberRole.heavy_hitter, "gt_25m"),
    ("Thornclaw", MemberRole.heavy_hitter, "gt_25m"),
    ("Malakar",   MemberRole.heavy_hitter, "gt_25m"),
    # Advanced (7) — 3 at 21_25m, 4 at 16_20m
    ("Drakemoor", MemberRole.advanced, "21_25m"),
    ("Sylvaris",  MemberRole.advanced, "21_25m"),
    ("Varek",     MemberRole.advanced, "21_25m"),
    ("Kaelith",   MemberRole.advanced, "16_20m"),
    ("Morvain",   MemberRole.advanced, "16_20m"),
    ("Rhogar",    MemberRole.advanced, "16_20m"),
    ("Ashborne",  MemberRole.advanced, "16_20m"),
    # Medium (7) — 2 at 16_20m, 5 at 10_15m
    ("Brennan",   MemberRole.medium, "16_20m"),
    ("Tovik",     MemberRole.medium, "16_20m"),
    ("Sellira",   MemberRole.medium, "10_15m"),
    ("Jorund",    MemberRole.medium, "10_15m"),
    ("Marek",     MemberRole.medium, "10_15m"),
    ("Dravak",    MemberRole.medium, "10_15m"),
    ("Linneth",   MemberRole.medium, "10_15m"),
    # Novice (9) — lt_10m
    ("Tamsin",    MemberRole.novice, "lt_10m"),
    ("Wren",      MemberRole.novice, "lt_10m"),
    ("Orrin",     MemberRole.novice, "lt_10m"),
    ("Finnick",   MemberRole.novice, "lt_10m"),
    ("Perrin",    MemberRole.novice, "lt_10m"),
    ("Lira",      MemberRole.novice, "lt_10m"),
    ("Kessen",    MemberRole.novice, "lt_10m"),
    ("Brandis",   MemberRole.novice, "lt_10m"),
    ("Noll",      MemberRole.novice, "lt_10m"),
]

# Building layout: (type, building_number, level, group_count, slots_per_group)
# This mirrors a typical competitive clan setup.
DEMO_BUILDINGS: list[tuple[BuildingType, int, int, int, int]] = [
    (BuildingType.stronghold, 1, 3, 4, 3),
    (BuildingType.mana_shrine, 1, 2, 2, 3),
    (BuildingType.mana_shrine, 2, 2, 2, 3),
    (BuildingType.magic_tower, 1, 2, 1, 2),
    (BuildingType.magic_tower, 2, 2, 1, 2),
    (BuildingType.magic_tower, 3, 1, 1, 2),
    (BuildingType.magic_tower, 4, 1, 1, 2),
    (BuildingType.defense_tower, 1, 2, 1, 2),
    (BuildingType.defense_tower, 2, 2, 1, 2),
    (BuildingType.defense_tower, 3, 1, 1, 2),
    (BuildingType.defense_tower, 4, 1, 1, 2),
    (BuildingType.defense_tower, 5, 1, 1, 2),
    # 18 post buildings — each has 1 group with 1 slot
    *[(BuildingType.post, n, 1, 1, 1) for n in range(1, 19)],
]


async def get_or_create_members(session: AsyncSession) -> list[Member]:
    """Return existing demo members or create them."""
    members = []
    for name, role, power_level in DEMO_MEMBERS:
        result = await session.execute(select(Member).where(Member.name == name))
        member = result.scalar_one_or_none()
        if member is None:
            member = Member(
                name=name,
                role=role,
                power_level=power_level,
                is_active=True,
            )
            session.add(member)
            await session.flush()
        members.append(member)
    return members


async def get_or_create_demo_siege(session: AsyncSession) -> Siege:
    """Return the existing demo siege or create a new one."""
    result = await session.execute(select(Siege).where(Siege.status == SiegeStatus.active).limit(1))
    siege = result.scalar_one_or_none()
    if siege is None:
        # Use the upcoming Saturday as the siege date (or today + 3 days).
        today = date.today()
        days_until_saturday = (5 - today.weekday()) % 7
        siege_date = today + timedelta(days=days_until_saturday if days_until_saturday else 7)
        siege = Siege(
            date=siege_date,
            status=SiegeStatus.active,
            defense_scroll_count=6,
        )
        session.add(siege)
        await session.flush()
    return siege


async def seed_buildings_and_positions(
    session: AsyncSession,
    siege: Siege,
    members: list[Member],
    member_start: int = 0,
) -> None:
    """Create buildings, groups, and positions; assign members round-robin.

    member_start offsets which member the cycle begins at, so a second siege
    can have a visibly different assignment order for comparison screenshots.
    """
    # Check if siege already has buildings (idempotency).
    result = await session.execute(select(Building).where(Building.siege_id == siege.id))
    if result.first() is not None:
        return  # Already seeded.

    # Rotate the member list so the second siege shows different assignments.
    rotated = members[member_start:] + members[:member_start]
    member_iter = cycle(rotated)

    for building_type, building_number, level, group_count, slots in DEMO_BUILDINGS:
        building = Building(
            siege_id=siege.id,
            building_type=building_type,
            building_number=building_number,
            level=level,
        )
        session.add(building)
        await session.flush()

        for group_number in range(1, group_count + 1):
            group = BuildingGroup(
                building_id=building.id,
                group_number=group_number,
                slot_count=slots,
            )
            session.add(group)
            await session.flush()

            for position_number in range(1, slots + 1):
                # Leave the last position of each group empty for visual variety.
                assign_member = position_number < slots
                member = next(member_iter) if assign_member else None
                position = Position(
                    building_group_id=group.id,
                    position_number=position_number,
                    member_id=member.id if member else None,
                )
                session.add(position)

        # Post-type buildings require a matching Post record.
        if building_type == BuildingType.post:
            ppc_result = await session.execute(
                select(PostPriorityConfig).where(
                    PostPriorityConfig.post_number == building_number
                )
            )
            ppc = ppc_result.scalar_one_or_none()
            session.add(
                Post(
                    siege_id=siege.id,
                    building_id=building.id,
                    priority=ppc.priority if ppc else 2,
                    description=ppc.description if ppc else None,
                )
            )

    await session.flush()


async def get_or_create_second_siege(session: AsyncSession, first_siege: Siege) -> Siege:
    """Return the existing planning siege or create one one week after the first."""
    result = await session.execute(
        select(Siege).where(Siege.status == SiegeStatus.planning).limit(1)
    )
    siege = result.scalar_one_or_none()
    if siege is None:
        siege = Siege(
            date=first_siege.date + timedelta(weeks=1),
            status=SiegeStatus.planning,
            defense_scroll_count=6,
        )
        session.add(siege)
        await session.flush()
    return siege


async def seed_siege_members(
    session: AsyncSession,
    siege: Siege,
    members: list[Member],
) -> None:
    """Enrol members in the siege with attack day assignments."""
    result = await session.execute(select(SiegeMember).where(SiegeMember.siege_id == siege.id))
    if result.first() is not None:
        return  # Already seeded.

    for i, member in enumerate(members):
        attack_day = 1 if i % 2 == 0 else 2
        sm = SiegeMember(
            siege_id=siege.id,
            member_id=member.id,
            attack_day=attack_day,
        )
        session.add(sm)

    await session.flush()


async def main() -> None:
    engine = create_async_engine(settings.database_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        # Always ensure reference data is present.
        print("Seeding reference data...")
        await seed_post_conditions(session)
        await seed_building_type_config(session)
        await seed_post_priority_config(session)
        await session.commit()

        # Demo members.
        print("Seeding demo members...")
        members = await get_or_create_members(session)
        await session.commit()

        # Demo siege.
        print("Seeding demo siege...")
        siege = await get_or_create_demo_siege(session)
        await session.commit()

        # Buildings, groups, positions.
        print("Seeding demo board positions...")
        await seed_buildings_and_positions(session, siege, members)
        await session.commit()

        # Siege member enrollments.
        print("Seeding siege member enrollments...")
        await seed_siege_members(session, siege, members)
        await session.commit()

        # Second (planning) siege — same layout, shifted member assignments.
        print("Seeding second (planning) siege...")
        siege2 = await get_or_create_second_siege(session, siege)
        await session.commit()

        print("Seeding second siege board positions...")
        # Shift member rotation by 7 so ~25% of assignments visibly differ.
        await seed_buildings_and_positions(session, siege2, members, member_start=7)
        await session.commit()

        print("Seeding second siege member enrollments...")
        await seed_siege_members(session, siege2, members)
        await session.commit()

    await engine.dispose()
    print(
        f"Demo seed complete. "
        f"Siege 1 ID: {siege.id} (active), "
        f"Siege 2 ID: {siege2.id} (planning), "
        f"Members: {len(members)}"
    )


if __name__ == "__main__":
    asyncio.run(main())
