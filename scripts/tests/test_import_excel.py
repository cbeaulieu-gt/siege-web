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
    """Extracts a valid date from a canonical filename."""
    result = ie.parse_filename_date("clan_siege_15_03_2026.xlsm")
    assert result == date(2026, 3, 15)


def test_parse_filename_with_path_prefix():
    """Extracts date even when the filename has a path prefix passed as string."""
    result = ie.parse_filename_date("/some/path/clan_siege_01_12_2025.xlsm")
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
    assert ie.map_building_alias("Stronghold") == "stronghold"


def test_building_alias_mana_shrine_full():
    assert ie.map_building_alias("Mana Shrine") == "mana_shrine"


def test_building_alias_mana_short():
    assert ie.map_building_alias("Mana") == "mana_shrine"


def test_building_alias_magic_tower_full():
    assert ie.map_building_alias("Magic Tower") == "magic_tower"


def test_building_alias_magic_short():
    assert ie.map_building_alias("Magic") == "magic_tower"


def test_building_alias_defense_tower_full():
    assert ie.map_building_alias("Defense Tower") == "defense_tower"


def test_building_alias_defense_short():
    assert ie.map_building_alias("Defense") == "defense_tower"


def test_building_alias_post():
    assert ie.map_building_alias("Post") == "post"


def test_building_alias_unknown_returns_none():
    assert ie.map_building_alias("Barracks") is None


# ---------------------------------------------------------------------------
# test_parse_members_sheet
# ---------------------------------------------------------------------------


def _make_worksheet(rows: list[tuple]) -> MagicMock:
    """Create a mock openpyxl worksheet that yields the given rows."""
    ws = MagicMock()
    ws.iter_rows.return_value = iter(rows)
    return ws


def test_parse_members_sheet_basic():
    ws = _make_worksheet(
        [
            # (name, role, power, discord_username)
            ("Alice", "Heavy Hitter", 5_000_000, "alice#1234"),
            ("Bob", "Advanced", 3_500_000, None),
            ("Charlie", "Novice", None, "charlie"),
        ]
    )
    members = ie.parse_members_sheet(ws)
    assert len(members) == 3

    assert members[0].name == "Alice"
    assert members[0].role == "Heavy Hitter"
    assert members[0].power == 5_000_000.0
    assert members[0].discord_username == "alice#1234"

    assert members[1].name == "Bob"
    assert members[1].discord_username is None

    assert members[2].name == "Charlie"
    assert members[2].power is None


def test_parse_members_sheet_skips_empty_rows():
    ws = _make_worksheet(
        [
            ("Alice", "Medium", 2_000_000, None),
            (None, None, None, None),   # empty row — should be skipped
            ("", "Novice", None, None),  # blank name — should be skipped
        ]
    )
    members = ie.parse_members_sheet(ws)
    assert len(members) == 1
    assert members[0].name == "Alice"


def test_parse_members_sheet_strips_whitespace():
    ws = _make_worksheet([("  Dave  ", "  Advanced  ", 1_000_000, "  dave  ")])
    members = ie.parse_members_sheet(ws)
    assert members[0].name == "Dave"
    assert members[0].discord_username == "dave"


# ---------------------------------------------------------------------------
# test_parse_assignments_sheet
# ---------------------------------------------------------------------------


def test_parse_assignments_sheet_member_assignment():
    ws = _make_worksheet(
        [
            # (building_type, building_number, group_number, position_number, value)
            ("Mana Shrine", 1, 1, 1, "Alice"),
            ("Mana Shrine", 1, 1, 2, "Bob"),
            ("Post", 3, 1, 1, "RESERVE"),
            ("Magic Tower", 2, 1, 1, None),
        ]
    )
    assignments = ie.parse_assignments_sheet(ws)
    assert len(assignments) == 4

    assert assignments[0].building_type == "mana_shrine"
    assert assignments[0].building_number == 1
    assert assignments[0].group_number == 1
    assert assignments[0].position_number == 1
    assert assignments[0].value == "Alice"

    assert assignments[2].building_type == "post"
    assert assignments[2].value == "RESERVE"

    assert assignments[3].value is None


def test_parse_assignments_sheet_skips_unknown_building_type():
    ws = _make_worksheet(
        [
            ("Unknown", 1, 1, 1, "Alice"),
            ("Stronghold", 1, 1, 1, "Bob"),
        ]
    )
    assignments = ie.parse_assignments_sheet(ws)
    # Only the valid row should be returned
    assert len(assignments) == 1
    assert assignments[0].building_type == "stronghold"


def test_parse_assignments_sheet_skips_incomplete_rows():
    ws = _make_worksheet(
        [
            ("Post", None, 1, 1, "Alice"),  # missing building_number
            ("Defense", 1, None, 1, "Bob"),  # missing group_number
        ]
    )
    assignments = ie.parse_assignments_sheet(ws)
    assert len(assignments) == 0


def test_parse_assignments_sheet_empty_value_is_none():
    ws = _make_worksheet([("Post", 1, 1, 1, "  ")])  # whitespace-only value
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
