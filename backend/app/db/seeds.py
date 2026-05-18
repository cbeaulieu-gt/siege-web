"""Seed functions for reference/static data tables."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def seed_post_conditions(session: AsyncSession) -> None:
    """Insert all 36 PostCondition rows. Safe to re-run (ON CONFLICT DO NOTHING).

    Each tuple is (id, description, stronghold_level, condition_type).
    The condition_type values mirror the canonical frontend map in
    ``frontend/src/lib/postConditionTypes.ts``.
    """
    rows = [
        # Level 1 (18 conditions)
        (1, "Only Champions from the Telerian League can be used.", 1, "league"),
        (2, "Only Champions from the Gaellen Pact can be used.", 1, "league"),
        (3, "Only Champions from The Corrupted can be used.", 1, "league"),
        (4, "Only Champions from the Nyresan Union can be used.", 1, "league"),
        (5, "Only HP Champions can be used.", 1, "role"),
        (6, "Only DEF Champions can be used.", 1, "role"),
        (7, "Only Support Champions can be used.", 1, "role"),
        (8, "Only ATK Champions can be used.", 1, "role"),
        (9, "Only Banner Lord Champions can be used.", 1, "faction"),
        (10, "Only High Elves Champions can be used.", 1, "faction"),
        (11, "Only Sacred Order Champions can be used.", 1, "faction"),
        (12, "Only Barbarian Champions can be used.", 1, "faction"),
        (13, "Only Ogryn Tribe Champions can be used.", 1, "faction"),
        (14, "Only Lizardmen Champions can be used.", 1, "faction"),
        (15, "Only Skinwalker Champions can be used.", 1, "faction"),
        (16, "Only Orc Champions can be used.", 1, "faction"),
        (17, "All Champions are immune to Turn Meter reduction effects.", 1, "effect"),
        (18, "All Champions are immune to Turn Meter fill effects.", 1, "effect"),
        # Level 2 (10 conditions)
        (19, "Only Void Champions can be used.", 2, "affinity"),
        (20, "Only Force Champions can be used.", 2, "affinity"),
        (21, "Only Magic Champions can be used.", 2, "affinity"),
        (22, "Only Spirit Champions can be used.", 2, "affinity"),
        (23, "Only Demonspawn Champions can be used.", 2, "faction"),
        (24, "Only Undead Horde Champions can be used.", 2, "faction"),
        (25, "Only Dark Elves Champions can be used.", 2, "faction"),
        (26, "Only Knights Revenant Champions can be used.", 2, "faction"),
        (27, "All Champions are immune to cooldown increasing effects.", 2, "effect"),
        (28, "All Champions are immune to cooldown decreasing effects.", 2, "effect"),
        # Level 3 (8 conditions)
        (29, "Only Legendary Champions can be used.", 3, "rarity"),
        (30, "Only Epic Champions can be used.", 3, "rarity"),
        (31, "Only Rare Champions can be used.", 3, "rarity"),
        (32, "Only Dwarves Champions can be used.", 3, "faction"),
        (33, "Only Shadowkin Champions can be used.", 3, "faction"),
        (34, "Only Sylvan Watcher Champions can be used.", 3, "faction"),
        (35, "All Champions are immune to [Sheep] debuffs.", 3, "effect"),
        (36, "Champions cannot be revived.", 3, "other"),
    ]
    await session.execute(
        text(
            "INSERT INTO post_condition "
            "(id, description, stronghold_level, condition_type) "
            "VALUES (:id, :description, :stronghold_level, :condition_type) "
            "ON CONFLICT DO NOTHING"
        ),
        [
            {
                "id": id_,
                "description": description,
                "stronghold_level": level,
                "condition_type": condition_type,
            }
            for id_, description, level, condition_type in rows
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


async def seed_post_priority_config(session: AsyncSession) -> None:
    """Insert all 18 PostPriorityConfig rows with default priority=2.

    Safe to re-run (ON CONFLICT DO NOTHING).
    """
    await session.execute(
        text(
            "INSERT INTO post_priority_config (post_number, priority) "
            "VALUES (:post_number, :priority) "
            "ON CONFLICT DO NOTHING"
        ),
        [{"post_number": n, "priority": 2} for n in range(1, 19)],
    )
