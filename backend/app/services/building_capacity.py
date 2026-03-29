from app.models.enums import BuildingType

# Teams per building type per level (from game data).
# Post buildings are not listed here — they always have exactly 1 position.
_LEVEL_TEAMS: dict[str, dict[int, int]] = {
    "stronghold": {1: 12, 2: 16, 3: 18, 4: 22, 5: 25, 6: 30},
    "mana_shrine": {1: 6, 2: 7, 3: 9, 4: 11, 5: 13, 6: 15},
    "magic_tower": {1: 2, 2: 3, 3: 4, 4: 5, 5: 7, 6: 9},
    "defense_tower": {1: 2, 2: 3, 3: 4, 4: 6, 5: 9, 6: 12},
}


def get_team_count(building_type: str | BuildingType, level: int) -> int:
    """Return the theoretical total team slots for a building type at a given level.

    This is derived purely from game data in ``_LEVEL_TEAMS`` and is independent
    of database state (no Position or BuildingGroup records are consulted).

    Post buildings always have exactly 1 position and are handled explicitly before
    the lookup table is consulted.  Any building type that is not ``post`` and is
    also not found in ``_LEVEL_TEAMS`` raises ``ValueError`` — this catches typos
    and new enum values that haven't been added to the table yet.

    Args:
        building_type: The building type as a string or ``BuildingType`` enum value
            (e.g. ``BuildingType.stronghold`` or ``"stronghold"``).
        level: The building level (1–6).

    Returns:
        Total position count for the given type+level combination.

    Raises:
        ValueError: If ``building_type`` is not ``post`` and has no entry in
            ``_LEVEL_TEAMS``.  Add the missing type to ``_LEVEL_TEAMS`` to fix.
    """
    type_key = building_type.value if hasattr(building_type, "value") else building_type

    if type_key == BuildingType.post.value:
        return 1

    levels = _LEVEL_TEAMS.get(type_key)
    if levels is None:
        raise ValueError(
            f"Unknown building type '{type_key}' — add it to _LEVEL_TEAMS in building_capacity.py"
        )
    return levels.get(level, levels[1])
