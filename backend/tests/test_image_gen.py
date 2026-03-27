"""Tests for the image generation service."""

from unittest.mock import AsyncMock, patch

import pytest

from app.models.enums import BuildingType, MemberRole
from app.schemas.board import BoardResponse
from app.services.image_gen import (
    SiegeMemberWithName,
    _build_assignments_html,
    _build_reserves_html,
    generate_assignments_image,
    generate_reserves_image,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_board(buildings=None) -> BoardResponse:
    return BoardResponse(siege_id=1, buildings=buildings or [])


def _make_building_dict(
    building_type: str = "stronghold",
    building_number: int = 1,
    level: int = 3,
    is_broken: bool = False,
    groups=None,
) -> dict:
    return {
        "id": 1,
        "building_type": building_type,
        "building_number": building_number,
        "level": level,
        "is_broken": is_broken,
        "groups": groups or [],
    }


def _make_group_dict(group_number: int = 1, positions=None) -> dict:
    return {
        "id": 1,
        "group_number": group_number,
        "slot_count": 3,
        "positions": positions or [],
    }


def _make_position_dict(
    position_number: int = 1,
    member_name: str | None = "Alice",
    is_reserve: bool = False,
    is_disabled: bool = False,
) -> dict:
    return {
        "id": 1,
        "position_number": position_number,
        "member_id": 1 if member_name else None,
        "member_name": member_name,
        "is_reserve": is_reserve,
        "is_disabled": is_disabled,
        "matched_condition_id": None,
    }


def _make_member(
    name: str = "Alice",
    role: MemberRole = MemberRole.advanced,
    attack_day: int | None = 1,
    has_reserve_set: bool | None = True,
) -> SiegeMemberWithName:
    return SiegeMemberWithName(
        name=name,
        role=role,
        attack_day=attack_day,
        has_reserve_set=has_reserve_set,
    )


# ---------------------------------------------------------------------------
# _build_assignments_html
# ---------------------------------------------------------------------------


def test_build_assignments_html_contains_title():
    board = _make_board()
    html = _build_assignments_html(board, "2026-03-20")
    assert "2026-03-20" in html
    assert "Siege Assignments" in html


def test_build_assignments_html_contains_building_type():
    position = _make_position_dict(member_name="Alice")
    group = _make_group_dict(positions=[position])
    building = _make_building_dict(building_type="stronghold", groups=[group])
    board = BoardResponse.model_validate({"siege_id": 1, "buildings": [building]})
    html = _build_assignments_html(board, "2026-03-20")
    assert "Stronghold" in html
    assert "Alice" in html


def test_build_assignments_html_reserve_cell():
    position = _make_position_dict(member_name=None, is_reserve=True)
    group = _make_group_dict(positions=[position])
    building = _make_building_dict(groups=[group])
    board = BoardResponse.model_validate({"siege_id": 1, "buildings": [building]})
    html = _build_assignments_html(board, "2026-03-20")
    assert "RESERVE" in html


def test_build_assignments_html_disabled_cell():
    position = _make_position_dict(member_name=None, is_disabled=True)
    group = _make_group_dict(positions=[position])
    building = _make_building_dict(groups=[group])
    board = BoardResponse.model_validate({"siege_id": 1, "buildings": [building]})
    html = _build_assignments_html(board, "2026-03-20")
    assert "N/A" in html


def test_build_assignments_html_empty_board():
    board = _make_board()
    html = _build_assignments_html(board, "2026-03-20")
    assert len(html) > 0
    assert "Siege Assignments" in html


def test_build_assignments_html_all_building_types_colored():
    buildings = [
        _make_building_dict(building_type=bt.value, building_number=i + 1)
        for i, bt in enumerate(BuildingType)
    ]
    board = BoardResponse.model_validate({"siege_id": 1, "buildings": buildings})
    html = _build_assignments_html(board, "2026-03-20")
    # All color codes should appear
    assert "#dc2626" in html  # stronghold
    assert "#d97706" in html  # mana_shrine
    assert "#2563eb" in html  # magic_tower
    assert "#16a34a" in html  # defense_tower
    assert "#64748b" in html  # post


# ---------------------------------------------------------------------------
# _build_reserves_html
# ---------------------------------------------------------------------------


def test_build_reserves_html_contains_title():
    html = _build_reserves_html([], "2026-03-20")
    assert "2026-03-20" in html
    assert "Siege Members" in html


def test_build_reserves_html_contains_member():
    members = [_make_member(name="Bob", attack_day=1)]
    html = _build_reserves_html(members, "2026-03-20")
    assert "Bob" in html


def test_build_reserves_html_day1_color():
    members = [_make_member(attack_day=1)]
    html = _build_reserves_html(members, "2026-03-20")
    assert "#60a5fa" in html  # blue for day 1


def test_build_reserves_html_day2_color():
    members = [_make_member(attack_day=2)]
    html = _build_reserves_html(members, "2026-03-20")
    assert "#fb923c" in html  # orange for day 2


def test_build_reserves_html_no_role_column():
    """Role column must not appear in the rendered HTML."""
    members = [
        _make_member(name="Alice", role=MemberRole.heavy_hitter),
        _make_member(name="Bob", role=MemberRole.advanced),
    ]
    html = _build_reserves_html(members, "2026-03-20")
    assert "Role" not in html
    assert "HH" not in html
    assert "ADV" not in html
    assert "MED" not in html
    assert "NOV" not in html


# ---------------------------------------------------------------------------
# generate_assignments_image / generate_reserves_image (patched render)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_assignments_image_calls_render():
    board = _make_board()
    with patch(
        "app.services.image_gen._render_html_to_png",
        new_callable=AsyncMock,
        return_value=b"fake-png",
    ) as mock_render:
        result = await generate_assignments_image(board, "2026-03-20")

    assert result == b"fake-png"
    mock_render.assert_awaited_once()
    # Verify the HTML passed to render contains expected content
    called_html = mock_render.call_args[0][0]
    assert "Siege Assignments" in called_html


@pytest.mark.asyncio
async def test_generate_reserves_image_calls_render():
    members = [_make_member()]
    with patch(
        "app.services.image_gen._render_html_to_png",
        new_callable=AsyncMock,
        return_value=b"fake-png",
    ) as mock_render:
        result = await generate_reserves_image(members, "2026-03-20")

    assert result == b"fake-png"
    mock_render.assert_awaited_once()
    called_html = mock_render.call_args[0][0]
    assert "Siege Members" in called_html


# ---------------------------------------------------------------------------
# Group header rows
# ---------------------------------------------------------------------------


def test_build_assignments_html_group_header_present():
    """Each group must have a 'Group N' label in the HTML."""
    group1 = _make_group_dict(group_number=1, positions=[_make_position_dict(member_name="Alice")])
    group2 = _make_group_dict(group_number=2, positions=[_make_position_dict(member_name="Bob")])
    building = _make_building_dict(building_type="stronghold", groups=[group1, group2])
    board = BoardResponse.model_validate({"siege_id": 1, "buildings": [building]})
    html = _build_assignments_html(board, "2026-03-20")
    assert "Group 1" in html
    assert "Group 2" in html


def test_build_assignments_html_group_header_before_members():
    """Group 1 header must appear before Group 2 header in document order."""
    group1 = _make_group_dict(group_number=1, positions=[_make_position_dict(member_name="Alice")])
    group2 = _make_group_dict(group_number=2, positions=[_make_position_dict(member_name="Bob")])
    building = _make_building_dict(building_type="stronghold", groups=[group1, group2])
    board = BoardResponse.model_validate({"siege_id": 1, "buildings": [building]})
    html = _build_assignments_html(board, "2026-03-20")
    assert html.index("Group 1") < html.index("Alice")
    assert html.index("Group 1") < html.index("Group 2")
    assert html.index("Group 2") < html.index("Bob")


def test_build_assignments_html_single_row_per_group():
    """Group label and slot cells must appear in the same <tr>, not separate rows.

    The old layout emitted two <tr> elements per group: one colspan header row
    followed by one slot row.  The new layout collapses them into a single <tr>
    whose first <td> is the group label.
    """
    position = _make_position_dict(member_name="Alice")
    group = _make_group_dict(group_number=1, positions=[position])
    building = _make_building_dict(building_type="stronghold", groups=[group])
    board = BoardResponse.model_validate({"siege_id": 1, "buildings": [building]})
    html = _build_assignments_html(board, "2026-03-20")

    # "Group 1" label and "Alice" must sit inside the same <tr>...</tr> block.
    # Find the <tr> that contains "Group 1" and assert "Alice" is also in it.
    import re

    rows = re.findall(r"<tr>(.*?)</tr>", html, re.DOTALL)
    group1_rows = [r for r in rows if "Group 1" in r]
    assert len(group1_rows) == 1, "Expected exactly one <tr> containing 'Group 1'"
    assert "Alice" in group1_rows[0], "Slot cell must be in the same <tr> as the group label"

    # Ensure there is no colspan spanning header row separate from slot cells.
    # The old pattern was colspan="20" on a standalone header row.
    assert 'colspan="20"' not in html, "No standalone colspan header row should exist"


def test_build_assignments_html_buildings_side_by_side():
    """Two buildings of the same type must both render and the section must use flex layout.

    Buildings of the same type are placed side by side via display:flex on the
    section wrapper, so both building headers should appear and the wrapper must
    carry the flex + gap styles.
    """
    group_a = _make_group_dict(group_number=1, positions=[_make_position_dict(member_name="Alice")])
    group_b = _make_group_dict(group_number=1, positions=[_make_position_dict(member_name="Bob")])
    building1 = _make_building_dict(
        building_type="stronghold", building_number=1, level=3, groups=[group_a]
    )
    building2 = _make_building_dict(
        building_type="stronghold", building_number=2, level=2, groups=[group_b]
    )
    board = BoardResponse.model_validate({"siege_id": 1, "buildings": [building1, building2]})
    html = _build_assignments_html(board, "2026-03-20")

    # Both building headers must be present (level is no longer shown)
    assert "#1" in html
    assert "#2" in html
    assert "Lv" not in html

    # The section wrapper must carry flex + gap layout so buildings sit side by side
    assert "display:flex" in html
    assert "flex-wrap:wrap" in html
    assert "gap:16px" in html


# ---------------------------------------------------------------------------
# Role color tests — _build_assignments_html
# ---------------------------------------------------------------------------


def test_build_assignments_html_heavy_hitter_color():
    """A member mapped to heavy_hitter role gets the amber color #f59e0b."""
    position = _make_position_dict(member_name="Alice")  # member_id=1 by default
    group = _make_group_dict(positions=[position])
    building = _make_building_dict(building_type="stronghold", groups=[group])
    board = BoardResponse.model_validate({"siege_id": 1, "buildings": [building]})
    html = _build_assignments_html(
        board, "2026-03-20", member_id_to_role={1: MemberRole.heavy_hitter}
    )
    assert "#f59e0b" in html
    assert "Alice" in html


def test_build_assignments_html_no_role_map_fallback():
    """When member_id_to_role is empty the fallback white color is used."""
    position = _make_position_dict(member_name="Alice")
    group = _make_group_dict(positions=[position])
    building = _make_building_dict(building_type="stronghold", groups=[group])
    board = BoardResponse.model_validate({"siege_id": 1, "buildings": [building]})
    html = _build_assignments_html(board, "2026-03-20", member_id_to_role={})
    assert "Alice" in html
    assert "#f9fafb" in html


def test_build_assignments_html_role_color_on_span_not_background():
    """The role color appears on the name <span>, not the cell background."""
    position = _make_position_dict(member_name="Alice")
    group = _make_group_dict(positions=[position])
    building = _make_building_dict(building_type="stronghold", groups=[group])
    board = BoardResponse.model_validate({"siege_id": 1, "buildings": [building]})
    html = _build_assignments_html(board, "2026-03-20", member_id_to_role={1: MemberRole.advanced})
    assert '<span style="color:#a855f7">' in html
    assert "background:#1f2937" in html


# ---------------------------------------------------------------------------
# Role color tests — _build_reserves_html
# ---------------------------------------------------------------------------


def test_build_reserves_html_advanced_color():
    """A member with advanced role gets the purple color #a855f7."""
    members = [_make_member(name="Bob", role=MemberRole.advanced)]
    html = _build_reserves_html(members, "2026-03-20")
    assert "#a855f7" in html
    assert "Bob" in html


def test_build_reserves_html_novice_color():
    """A member with novice role gets the slate color #94a3b8."""
    members = [_make_member(name="Carol", role=MemberRole.novice)]
    html = _build_reserves_html(members, "2026-03-20")
    assert "#94a3b8" in html
    assert "Carol" in html


def test_build_reserves_html_fallback_color():
    """A member whose role is not in _MEMBER_ROLE_COLORS falls back to #f9fafb."""
    # Pass a raw SiegeMemberWithName with a role value that won't be in the map.
    # We patch the member's role attribute to a sentinel not present in the dict.
    member = _make_member(name="Ghost", role=MemberRole.medium)
    # Temporarily override role to an unknown value by constructing directly
    from app.services.image_gen import _MEMBER_ROLE_COLORS

    # Use a role that IS in the map to verify fallback only happens for missing keys.
    # To test true fallback we remove it temporarily.
    original = _MEMBER_ROLE_COLORS.pop(MemberRole.medium, None)
    try:
        html = _build_reserves_html([member], "2026-03-20")
        assert "Ghost" in html
        assert "#f9fafb" in html
    finally:
        if original is not None:
            _MEMBER_ROLE_COLORS[MemberRole.medium] = original


# ---------------------------------------------------------------------------
# Image layout improvements — level removal, thead header, flat post table
# ---------------------------------------------------------------------------


def test_build_assignments_html_no_level_in_header():
    """Building header must not contain the level."""
    group = _make_group_dict(positions=[_make_position_dict(member_name="Alice")])
    building = _make_building_dict(building_type="stronghold", building_number=1, level=5, groups=[group])
    board = BoardResponse.model_validate({"siege_id": 1, "buildings": [building]})
    html = _build_assignments_html(board, "2026-03-20")
    assert "#1" in html
    assert "Lv" not in html
    assert "Lv 5" not in html


def test_build_assignments_html_broken_building_no_level():
    """Broken building header shows [broken] but no level."""
    group = _make_group_dict(positions=[_make_position_dict(member_name="Alice")])
    building = _make_building_dict(building_type="stronghold", building_number=2, level=3, is_broken=True, groups=[group])
    board = BoardResponse.model_validate({"siege_id": 1, "buildings": [building]})
    html = _build_assignments_html(board, "2026-03-20")
    assert "[broken]" in html
    assert "Lv" not in html


def test_build_assignments_html_building_number_in_thead():
    """Building number must appear in a <thead> spanning row, not a standalone <div>."""
    group = _make_group_dict(positions=[_make_position_dict(member_name="Alice")])
    building = _make_building_dict(building_type="stronghold", building_number=3, groups=[group])
    board = BoardResponse.model_validate({"siege_id": 1, "buildings": [building]})
    html = _build_assignments_html(board, "2026-03-20")
    # #3 must appear inside a <thead> block
    assert "<thead>" in html
    thead_start = html.index("<thead>")
    thead_end = html.index("</thead>")
    thead_content = html[thead_start:thead_end]
    assert "#3" in thead_content


def test_build_assignments_html_post_flat_table():
    """Post buildings render as a single flat table, not per-building group tables."""
    post1 = _make_building_dict(building_type="post", building_number=2,
        groups=[_make_group_dict(group_number=1, positions=[_make_position_dict(position_number=1, member_name="Alice")])])
    post2 = _make_building_dict(building_type="post", building_number=8,
        groups=[_make_group_dict(group_number=1, positions=[_make_position_dict(position_number=1, member_name="Bob")])])
    board = BoardResponse.model_validate({"siege_id": 1, "buildings": [post1, post2]})
    html = _build_assignments_html(board, "2026-03-20")
    # Both post headers appear as column headers
    assert "Post 2" in html
    assert "Post 8" in html
    # Member names appear
    assert "Alice" in html
    assert "Bob" in html
    # Posts come in sorted order
    assert html.index("Post 2") < html.index("Post 8")


def test_build_assignments_html_post_reserve_and_disabled():
    """Post flat table correctly renders reserve and disabled slots."""
    post_reserve = _make_building_dict(building_type="post", building_number=11,
        groups=[_make_group_dict(positions=[_make_position_dict(member_name=None, is_reserve=True)])])
    post_disabled = _make_building_dict(building_type="post", building_number=14,
        groups=[_make_group_dict(positions=[_make_position_dict(member_name=None, is_disabled=True)])])
    board = BoardResponse.model_validate({"siege_id": 1, "buildings": [post_reserve, post_disabled]})
    html = _build_assignments_html(board, "2026-03-20")
    assert "RESERVE" in html
    assert "N/A" in html
