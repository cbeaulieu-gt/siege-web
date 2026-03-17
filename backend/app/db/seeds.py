"""Seed functions for reference/static data tables."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def seed_post_conditions(session: AsyncSession) -> None:
    """Insert all 36 PostCondition rows. Safe to re-run (ON CONFLICT DO NOTHING)."""
    rows = [
        # Level 1 (18 conditions)
        (1, "Only Champions from the Telerian League can be used.", 1),
        (2, "Only Champions from the Gaellen Pact can be used.", 1),
        (3, "Only Champions from The Corrupted can be used.", 1),
        (4, "Only Champions from the Nyresan Union can be used.", 1),
        (5, "Only HP Champions can be used.", 1),
        (6, "Only DEF Champions can be used.", 1),
        (7, "Only Support Champions can be used.", 1),
        (8, "Only ATK Champions can be used.", 1),
        (9, "Only Banner Lord Champions can be used.", 1),
        (10, "Only High Elves Champions can be used.", 1),
        (11, "Only Sacred Order Champions can be used.", 1),
        (12, "Only Barbarian Champions can be used.", 1),
        (13, "Only Ogryn Tribe Champions can be used.", 1),
        (14, "Only Lizardmen Champions can be used.", 1),
        (15, "Only Skinwalker Champions can be used.", 1),
        (16, "Only Orc Champions can be used.", 1),
        (17, "All Champions are immune to Turn Meter reduction effects.", 1),
        (18, "All Champions are immune to Turn Meter fill effects.", 1),
        # Level 2 (10 conditions)
        (19, "Only Void Champions can be used.", 2),
        (20, "Only Force Champions can be used.", 2),
        (21, "Only Magic Champions can be used.", 2),
        (22, "Only Spirit Champions can be used.", 2),
        (23, "Only Demonspawn Champions can be used.", 2),
        (24, "Only Undead Horde Champions can be used.", 2),
        (25, "Only Dark Elves Champions can be used.", 2),
        (26, "Only Knights Revenant Champions can be used.", 2),
        (27, "All Champions are immune to cooldown increasing effects.", 2),
        (28, "All Champions are immune to cooldown decreasing effects.", 2),
        # Level 3 (8 conditions)
        (29, "Only Legendary Champions can be used.", 3),
        (30, "Only Epic Champions can be used.", 3),
        (31, "Only Rare Champions can be used.", 3),
        (32, "Only Dwarves Champions can be used.", 3),
        (33, "Only Shadowkin Champions can be used.", 3),
        (34, "Only Sylvan Watcher Champions can be used.", 3),
        (35, "All Champions are immune to [Sheep] debuffs.", 3),
        (36, "Champions cannot be revived.", 3),
    ]
    await session.execute(
        text(
            "INSERT INTO post_condition (id, description, stronghold_level) "
            "VALUES (:id, :description, :stronghold_level) "
            "ON CONFLICT DO NOTHING"
        ),
        [
            {"id": id_, "description": description, "stronghold_level": level}
            for id_, description, level in rows
        ],
    )


async def seed_building_type_config(session: AsyncSession) -> None:
    """Insert all 5 BuildingTypeConfig rows. Safe to re-run (ON CONFLICT DO NOTHING)."""
    rows = [
        ("stronghold", 1, 4, 3),
        ("mana_shrine", 2, 2, 3),
        ("magic_tower", 4, 1, 2),
        ("defense_tower", 5, 1, 2),
        ("post", 18, 1, 1),
    ]
    await session.execute(
        text(
            "INSERT INTO building_type_config "
            "(building_type, count, base_group_count, base_last_group_slots) "
            "VALUES (:building_type, :count, :base_group_count, :base_last_group_slots) "
            "ON CONFLICT DO NOTHING"
        ),
        [
            {
                "building_type": bt,
                "count": count,
                "base_group_count": bgc,
                "base_last_group_slots": blgs,
            }
            for bt, count, bgc, blgs in rows
        ],
    )
