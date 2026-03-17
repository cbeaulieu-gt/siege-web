"""Tests for the image generation service."""

from types import SimpleNamespace
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
    }


def _make_member(
    name: str = "Alice",
    role: MemberRole = MemberRole.advanced,
    attack_day: int | None = 1,
    has_reserve_set: bool | None = True,
) -> SiegeMemberWithName:
    return SiegeMemberWithName(
        name=name, role=role, attack_day=attack_day, has_reserve_set=has_reserve_set
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
    assert "#7c3aed" in html  # stronghold
    assert "#2563eb" in html  # mana_shrine
    assert "#d97706" in html  # magic_tower
    assert "#16a34a" in html  # defense_tower
    assert "#dc2626" in html  # post


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
    assert "ADV" in html


def test_build_reserves_html_day1_color():
    members = [_make_member(attack_day=1)]
    html = _build_reserves_html(members, "2026-03-20")
    assert "#60a5fa" in html  # blue for day 1


def test_build_reserves_html_day2_color():
    members = [_make_member(attack_day=2)]
    html = _build_reserves_html(members, "2026-03-20")
    assert "#fb923c" in html  # orange for day 2


def test_build_reserves_html_role_abbreviations():
    from app.models.enums import MemberRole

    members = [
        _make_member(name="HH", role=MemberRole.heavy_hitter),
        _make_member(name="ADV", role=MemberRole.advanced),
        _make_member(name="MED", role=MemberRole.medium),
        _make_member(name="NOV", role=MemberRole.novice),
    ]
    html = _build_reserves_html(members, "2026-03-20")
    assert "HH" in html
    assert "ADV" in html
    assert "MED" in html
    assert "NOV" in html


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
