#!/usr/bin/env python
"""Seed demo data for local development.

Creates 25 fictional clan members, one siege with those members enrolled,
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
from app.models.siege import Siege
from app.models.siege_member import SiegeMember

# ---------------------------------------------------------------------------
# Demo member pool — 25 fully fictional names
# ---------------------------------------------------------------------------

DEMO_MEMBERS: list[tuple[str, MemberRole, str]] = [
    ("Demo Member 01", MemberRole.heavy_hitter, "gt_25m"),
    ("Demo Member 02", MemberRole.heavy_hitter, "gt_25m"),
    ("Demo Member 03", MemberRole.heavy_hitter, "gt_25m"),
    ("Demo Member 04", MemberRole.advanced, "21_25m"),
    ("Demo Member 05", MemberRole.advanced, "21_25m"),
    ("Demo Member 06", MemberRole.advanced, "21_25m"),
    ("Demo Member 07", MemberRole.advanced, "21_25m"),
    ("Demo Member 08", MemberRole.advanced, "16_20m"),
    ("Demo Member 09", MemberRole.advanced, "16_20m"),
    ("Demo Member 10", MemberRole.advanced, "16_20m"),
    ("Demo Member 11", MemberRole.medium, "16_20m"),
    ("Demo Member 12", MemberRole.medium, "16_20m"),
    ("Demo Member 13", MemberRole.medium, "10_15m"),
    ("Demo Member 14", MemberRole.medium, "10_15m"),
    ("Demo Member 15", MemberRole.medium, "10_15m"),
    ("Demo Member 16", MemberRole.medium, "10_15m"),
    ("Demo Member 17", MemberRole.medium, "10_15m"),
    ("Demo Member 18", MemberRole.novice, "lt_10m"),
    ("Demo Member 19", MemberRole.novice, "lt_10m"),
    ("Demo Member 20", MemberRole.novice, "lt_10m"),
    ("Demo Member 21", MemberRole.novice, "lt_10m"),
    ("Demo Member 22", MemberRole.novice, "lt_10m"),
    ("Demo Member 23", MemberRole.novice, "lt_10m"),
    ("Demo Member 24", MemberRole.novice, "lt_10m"),
    ("Demo Member 25", MemberRole.novice, "lt_10m"),
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
) -> None:
    """Create buildings, groups, and positions; assign members round-robin."""
    # Check if siege already has buildings (idempotency).
    result = await session.execute(select(Building).where(Building.siege_id == siege.id))
    if result.first() is not None:
        return  # Already seeded.

    member_iter = cycle(members)  # Round-robin through members to fill all positions.

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

    await session.flush()


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

    await engine.dispose()
    print(f"Demo seed complete. Siege ID: {siege.id}, Members: {len(members)}")


if __name__ == "__main__":
    asyncio.run(main())
