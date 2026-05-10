"""Tests for enum definitions and associated constants in app.models.enums."""

from app.models.enums import BUILDING_TYPE_LABELS, BuildingType


def test_building_type_labels_covers_all_values():
    """Every BuildingType member must have an entry in BUILDING_TYPE_LABELS.

    This is a coverage guard: if a new BuildingType is added without a
    corresponding label, this test will fail immediately rather than leaking
    a raw enum value into user-facing messages at runtime.
    """
    assert set(BUILDING_TYPE_LABELS.keys()) == set(BuildingType)


def test_building_type_labels_are_friendly_strings():
    """BUILDING_TYPE_LABELS values must be non-empty title-cased display strings.

    Verifies that the label for each BuildingType is a non-empty string that
    does not match the raw enum value (i.e. underscores replaced, capitalized).
    """
    for bt, label in BUILDING_TYPE_LABELS.items():
        assert isinstance(label, str), f"Label for {bt!r} must be str"
        assert label, f"Label for {bt!r} must not be empty"
        assert "_" not in label, f"Label for {bt!r} must not contain underscores, got {label!r}"
        assert label[0].isupper(), f"Label for {bt!r} must start with uppercase, got {label!r}"
