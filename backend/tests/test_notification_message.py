"""Unit tests for build_member_notification_message in notification_message.py."""

from app.models.enums import BuildingType
from app.services.notification_message import PositionInfo, build_member_notification_message

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SINGLE_STRONGHOLD_COUNTS: dict[BuildingType, int] = {
    BuildingType.stronghold: 1,
    BuildingType.defense_tower: 3,
    BuildingType.post: 18,
}

MULTI_DEFENSE_TOWER_COUNTS: dict[BuildingType, int] = {
    BuildingType.stronghold: 1,
    BuildingType.defense_tower: 5,
    BuildingType.post: 18,
}


def _stronghold_pos(group: int = 6, pos: int = 1) -> PositionInfo:
    return PositionInfo(
        building_type=BuildingType.stronghold,
        building_number=1,
        group_number=group,
        position_number=pos,
    )


def _defense_tower_pos(number: int = 5, group: int = 1, pos: int = 3) -> PositionInfo:
    return PositionInfo(
        building_type=BuildingType.defense_tower,
        building_number=number,
        group_number=group,
        position_number=pos,
    )


def _post_pos(number: int = 2) -> PositionInfo:
    return PositionInfo(
        building_type=BuildingType.post,
        building_number=number,
        group_number=1,
        position_number=1,
    )


# ---------------------------------------------------------------------------
# 1. No previous siege — all current positions appear in "Set At"
# ---------------------------------------------------------------------------


def test_no_previous_siege_all_current_in_set_at():
    """When previous_positions is empty every current position goes to Set At."""
    current = [_stronghold_pos(), _post_pos(2)]
    msg = build_member_notification_message(
        siege_date="2026-03-17",
        has_reserve_set=True,
        attack_day=2,
        current_positions=current,
        previous_positions=[],
        building_type_counts=SINGLE_STRONGHOLD_COUNTS,
    )
    assert ":crossed_swords:  Set At  :crossed_swords:" in msg
    assert ":crossed_swords:  No Change  :crossed_swords:" not in msg
    assert ":crossed_swords:  Remove From  :crossed_swords:" not in msg


# ---------------------------------------------------------------------------
# 2. Empty sections are omitted — no diff → only No Change
# ---------------------------------------------------------------------------


def test_empty_sections_omitted_all_no_change():
    """When current and previous are identical only No Change appears."""
    pos = [_stronghold_pos(), _post_pos(8)]
    msg = build_member_notification_message(
        siege_date="2026-03-17",
        has_reserve_set=False,
        attack_day=1,
        current_positions=pos,
        previous_positions=pos,
        building_type_counts=SINGLE_STRONGHOLD_COUNTS,
    )
    assert ":crossed_swords:  No Change  :crossed_swords:" in msg
    assert ":crossed_swords:  Remove From  :crossed_swords:" not in msg
    assert ":crossed_swords:  Set At  :crossed_swords:" not in msg


# ---------------------------------------------------------------------------
# 3. Full diff — positions spread across all three sections
# ---------------------------------------------------------------------------


def test_full_diff_three_sections():
    """Positions only in current → Set At, only in previous → Remove From, both → No Change."""
    shared = _stronghold_pos(group=6, pos=1)
    only_current = _post_pos(2)
    only_previous = _post_pos(18)

    msg = build_member_notification_message(
        siege_date="2026-03-17",
        has_reserve_set=True,
        attack_day=2,
        current_positions=[shared, only_current],
        previous_positions=[shared, only_previous],
        building_type_counts=SINGLE_STRONGHOLD_COUNTS,
    )
    assert ":crossed_swords:  No Change  :crossed_swords:" in msg
    assert ":crossed_swords:  Remove From  :crossed_swords:" in msg
    assert ":crossed_swords:  Set At  :crossed_swords:" in msg

    # Correct positions end up in the right sections
    no_change_idx = msg.index("No Change")
    remove_from_idx = msg.index("Remove From")
    set_at_idx = msg.index("Set At")

    # Stronghold (shared) appears in No Change
    stronghold_label = ":red_circle: Stronghold / Group 6 / Pos 1"
    assert stronghold_label in msg
    assert msg.index(stronghold_label) > no_change_idx

    # Post 18 (only previous) appears after Remove From header
    post18_label = ":white_circle: Post 18"
    assert post18_label in msg
    assert msg.index(post18_label) > remove_from_idx

    # Post 2 (only current) appears after Set At header
    post2_label = ":white_circle: Post 2"
    assert post2_label in msg
    assert msg.index(post2_label) > set_at_idx


# ---------------------------------------------------------------------------
# 4. Header content — siege date, reserve set, attack day
# ---------------------------------------------------------------------------


def test_header_contains_siege_date_and_member_settings():
    """The message header must include the date, reserve status and attack day."""
    msg = build_member_notification_message(
        siege_date="2026-03-17",
        has_reserve_set=True,
        attack_day=2,
        current_positions=[],
        previous_positions=[],
        building_type_counts={},
    )
    assert "[1MOM] Masters of Magicka Siege Assignment (2026-03-17)" in msg
    assert "Have Reserve Set: Yes" in msg
    assert "Attack Day: 2" in msg


# ---------------------------------------------------------------------------
# 5. None values for has_reserve_set and attack_day → "Unknown"
# ---------------------------------------------------------------------------


def test_none_fields_display_as_unknown():
    """None for has_reserve_set or attack_day should render as 'Unknown'."""
    msg = build_member_notification_message(
        siege_date="2026-03-17",
        has_reserve_set=None,
        attack_day=None,
        current_positions=[],
        previous_positions=[],
        building_type_counts={},
    )
    assert "Have Reserve Set: Unknown" in msg
    assert "Attack Day: Unknown" in msg


def test_false_reserve_set_displays_no():
    """has_reserve_set=False should render as 'No', not 'Unknown'."""
    msg = build_member_notification_message(
        siege_date="2026-03-17",
        has_reserve_set=False,
        attack_day=1,
        current_positions=[],
        previous_positions=[],
        building_type_counts={},
    )
    assert "Have Reserve Set: No" in msg


# ---------------------------------------------------------------------------
# 6. Single building type — Stronghold label omits building number
# ---------------------------------------------------------------------------


def test_single_building_type_omits_building_number():
    """When count == 1 the building number is omitted from the label."""
    current = [_stronghold_pos(group=6, pos=1)]
    msg = build_member_notification_message(
        siege_date="2026-03-17",
        has_reserve_set=True,
        attack_day=2,
        current_positions=current,
        previous_positions=[],
        building_type_counts={BuildingType.stronghold: 1},
    )
    # No building number in label
    assert ":red_circle: Stronghold / Group 6 / Pos 1" in msg
    assert ":red_circle: Stronghold 1 / Group" not in msg


# ---------------------------------------------------------------------------
# 7. Multiple of same type — Defense Tower label includes building number
# ---------------------------------------------------------------------------


def test_multiple_building_type_includes_building_number():
    """When count > 1 the building number is included in the label."""
    current = [_defense_tower_pos(number=5, group=1, pos=3)]
    msg = build_member_notification_message(
        siege_date="2026-03-17",
        has_reserve_set=True,
        attack_day=2,
        current_positions=current,
        previous_positions=[],
        building_type_counts=MULTI_DEFENSE_TOWER_COUNTS,
    )
    assert ":green_circle: Defense Tower 5 / Group 1 / Pos 3" in msg


# ---------------------------------------------------------------------------
# 8. Post format — always uses short "Post {N}" format
# ---------------------------------------------------------------------------


def test_post_always_uses_short_format():
    """Posts always render as ':white_circle: Post {N}' regardless of count."""
    current = [_post_pos(8)]
    # Even with many posts, short format must be used
    msg = build_member_notification_message(
        siege_date="2026-03-17",
        has_reserve_set=True,
        attack_day=1,
        current_positions=current,
        previous_positions=[],
        building_type_counts={BuildingType.post: 18},
    )
    assert ":white_circle: Post 8" in msg
    assert "Group" not in msg.split(":white_circle:")[1]


def test_post_with_single_count_still_uses_short_format():
    """Posts with count == 1 still use short format (not the number-omitting path)."""
    current = [_post_pos(1)]
    msg = build_member_notification_message(
        siege_date="2026-03-17",
        has_reserve_set=True,
        attack_day=1,
        current_positions=current,
        previous_positions=[],
        building_type_counts={BuildingType.post: 1},
    )
    assert ":white_circle: Post 1" in msg


# ---------------------------------------------------------------------------
# 9. Section order — No Change → Remove From → Set At
# ---------------------------------------------------------------------------


def test_section_order_no_change_then_remove_then_set_at():
    """Sections must appear in the order: No Change, Remove From, Set At."""
    shared = _stronghold_pos(group=1, pos=1)
    only_prev = _defense_tower_pos(number=1, group=1, pos=1)
    only_curr = _post_pos(5)

    msg = build_member_notification_message(
        siege_date="2026-03-17",
        has_reserve_set=True,
        attack_day=2,
        current_positions=[shared, only_curr],
        previous_positions=[shared, only_prev],
        building_type_counts=MULTI_DEFENSE_TOWER_COUNTS,
    )

    no_change_idx = msg.index("No Change")
    remove_from_idx = msg.index("Remove From")
    set_at_idx = msg.index("Set At")

    assert no_change_idx < remove_from_idx < set_at_idx


# ---------------------------------------------------------------------------
# 10. Positions within a section are sorted by building type then number etc.
# ---------------------------------------------------------------------------


def test_positions_sorted_within_section():
    """Within Set At, positions should be sorted by type order then building/group/pos."""
    # Post comes after Stronghold in canonical order
    sh = _stronghold_pos(group=2, pos=1)
    post = _post_pos(3)

    msg = build_member_notification_message(
        siege_date="2026-03-17",
        has_reserve_set=True,
        attack_day=1,
        current_positions=[post, sh],  # deliberately reversed
        previous_positions=[],
        building_type_counts=SINGLE_STRONGHOLD_COUNTS,
    )

    stronghold_idx = msg.index(":red_circle: Stronghold")
    post_idx = msg.index(":white_circle: Post")
    assert stronghold_idx < post_idx
