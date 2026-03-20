"""
Tests for scripts/import_excel.py parsing logic.

All tests are pure-function tests that do not require a database connection.
"""

import sys
import os
from datetime import date
from unittest.mock import MagicMock

import pytest

# Add scripts dir to path so we can import import_excel directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
# Add backend dir to path so import_excel can import from app.*
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

import import_excel as ie


# ---------------------------------------------------------------------------
# test_parse_filename
# ---------------------------------------------------------------------------


def test_parse_filename():
    """Extracts a valid date from a canonical MM_DD_YYYY filename."""
    result = ie.parse_filename_date("clan_siege_03_15_2026.xlsm")
    assert result == date(2026, 3, 15)


def test_parse_filename_with_path_prefix():
    """Extracts date even when the filename has a path prefix passed as string."""
    result = ie.parse_filename_date("/some/path/clan_siege_12_01_2025.xlsm")
    assert result == date(2025, 12, 1)


# ---------------------------------------------------------------------------
# test_parse_filename_invalid
# ---------------------------------------------------------------------------


def test_parse_filename_invalid_no_match():
    """Returns None for a filename that does not match the pattern."""
    result = ie.parse_filename_date("siege_assignments.xlsx")
    assert result is None


def test_parse_filename_invalid_random():
    """Returns None for a completely unrelated filename."""
    result = ie.parse_filename_date("report.xlsm")
    assert result is None


def test_parse_filename_invalid_impossible_date():
    """Returns None when the extracted date components don't form a valid date."""
    result = ie.parse_filename_date("clan_siege_32_13_2026.xlsm")
    assert result is None


# ---------------------------------------------------------------------------
# test_role_mapping
# ---------------------------------------------------------------------------


def test_role_mapping_heavy_hitter():
    assert ie.map_role("Heavy Hitter") == "heavy_hitter"


def test_role_mapping_advanced():
    assert ie.map_role("Advanced") == "advanced"


def test_role_mapping_medium():
    assert ie.map_role("Medium") == "medium"


def test_role_mapping_novice():
    assert ie.map_role("Novice") == "novice"


def test_role_mapping_unknown_returns_none():
    assert ie.map_role("Elite") is None


# ---------------------------------------------------------------------------
# test_building_alias_mapping
# ---------------------------------------------------------------------------


def test_building_alias_stronghold():
    assert ie.map_building_alias("Stronghold") == ("stronghold", None)


def test_building_alias_mana_shrine_full():
    assert ie.map_building_alias("Mana Shrine") == ("mana_shrine", None)


def test_building_alias_mana_short():
    assert ie.map_building_alias("Mana") == ("mana_shrine", None)


def test_building_alias_magic_tower_full():
    assert ie.map_building_alias("Magic Tower") == ("magic_tower", None)


def test_building_alias_magic_short():
    assert ie.map_building_alias("Magic") == ("magic_tower", None)


def test_building_alias_defense_tower_full():
    assert ie.map_building_alias("Defense Tower") == ("defense_tower", None)


def test_building_alias_defense_short():
    assert ie.map_building_alias("Defense") == ("defense_tower", None)


def test_building_alias_post():
    assert ie.map_building_alias("Post") == ("post", None)


def test_building_alias_unknown_returns_none():
    assert ie.map_building_alias("Barracks") == (None, None)


# ---------------------------------------------------------------------------
# test_parse_members_sheet
# ---------------------------------------------------------------------------


def _make_worksheet(rows: list[tuple]) -> MagicMock:
    """Create a mock openpyxl worksheet that yields the given rows."""
    ws = MagicMock()
    ws.iter_rows.return_value = iter(rows)
    return ws


def test_parse_members_sheet_basic():
    """Parses name, power_level bucket, and role from correct column positions."""
    ws = _make_worksheet(
        [
            # (name, level_placeholder, power, role, post_restrictions)
            ("Alice", None, 5_000_000, "Heavy Hitter", None),
            ("Bob", None, 3_500_000, "Advanced", None),
            ("Charlie", None, None, "Novice", None),
        ]
    )
    members = ie.parse_members_sheet(ws)
    assert len(members) == 3

    assert members[0].name == "Alice"
    assert members[0].role == "Heavy Hitter"
    # 5_000_000 < 10_000_000 -> "lt_10m"
    assert members[0].power_level == "lt_10m"
    # discord_username is never populated from the sheet
    assert members[0].discord_username is None

    assert members[1].name == "Bob"
    # 3_500_000 < 10_000_000 -> "lt_10m"
    assert members[1].power_level == "lt_10m"

    assert members[2].name == "Charlie"
    assert members[2].power_level is None


def test_parse_members_sheet_skips_empty_rows():
    ws = _make_worksheet(
        [
            # (name, level_placeholder, power, role, post_restrictions)
            ("Alice", None, 2_000_000, "Medium", None),
            (None, None, None, None, None),   # empty row — should be skipped
            ("", None, None, "Novice", None),  # blank name — should be skipped
        ]
    )
    members = ie.parse_members_sheet(ws)
    assert len(members) == 1
    assert members[0].name == "Alice"


def test_parse_members_sheet_strips_whitespace():
    ws = _make_worksheet(
        [
            # (name, level_placeholder, power, role, post_restrictions)
            ("  Dave  ", None, 1_000_000, "  Advanced  ", None),
        ]
    )
    members = ie.parse_members_sheet(ws)
    assert members[0].name == "Dave"
    # role is stored as-is (stripped)
    assert members[0].role == "Advanced"
    # discord_username is always None (not in sheet)
    assert members[0].discord_username is None


def test_parse_members_sheet_post_preferences():
    """Column E is parsed as a slash-separated list of keyword strings."""
    ws = _make_worksheet(
        [
            # (name, level_placeholder, power, role, post_restrictions)
            ("Alice", None, 5_000_000, "Heavy Hitter", "HP/DEF/Void"),
        ]
    )
    members = ie.parse_members_sheet(ws)
    assert len(members) == 1
    assert members[0].post_preference_keywords == ["HP", "DEF", "Void"]


def test_parse_members_sheet_post_preferences_empty():
    """Empty or None column E results in an empty list."""
    ws = _make_worksheet(
        [
            # None in column E
            ("Alice", None, 5_000_000, "Heavy Hitter", None),
        ]
    )
    members = ie.parse_members_sheet(ws)
    assert members[0].post_preference_keywords == []

    ws2 = _make_worksheet(
        [
            # Whitespace-only in column E
            ("Bob", None, 5_000_000, "Advanced", "   "),
        ]
    )
    members2 = ie.parse_members_sheet(ws2)
    assert members2[0].post_preference_keywords == []


# ---------------------------------------------------------------------------
# test_parse_assignments_sheet
# ---------------------------------------------------------------------------


def _make_assignments_worksheet(data_rows: list[tuple], position_count: int) -> MagicMock:
    """
    Build a mock assignments worksheet with the proper two header rows prepended.

    The sub-header row (row 2) has None in cols A and B, then integers 1..position_count
    in cols C onward so the parser can detect the position count.
    """
    header_row = ("Location", "Group", "Assigned") + (None,) * (position_count - 1)
    subheader_row = (None, None) + tuple(range(1, position_count + 1))
    all_rows = [header_row, subheader_row] + list(data_rows)
    ws = MagicMock()
    ws.iter_rows.return_value = iter(all_rows)
    return ws


def test_parse_assignments_sheet_member_assignment():
    ws = _make_assignments_worksheet(
        [
            # col A=building, col B=group, col C=pos1, col D=pos2, ...
            ("Mana Shrine", 1, "Alice", "Bob"),
            ("Post", 1, "RESERVE", None),
            ("Magic Tower", 1, None, None),
        ],
        position_count=2,
    )
    assignments = ie.parse_assignments_sheet(ws)
    # 3 data rows × 2 positions = 6 ParsedAssignments
    assert len(assignments) == 6

    # Mana Shrine group 1, position 1
    assert assignments[0].building_type == "mana_shrine"
    assert assignments[0].building_number == 1
    assert assignments[0].group_number == 1
    assert assignments[0].position_number == 1
    assert assignments[0].value == "Alice"

    # Mana Shrine group 1, position 2
    assert assignments[1].value == "Bob"

    # Post group 1, position 1
    assert assignments[2].building_type == "post"
    assert assignments[2].value == "RESERVE"

    # Post group 1, position 2
    assert assignments[3].value is None

    # Magic Tower group 1, position 1
    assert assignments[4].building_type == "magic_tower"
    assert assignments[4].value is None


def test_parse_assignments_sheet_skips_unknown_building_type():
    ws = _make_assignments_worksheet(
        [
            ("Unknown", 1, "Alice", None),
            ("Stronghold", 1, "Bob", None),
        ],
        position_count=2,
    )
    assignments = ie.parse_assignments_sheet(ws)
    # Only the stronghold row should survive
    stronghold_assignments = [a for a in assignments if a.building_type == "stronghold"]
    assert len(stronghold_assignments) == 2
    assert stronghold_assignments[0].value == "Bob"


def test_parse_assignments_sheet_skips_incomplete_rows():
    """Rows with a None group cell are skipped."""
    ws = _make_assignments_worksheet(
        [
            ("Post", None, "Alice"),   # group is None — skipped
        ],
        position_count=1,
    )
    assignments = ie.parse_assignments_sheet(ws)
    assert len(assignments) == 0


def test_parse_assignments_sheet_empty_value_is_none():
    """Whitespace-only cell values normalise to None."""
    ws = _make_assignments_worksheet(
        [("Post", 1, "  ")],
        position_count=1,
    )
    assignments = ie.parse_assignments_sheet(ws)
    assert len(assignments) == 1
    assert assignments[0].value is None


# ---------------------------------------------------------------------------
# test_parse_reserves_sheet
# ---------------------------------------------------------------------------


def test_parse_reserves_sheet_basic():
    ws = _make_worksheet(
        [
            # (member_name, attack_day, has_reserve_set)
            ("Alice", 1, "Yes"),
            ("Bob", 2, "No"),
            ("Charlie", None, None),
        ]
    )
    reserves = ie.parse_reserves_sheet(ws)
    assert len(reserves) == 3

    assert reserves[0].member_name == "Alice"
    assert reserves[0].attack_day == 1
    assert reserves[0].has_reserve_set is True

    assert reserves[1].attack_day == 2
    assert reserves[1].has_reserve_set is False

    assert reserves[2].attack_day is None
    assert reserves[2].has_reserve_set is None


def test_parse_reserves_sheet_skips_empty_rows():
    ws = _make_worksheet(
        [
            ("Alice", 1, "Yes"),
            (None, 2, "No"),  # no name — skip
        ]
    )
    reserves = ie.parse_reserves_sheet(ws)
    assert len(reserves) == 1
    assert reserves[0].member_name == "Alice"


def test_parse_reserves_sheet_invalid_attack_day_ignored():
    ws = _make_worksheet([("Alice", 3, "Yes")])  # day 3 is invalid
    reserves = ie.parse_reserves_sheet(ws)
    assert reserves[0].attack_day is None


def test_parse_reserves_sheet_case_insensitive_yes_no():
    ws = _make_worksheet(
        [
            ("Alice", 1, "YES"),
            ("Bob", 2, "no"),
        ]
    )
    reserves = ie.parse_reserves_sheet(ws)
    assert reserves[0].has_reserve_set is True
    assert reserves[1].has_reserve_set is False


# ---------------------------------------------------------------------------
# test_build_group_structure
# ---------------------------------------------------------------------------


def test_build_group_structure_stronghold():
    """Stronghold: 4 groups all with 3 slots."""
    slots = ie.build_group_structure("stronghold")
    assert slots == [3, 3, 3, 3]


def test_build_group_structure_mana_shrine():
    """Mana shrine: 2 groups both with 3 slots."""
    slots = ie.build_group_structure("mana_shrine")
    assert slots == [3, 3]


def test_build_group_structure_magic_tower():
    """Magic tower: 1 group with 2 slots."""
    slots = ie.build_group_structure("magic_tower")
    assert slots == [2]


def test_build_group_structure_defense_tower():
    """Defense tower: 1 group with 2 slots."""
    slots = ie.build_group_structure("defense_tower")
    assert slots == [2]


def test_build_group_structure_post():
    """Post: 1 group with 1 slot."""
    slots = ie.build_group_structure("post")
    assert slots == [1]


# ---------------------------------------------------------------------------
# test_compute_building_group_structure
# ---------------------------------------------------------------------------


def test_compute_building_group_structure_basic():
    """
    Mana shrine with 2 groups: position 3 is an empty trailing sheet column for group 2,
    but mana_shrine has base_last_slots=3 so both groups still get slot_count=3.
    """
    assignments = [
        ie.ParsedAssignment("mana_shrine", 1, 1, 1, "Alice"),
        ie.ParsedAssignment("mana_shrine", 1, 1, 2, "Bob"),
        ie.ParsedAssignment("mana_shrine", 1, 1, 3, None),   # trailing empty column
        ie.ParsedAssignment("mana_shrine", 1, 2, 1, "Charlie"),
        ie.ParsedAssignment("mana_shrine", 1, 2, 2, None),
        ie.ParsedAssignment("mana_shrine", 1, 2, 3, None),   # trailing empty column
        # Different building instance — should be ignored
        ie.ParsedAssignment("mana_shrine", 2, 1, 1, "Dave"),
    ]
    result = ie.compute_building_group_structure(assignments, "mana_shrine", 1)
    # Both groups get 3 slots: base_last_slots=3 for mana_shrine, nothing overrides it.
    assert result == {1: 3, 2: 3}


def test_compute_building_group_structure_magic_tower_no_inflation():
    """
    Magic tower (base_last_slots=2): position 3 is a trailing empty sheet column and
    must NOT inflate the slot count to 3.
    """
    assignments = [
        ie.ParsedAssignment("magic_tower", 1, 1, 1, "Alice"),
        ie.ParsedAssignment("magic_tower", 1, 1, 2, "Bob"),
        ie.ParsedAssignment("magic_tower", 1, 1, 3, None),   # trailing empty — must be excluded
    ]
    result = ie.compute_building_group_structure(assignments, "magic_tower", 1)
    assert result == {1: 2}


def test_compute_building_group_structure_magic_tower_higher_level():
    """
    Magic tower at a higher level where position 3 is genuinely filled:
    slot_count should be 3.
    """
    assignments = [
        ie.ParsedAssignment("magic_tower", 1, 1, 1, "Alice"),
        ie.ParsedAssignment("magic_tower", 1, 1, 2, "Bob"),
        ie.ParsedAssignment("magic_tower", 1, 1, 3, "Charlie"),  # real slot at level 2+
    ]
    result = ie.compute_building_group_structure(assignments, "magic_tower", 1)
    assert result == {1: 3}


def test_compute_building_group_structure_post_no_inflation():
    """
    Post (base_last_slots=1): positions 2 and 3 are always empty trailing columns.
    """
    assignments = [
        ie.ParsedAssignment("post", 1, 1, 1, "RESERVE"),
        ie.ParsedAssignment("post", 1, 1, 2, None),
        ie.ParsedAssignment("post", 1, 1, 3, None),
    ]
    result = ie.compute_building_group_structure(assignments, "post", 1)
    assert result == {1: 1}


def test_compute_building_group_structure_filters_by_building_number():
    """Only assignments for the specified (type, number) pair are counted."""
    assignments = [
        ie.ParsedAssignment("magic_tower", 1, 1, 1, "Alice"),
        ie.ParsedAssignment("magic_tower", 1, 1, 2, "Bob"),
        ie.ParsedAssignment("magic_tower", 1, 1, 3, None),
        ie.ParsedAssignment("magic_tower", 2, 1, 1, "Charlie"),
        ie.ParsedAssignment("magic_tower", 2, 1, 2, None),
        ie.ParsedAssignment("magic_tower", 2, 1, 3, None),
    ]
    result_1 = ie.compute_building_group_structure(assignments, "magic_tower", 1)
    assert result_1 == {1: 2}  # Alice+Bob fill pos 1+2; pos 3 empty → base_last=2

    result_2 = ie.compute_building_group_structure(assignments, "magic_tower", 2)
    assert result_2 == {1: 2}  # only pos 1 filled; pos 2+3 empty → base_last=2


def test_compute_building_group_structure_stronghold_level2():
    """
    Stronghold level 2 = 16 total slots = 5 full groups (3 slots each) + 1 last group
    with only 1 real slot.  The last group has 1 member assigned; positions 2 and 3
    are trailing empty columns.  The result must be {1:3, 2:3, 3:3, 4:3, 5:3, 6:1}
    (total 16), not {…, 6:3} (total 18 → level 3).
    """
    assignments = []
    for grp in range(1, 6):
        for pos in range(1, 4):
            assignments.append(ie.ParsedAssignment("stronghold", 1, grp, pos, f"Member{grp}{pos}"))
    # Last group: only position 1 is real, positions 2 and 3 are trailing empty cols
    assignments.append(ie.ParsedAssignment("stronghold", 1, 6, 1, "LastMember"))
    assignments.append(ie.ParsedAssignment("stronghold", 1, 6, 2, None))
    assignments.append(ie.ParsedAssignment("stronghold", 1, 6, 3, None))

    result = ie.compute_building_group_structure(assignments, "stronghold", 1)
    assert result == {1: 3, 2: 3, 3: 3, 4: 3, 5: 3, 6: 1}
    assert sum(result.values()) == 16


def test_compute_building_group_structure_stronghold_level4():
    """
    Stronghold level 4 = 22 total slots = 7 full groups + 1 last group with 1 slot.
    """
    assignments = []
    for grp in range(1, 8):
        for pos in range(1, 4):
            assignments.append(ie.ParsedAssignment("stronghold", 1, grp, pos, f"M{grp}{pos}"))
    assignments.append(ie.ParsedAssignment("stronghold", 1, 8, 1, "Last"))
    assignments.append(ie.ParsedAssignment("stronghold", 1, 8, 2, None))
    assignments.append(ie.ParsedAssignment("stronghold", 1, 8, 3, None))

    result = ie.compute_building_group_structure(assignments, "stronghold", 1)
    assert result == {1: 3, 2: 3, 3: 3, 4: 3, 5: 3, 6: 3, 7: 3, 8: 1}
    assert sum(result.values()) == 22


def test_compute_building_group_structure_mana_shrine_level2():
    """
    Mana Shrine level 2 = 7 total slots = 2 full groups + 1 last group with 1 slot.
    """
    assignments = []
    for grp in range(1, 3):
        for pos in range(1, 4):
            assignments.append(ie.ParsedAssignment("mana_shrine", 1, grp, pos, f"M{grp}{pos}"))
    assignments.append(ie.ParsedAssignment("mana_shrine", 1, 3, 1, "Last"))
    assignments.append(ie.ParsedAssignment("mana_shrine", 1, 3, 2, None))
    assignments.append(ie.ParsedAssignment("mana_shrine", 1, 3, 3, None))

    result = ie.compute_building_group_structure(assignments, "mana_shrine", 1)
    assert result == {1: 3, 2: 3, 3: 1}
    assert sum(result.values()) == 7


def test_compute_building_group_structure_mana_shrine_level4():
    """
    Mana Shrine level 4 = 11 total slots = 3 full groups + 1 last group with 2 slots.
    """
    assignments = []
    for grp in range(1, 4):
        for pos in range(1, 4):
            assignments.append(ie.ParsedAssignment("mana_shrine", 1, grp, pos, f"M{grp}{pos}"))
    # Last group: 2 real slots
    assignments.append(ie.ParsedAssignment("mana_shrine", 1, 4, 1, "L1"))
    assignments.append(ie.ParsedAssignment("mana_shrine", 1, 4, 2, "L2"))
    assignments.append(ie.ParsedAssignment("mana_shrine", 1, 4, 3, None))

    result = ie.compute_building_group_structure(assignments, "mana_shrine", 1)
    assert result == {1: 3, 2: 3, 3: 3, 4: 2}
    assert sum(result.values()) == 11


def test_compute_building_group_structure_magic_tower_level3():
    """
    Magic Tower level 3 = 4 total slots = 1 full group (3 slots) + 1 last group with 1 slot.
    """
    assignments = [
        ie.ParsedAssignment("magic_tower", 1, 1, 1, "A"),
        ie.ParsedAssignment("magic_tower", 1, 1, 2, "B"),
        ie.ParsedAssignment("magic_tower", 1, 1, 3, "C"),
        ie.ParsedAssignment("magic_tower", 1, 2, 1, "D"),
        ie.ParsedAssignment("magic_tower", 1, 2, 2, None),
        ie.ParsedAssignment("magic_tower", 1, 2, 3, None),
    ]
    result = ie.compute_building_group_structure(assignments, "magic_tower", 1)
    assert result == {1: 3, 2: 1}
    assert sum(result.values()) == 4


def test_compute_building_group_structure_defense_tower_level4():
    """
    Defense Tower level 4 = 6 total slots = 2 full groups × 3 slots each.
    At level 4 both groups have 3 slots, so the standard non-last=3 rule applies.
    """
    assignments = [
        ie.ParsedAssignment("defense_tower", 1, 1, 1, "A"),
        ie.ParsedAssignment("defense_tower", 1, 1, 2, "B"),
        ie.ParsedAssignment("defense_tower", 1, 1, 3, "C"),
        ie.ParsedAssignment("defense_tower", 1, 2, 1, "D"),
        ie.ParsedAssignment("defense_tower", 1, 2, 2, "E"),
        ie.ParsedAssignment("defense_tower", 1, 2, 3, "F"),
    ]
    result = ie.compute_building_group_structure(assignments, "defense_tower", 1)
    assert result == {1: 3, 2: 3}
    assert sum(result.values()) == 6


# ---------------------------------------------------------------------------
# test_infer_building_level
# ---------------------------------------------------------------------------


def test_infer_building_level_stronghold_level1():
    """12 total positions in a stronghold -> level 1."""
    # 4 groups x 3 slots = 12 positions
    group_structure = {1: 3, 2: 3, 3: 3, 4: 3}
    assert ie.infer_building_level("stronghold", group_structure) == 1


def test_infer_building_level_stronghold_level3():
    """18 total positions in a stronghold -> level 3."""
    # 6 groups x 3 slots = 18 positions
    group_structure = {1: 3, 2: 3, 3: 3, 4: 3, 5: 3, 6: 3}
    assert ie.infer_building_level("stronghold", group_structure) == 3


def test_infer_building_level_stronghold_level6():
    """30 total positions in a stronghold -> level 6."""
    group_structure = {i: 3 for i in range(1, 11)}  # 10 groups x 3 = 30
    assert ie.infer_building_level("stronghold", group_structure) == 6


def test_infer_building_level_mana_shrine_level2():
    """7 total positions in a mana shrine -> level 2."""
    group_structure = {1: 3, 2: 3, 3: 1}  # 7 total
    assert ie.infer_building_level("mana_shrine", group_structure) == 2


def test_infer_building_level_magic_tower_level1():
    """2 total positions in a magic tower -> level 1."""
    group_structure = {1: 2}
    assert ie.infer_building_level("magic_tower", group_structure) == 1


def test_infer_building_level_defense_tower_level4():
    """6 total positions in a defense tower -> level 4."""
    group_structure = {1: 3, 2: 3}  # 6 total
    assert ie.infer_building_level("defense_tower", group_structure) == 4


def test_infer_building_level_post():
    """1 total position in a post -> level 1."""
    group_structure = {1: 1}
    assert ie.infer_building_level("post", group_structure) == 1


def test_infer_building_level_fallback():
    """An unknown total position count falls back to level 1."""
    group_structure = {1: 99}  # 99 positions — not in any level map
    assert ie.infer_building_level("stronghold", group_structure) == 1


def test_infer_building_level_unknown_building_type_fallback():
    """An unknown building type falls back to level 1."""
    group_structure = {1: 3}
    assert ie.infer_building_level("unknown_type", group_structure) == 1


# ---------------------------------------------------------------------------
# test_parse_posts_sheet_config
# ---------------------------------------------------------------------------


def _make_posts_config_worksheet(rows: list[tuple]) -> MagicMock:
    """
    Create a mock worksheet for parse_posts_sheet_config.

    The function calls ws.iter_rows(min_row=..., max_row=..., min_col=..., max_col=...,
    values_only=True), so we use a side_effect to capture those kwargs and return the
    right rows regardless of what keyword arguments are passed.
    """
    ws = MagicMock()
    ws.iter_rows.return_value = iter(rows)
    return ws


def test_parse_posts_sheet_config_basic():
    """One high-priority section with two posts: both get priority=3 and correct descriptions."""
    ws = _make_posts_config_worksheet([
        ("High Priority", None, None),   # priority header row
        (1, "First post desc", None),
        (2, "Second post desc", None),
    ])
    configs = ie.parse_posts_sheet_config(ws)
    assert len(configs) == 2

    assert configs[0].post_number == 1
    assert configs[0].priority == 3
    assert configs[0].description == "First post desc"

    assert configs[1].post_number == 2
    assert configs[1].priority == 3
    assert configs[1].description == "Second post desc"


def test_parse_posts_sheet_config_default_priority():
    """Rows before any priority header default to priority=1 (Low)."""
    ws = _make_posts_config_worksheet([
        (3, "Early post", None),   # no header above — should default to Low=1
        (4, "Another early post", None),
    ])
    configs = ie.parse_posts_sheet_config(ws)
    assert len(configs) == 2
    assert configs[0].priority == 1
    assert configs[1].priority == 1


def test_parse_posts_sheet_config_multiple_sections():
    """Posts fall into the correct priority section based on their position."""
    ws = _make_posts_config_worksheet([
        ("High Priority", None, None),
        (1, "High post", None),
        ("Low Priority", None, None),
        (2, "Low post", None),
    ])
    configs = ie.parse_posts_sheet_config(ws)
    assert len(configs) == 2

    # Post 1 is under the High section
    assert configs[0].post_number == 1
    assert configs[0].priority == 3

    # Post 2 is under the Low section
    assert configs[1].post_number == 2
    assert configs[1].priority == 1


# ---------------------------------------------------------------------------
# test_parse_posts_sheet_conditions
# ---------------------------------------------------------------------------


def _make_posts_conditions_worksheet(rows: list[tuple]) -> MagicMock:
    """
    Create a mock worksheet for parse_posts_sheet_conditions.

    The function enumerates ws.iter_rows(..., values_only=True) starting at row_index=34,
    so we return the rows directly.
    """
    ws = MagicMock()
    ws.iter_rows.return_value = iter(rows)
    return ws


def test_parse_posts_sheet_conditions_basic():
    """Three post rows with 1–3 keywords each are parsed correctly."""
    ws = _make_posts_conditions_worksheet([
        ("hp", None, None),              # post 1: 1 keyword
        ("def", "atk", None),            # post 2: 2 keywords
        ("void", "force", "magic"),      # post 3: 3 keywords
    ])
    results = ie.parse_posts_sheet_conditions(ws)
    assert len(results) == 3

    assert results[0].post_number == 1
    assert results[0].condition_keywords == ["hp"]

    assert results[1].post_number == 2
    assert results[1].condition_keywords == ["def", "atk"]

    assert results[2].post_number == 3
    assert results[2].condition_keywords == ["void", "force", "magic"]


def test_parse_posts_sheet_conditions_skips_empty():
    """A row with all-None cells is not included in the result."""
    ws = _make_posts_conditions_worksheet([
        ("hp", None, None),    # post 1: included
        (None, None, None),    # post 2: all None — should be skipped
        ("def", None, None),   # post 3: included
    ])
    results = ie.parse_posts_sheet_conditions(ws)
    # Only the two non-empty rows should be present
    assert len(results) == 2
    assert results[0].post_number == 1
    assert results[1].post_number == 3
