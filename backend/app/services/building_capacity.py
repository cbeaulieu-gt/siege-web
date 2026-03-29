# Teams per building type per level (from game data).
# Post buildings are not listed here — they always have exactly 1 position.
_LEVEL_TEAMS: dict[str, dict[int, int]] = {
    "stronghold": {1: 12, 2: 16, 3: 18, 4: 22, 5: 25, 6: 30},
    "mana_shrine": {1: 6, 2: 7, 3: 9, 4: 11, 5: 13, 6: 15},
    "magic_tower": {1: 2, 2: 3, 3: 4, 4: 5, 5: 7, 6: 9},
    "defense_tower": {1: 2, 2: 3, 3: 4, 4: 6, 5: 9, 6: 12},
}


def get_team_count(building_type: str, level: int) -> int:
    """Return the theoretical total team slots for a building type at a given level.

    This is derived purely from game data in ``_LEVEL_TEAMS`` and is independent
    of database state (no Position or BuildingGroup records are consulted).

    Post buildings are not in ``_LEVEL_TEAMS``; they always have 1 position, so
    the fallback chain ``levels.get(1, 1)`` returns 1 for any unrecognised type.

    Args:
        building_type: The building type as a string or enum with a ``.value``
            attribute (e.g. ``BuildingType.stronghold`` or ``"stronghold"``).
        level: The building level (1–6).

    Returns:
        Total position count for the given type+level combination.
    """
    type_key = building_type.value if hasattr(building_type, "value") else building_type
    levels = _LEVEL_TEAMS.get(type_key, {})
    return levels.get(level, levels.get(1, 1))
