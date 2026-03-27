"""Service-layer tests for update_building — focus on unbreak restoration."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import BuildingType, SiegeStatus
from app.schemas.building import BuildingUpdate
from app.services.buildings import update_building, _get_team_count

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_siege(status=SiegeStatus.planning):
    return SimpleNamespace(id=1, status=status)


def _make_building(
    id=1,
    building_type=BuildingType.stronghold,
    level=6,
    is_broken=False,
):
    b = SimpleNamespace(
        id=id,
        siege_id=1,
        building_type=building_type,
        level=level,
        is_broken=is_broken,
    )
    return b


def _make_group(id, group_number, slot_count, building_id=1):
    return SimpleNamespace(
        id=id,
        building_id=building_id,
        group_number=group_number,
        slot_count=slot_count,
    )


def _make_config(building_type, base_group_count, base_last_group_slots):
    return SimpleNamespace(
        building_type=building_type,
        base_group_count=base_group_count,
        base_last_group_slots=base_last_group_slots,
    )


def _scalars_all(items):
    """Return a MagicMock shaped like scalars().all() → items."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    return result


def _scalars_first(item):
    """Return a MagicMock shaped like scalars().first() → item."""
    result = MagicMock()
    result.scalars.return_value.first.return_value = item
    return result


def _scalar_one_or_none(item):
    """Return a MagicMock shaped like scalar_one_or_none() → item."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = item
    return result


# ---------------------------------------------------------------------------
# Stronghold level 6: 30 teams → 10 groups × 3 slots each
# Stronghold base config: 4 groups, last group 2 slots
#
# After breaking: 4 groups (last has 2 slots)
# After unbreaking: should restore to 10 groups × 3 slots
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_building_unbreak_restores_groups():
    """
    A Stronghold at level 6 (10 groups × 3 slots) was broken down to the base
    config (4 groups, last=2 slots).  Setting is_broken=False must rebuild it
    to 10 groups with the last group having 3 slots.
    """
    siege = _make_siege()
    # Building is currently broken; still at level 6
    building = _make_building(id=1, building_type=BuildingType.stronghold, level=6, is_broken=True)

    # Base config for stronghold: 4 groups, last group has 2 slots
    # When broken the building has exactly those 4 groups
    base_groups = [
        _make_group(id=g, group_number=g, slot_count=(2 if g == 4 else 3)) for g in range(1, 5)
    ]

    # After _rebuild_groups_for_level adds groups 5–10, the actual last group
    # will be group 10 with slot_count=3 (which already matches last_slots=3
    # so no further adjustment is needed for this case).
    # We simulate the second execute (desc order) returning a fresh group 10.
    new_last_group = _make_group(id=10, group_number=10, slot_count=3)

    call_count = 0

    async def fake_execute(stmt):
        nonlocal call_count
        call_count += 1
        # 1: get_siege
        if call_count == 1:
            return _scalar_one_or_none(siege)
        # 2: _get_building
        if call_count == 2:
            return _scalar_one_or_none(building)
        # 3: _rebuild_groups_for_level — current groups (asc order)
        if call_count == 3:
            return _scalars_all(base_groups)
        # 4: _rebuild_groups_for_level — last group after flush (desc order)
        if call_count == 4:
            return _scalars_first(new_last_group)
        # Fallback (shouldn't reach here in this path)
        return _scalar_one_or_none(None)

    session = AsyncMock()
    session.execute = fake_execute
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.delete = AsyncMock()

    added_objects = []
    session.add = lambda obj: added_objects.append(obj)

    async def fake_refresh(obj):
        obj.is_broken = False

    session.refresh = fake_refresh

    result = await update_building(
        session, siege_id=1, building_id=1, data=BuildingUpdate(is_broken=False)
    )

    assert result.is_broken is False

    # Verify new groups were added for group numbers 5 through 10
    from app.models.building_group import BuildingGroup

    added_groups = [o for o in added_objects if isinstance(o, BuildingGroup)]
    added_group_numbers = sorted(g.group_number for g in added_groups)
    assert added_group_numbers == list(
        range(5, 11)
    ), f"Expected groups 5–10 to be added, got {added_group_numbers}"

    # The previous last group (group 4, slot_count=2) must be expanded to 3
    assert (
        base_groups[3].slot_count == 3
    ), "Group 4 (previously last) should have been expanded to 3 slots"


@pytest.mark.asyncio
async def test_update_building_unbreak_restores_last_slot_count():
    """
    A Mana Shrine at level 5 has 13 teams = 4 full groups + 1 slot last group
    (4*3+1=13, so 5 groups, last=1 slot).  After being broken to base config
    (2 groups, last=2 slots) and then unbroken, the last group must have
    slot_count=1.
    """
    # mana_shrine level 5 → 13 teams → 5 groups, last has 1 slot
    expected_target_groups = 5
    expected_last_slots = 1

    siege = _make_siege()
    building = _make_building(id=2, building_type=BuildingType.mana_shrine, level=5, is_broken=True)

    # Base config for mana_shrine: 2 groups, last=2 slots
    base_groups = [
        _make_group(id=g, group_number=g, slot_count=(2 if g == 2 else 3)) for g in range(1, 3)
    ]

    # After rebuild adds groups 3, 4, 5 the actual last group is group 5
    # with slot_count=1 (matches last_slots so no further position tweak)
    new_last_group = _make_group(id=5, group_number=5, slot_count=1)

    call_count = 0

    async def fake_execute(stmt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _scalar_one_or_none(siege)
        if call_count == 2:
            return _scalar_one_or_none(building)
        if call_count == 3:
            return _scalars_all(base_groups)
        if call_count == 4:
            return _scalars_first(new_last_group)
        return _scalar_one_or_none(None)

    session = AsyncMock()
    session.execute = fake_execute
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.delete = AsyncMock()

    added_objects = []
    session.add = lambda obj: added_objects.append(obj)

    async def fake_refresh(obj):
        obj.is_broken = False

    session.refresh = fake_refresh

    await update_building(session, siege_id=1, building_id=2, data=BuildingUpdate(is_broken=False))

    from app.models.building_group import BuildingGroup

    added_groups = [o for o in added_objects if isinstance(o, BuildingGroup)]
    # Expect new groups for numbers 3, 4, 5
    added_group_numbers = sorted(g.group_number for g in added_groups)
    assert added_group_numbers == [
        3,
        4,
        5,
    ], f"Expected groups 3–5 to be added, got {added_group_numbers}"

    # The last added group must have slot_count=1
    last_added = next(g for g in added_groups if g.group_number == 5)
    assert (
        last_added.slot_count == expected_last_slots
    ), f"Last group slot_count should be {expected_last_slots}, got {last_added.slot_count}"

    # Group 2 (previously last at 2 slots) must have been expanded to 3
    assert base_groups[1].slot_count == 3, "Group 2 should have been expanded to 3 slots"


@pytest.mark.asyncio
async def test_update_building_break_then_unbreak_roundtrip():
    """
    Stronghold level 6: 10 groups × 3 slots.
    Break → reduces to base config (4 groups, last=2 slots).
    Unbreak → _rebuild_groups_for_level restores to 10 groups × 3 slots.

    This test runs both halves in sequence through two separate update_building
    calls to confirm the full roundtrip behaves correctly.
    """
    # --- BREAK phase ---
    siege = _make_siege()
    building_full = _make_building(
        id=1, building_type=BuildingType.stronghold, level=6, is_broken=False
    )

    # Simulate 10 groups existing before break
    full_groups = [_make_group(id=g, group_number=g, slot_count=3) for g in range(1, 11)]

    # Base config: 4 groups, last=2 slots
    config = _make_config(BuildingType.stronghold, base_group_count=4, base_last_group_slots=2)

    break_call_count = 0

    async def fake_execute_break(stmt):
        nonlocal break_call_count
        break_call_count += 1
        if break_call_count == 1:
            return _scalar_one_or_none(siege)
        if break_call_count == 2:
            return _scalar_one_or_none(building_full)
        # 3: building type config for break logic
        if break_call_count == 3:
            return _scalar_one_or_none(config)
        # 4: groups query for break logic
        if break_call_count == 4:
            return _scalars_all(full_groups)
        # 5: positions query for excess positions in last group
        if break_call_count == 5:
            return _scalars_all([])  # no positions to delete in this mock
        return _scalar_one_or_none(None)

    deleted_in_break = []

    break_session = AsyncMock()
    break_session.execute = fake_execute_break
    break_session.flush = AsyncMock()
    break_session.commit = AsyncMock()
    break_session.add = lambda obj: None

    async def fake_delete_break(obj):
        deleted_in_break.append(obj)

    break_session.delete = fake_delete_break

    async def fake_refresh_break(obj):
        obj.is_broken = True

    break_session.refresh = fake_refresh_break

    broken_result = await update_building(
        break_session, siege_id=1, building_id=1, data=BuildingUpdate(is_broken=True)
    )
    assert broken_result.is_broken is True

    # Groups 5–10 (indices 4–9) should have been deleted
    deleted_group_numbers = sorted(g.group_number for g in deleted_in_break)
    assert deleted_group_numbers == list(
        range(5, 11)
    ), f"Break should delete groups 5–10, got {deleted_group_numbers}"

    # Group 4's slot_count should have been trimmed to 2 (base_last_group_slots)
    assert full_groups[3].slot_count == 2, "Group 4 slot_count should be trimmed to 2 after break"

    # --- UNBREAK phase ---
    # Now the building is at base config: 4 groups, group 4 has 2 slots
    building_broken = _make_building(
        id=1, building_type=BuildingType.stronghold, level=6, is_broken=True
    )
    base_groups = [
        _make_group(id=g, group_number=g, slot_count=(2 if g == 4 else 3)) for g in range(1, 5)
    ]
    new_last = _make_group(id=10, group_number=10, slot_count=3)

    unbreak_call_count = 0

    async def fake_execute_unbreak(stmt):
        nonlocal unbreak_call_count
        unbreak_call_count += 1
        if unbreak_call_count == 1:
            return _scalar_one_or_none(siege)
        if unbreak_call_count == 2:
            return _scalar_one_or_none(building_broken)
        if unbreak_call_count == 3:
            return _scalars_all(base_groups)
        if unbreak_call_count == 4:
            return _scalars_first(new_last)
        return _scalar_one_or_none(None)

    added_in_unbreak = []
    unbreak_session = AsyncMock()
    unbreak_session.execute = fake_execute_unbreak
    unbreak_session.flush = AsyncMock()
    unbreak_session.commit = AsyncMock()
    unbreak_session.delete = AsyncMock()
    unbreak_session.add = lambda obj: added_in_unbreak.append(obj)

    async def fake_refresh_unbreak(obj):
        obj.is_broken = False

    unbreak_session.refresh = fake_refresh_unbreak

    restored_result = await update_building(
        unbreak_session, siege_id=1, building_id=1, data=BuildingUpdate(is_broken=False)
    )
    assert restored_result.is_broken is False

    from app.models.building_group import BuildingGroup

    added_groups = [o for o in added_in_unbreak if isinstance(o, BuildingGroup)]
    added_group_numbers = sorted(g.group_number for g in added_groups)

    # Groups 5–10 must be restored
    assert added_group_numbers == list(
        range(5, 11)
    ), f"Unbreak should restore groups 5–10, got {added_group_numbers}"

    # All restored groups except the last must have 3 slots
    for g in added_groups:
        if g.group_number < 10:
            assert g.slot_count == 3, f"Group {g.group_number} should have 3 slots"
    last_restored = next(g for g in added_groups if g.group_number == 10)
    assert last_restored.slot_count == 3, "Last restored group (10) should have 3 slots"

    # Group 4 should have been expanded back from 2 → 3 slots
    assert (
        base_groups[3].slot_count == 3
    ), "Group 4 should be expanded back to 3 slots during unbreak"
