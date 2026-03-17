"""Endpoint tests for /api reference data endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.enums import BuildingType
from app.models.post_condition import PostCondition


def _make_post_condition(id: int, description: str, stronghold_level: int) -> PostCondition:
    pc = PostCondition.__new__(PostCondition)
    pc.id = id
    pc.description = description
    pc.stronghold_level = stronghold_level
    return pc


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# 1. get_post_conditions returns list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_post_conditions_returns_list(client):
    conditions = [
        _make_post_condition(1, "Condition A", 1),
        _make_post_condition(2, "Condition B", 2),
    ]
    with patch(
        "app.api.reference.reference_service.get_post_conditions", new_callable=AsyncMock
    ) as mock:
        mock.return_value = conditions
        async with client as c:
            response = await c.get("/api/post-conditions")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["id"] == 1
    assert data[0]["description"] == "Condition A"
    assert data[0]["stronghold_level"] == 1


# ---------------------------------------------------------------------------
# 2. get_building_types returns list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_building_types_returns_list(client):
    building_types = [
        {
            "value": BuildingType.stronghold.value,
            "display": "Stronghold",
            "count": 1,
            "base_group_count": 9,
            "base_last_group_slots": 2,
        },
        {
            "value": BuildingType.post.value,
            "display": "Post",
            "count": 18,
            "base_group_count": 1,
            "base_last_group_slots": 3,
        },
    ]
    with patch(
        "app.api.reference.reference_service.get_building_types", new_callable=AsyncMock
    ) as mock:
        mock.return_value = building_types
        async with client as c:
            response = await c.get("/api/building-types")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["value"] == "stronghold"


# ---------------------------------------------------------------------------
# 3. get_member_roles returns exactly four roles
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_member_roles_returns_four_roles(client):
    roles = [
        {"value": "heavy_hitter", "display": "Heavy Hitter", "default_attack_day": 2},
        {"value": "advanced", "display": "Advanced", "default_attack_day": 2},
        {"value": "medium", "display": "Medium", "default_attack_day": 1},
        {"value": "novice", "display": "Novice", "default_attack_day": 1},
    ]
    with patch(
        "app.api.reference.reference_service.get_member_roles", new_callable=AsyncMock
    ) as mock:
        mock.return_value = roles
        async with client as c:
            response = await c.get("/api/member-roles")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 4
    values = [r["value"] for r in data]
    assert "heavy_hitter" in values
    assert "novice" in values
