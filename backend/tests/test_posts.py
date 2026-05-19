"""Endpoint tests for post management routes."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.enums import BuildingType


def _make_building(id: int = 10, building_number: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        siege_id=1,
        building_type=BuildingType.post,
        building_number=building_number,
        level=1,
        is_broken=False,
    )


def _make_condition(
    id: int = 1,
    description: str = "Role: Heavy Hitter",
    stronghold_level: int = 1,
    condition_type: str = "role",
) -> SimpleNamespace:
    """Build a minimal PostCondition-shaped object for test fixtures."""
    return SimpleNamespace(
        id=id,
        description=description,
        stronghold_level=stronghold_level,
        condition_type=condition_type,
    )


def _make_post(
    id: int = 1,
    siege_id: int = 1,
    building_id: int = 10,
    building_number: int = 1,
    priority: int = 1,
    description: str | None = None,
    active_conditions: list | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        siege_id=siege_id,
        building_id=building_id,
        priority=priority,
        description=description,
        active_conditions=active_conditions if active_conditions is not None else [],
        building=_make_building(id=building_id, building_number=building_number),
    )


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# 1. list_posts returns a list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_posts_returns_list(client):
    posts = [_make_post(id=1), _make_post(id=2, priority=2)]
    with patch("app.api.posts.posts_service.list_posts", new_callable=AsyncMock) as mock:
        mock.return_value = posts
        async with client as c:
            response = await c.get("/api/sieges/1/posts")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["id"] == 1
    assert data[0]["building_number"] == 1


# ---------------------------------------------------------------------------
# 2. update_post priority returns updated post
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_post_priority(client):
    post = _make_post(id=1, priority=5)
    with patch("app.api.posts.posts_service.update_post", new_callable=AsyncMock) as mock:
        mock.return_value = post
        async with client as c:
            response = await c.put("/api/sieges/1/posts/1", json={"priority": 5})

    assert response.status_code == 200
    assert response.json()["priority"] == 5


# ---------------------------------------------------------------------------
# 3. set_post_conditions with 4 IDs returns 400
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_post_conditions_too_many_returns_400(client):
    with patch("app.api.posts.posts_service.set_post_conditions", new_callable=AsyncMock) as mock:
        mock.side_effect = HTTPException(
            status_code=400, detail="A post can have at most 3 active conditions"
        )
        async with client as c:
            response = await c.put(
                "/api/sieges/1/posts/1/conditions",
                json={"post_condition_ids": [1, 2, 3, 4]},
            )

    assert response.status_code == 400
    assert "3" in response.json()["detail"]


# ---------------------------------------------------------------------------
# 4. list_posts response is sorted by building_number ascending
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_posts_sorted_by_building_number(client):
    """Posts endpoint returns rows sorted by Post # (building_number) ascending.

    The service returns posts in DB-insertion order: building_number 3 first
    (highest priority=3), then 1, then 2.  The endpoint must re-order them
    to [1, 2, 3] regardless of priority so that priority edits never change
    the visual order.
    """
    posts = [
        _make_post(id=3, building_id=30, building_number=3, priority=3),
        _make_post(id=1, building_id=10, building_number=1, priority=1),
        _make_post(id=2, building_id=20, building_number=2, priority=2),
    ]
    with patch("app.api.posts.posts_service.list_posts", new_callable=AsyncMock) as mock:
        mock.return_value = posts
        async with client as c:
            response = await c.get("/api/sieges/1/posts")

    assert response.status_code == 200
    data = response.json()
    building_numbers = [item["building_number"] for item in data]
    assert building_numbers == [
        1,
        2,
        3,
    ], f"Expected posts sorted by building_number [1,2,3], got {building_numbers}"


# ---------------------------------------------------------------------------
# 5. active_conditions in list_posts response includes condition_type field
#    Regression for #450: _serialize_post omitted condition_type, causing a
#    ResponseValidationError (HTTP 500) on every GET /api/sieges/{id}/posts
#    when posts had active conditions.
# ---------------------------------------------------------------------------

VALID_CONDITION_TYPES = {"role", "affinity", "faction", "league", "rarity", "effect", "other"}


@pytest.mark.asyncio
async def test_list_posts_active_conditions_include_condition_type(client):
    """Each active_condition in the posts list response must include condition_type.

    Without the fix, FastAPI's response validation raises ResponseValidationError
    (HTTP 500) because PostConditionResponse declares condition_type as a required
    Literal field that the hand-rolled serializer dict did not populate.
    """
    condition = _make_condition(
        id=7, description="Role: Heavy Hitter", stronghold_level=1, condition_type="role"
    )
    post = _make_post(id=1, active_conditions=[condition])

    with patch("app.api.posts.posts_service.list_posts", new_callable=AsyncMock) as mock:
        mock.return_value = [post]
        async with client as c:
            response = await c.get("/api/sieges/1/posts")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert len(data) == 1
    conditions = data[0]["active_conditions"]
    assert len(conditions) == 1, "Post fixture has one active condition — response must include it"
    cond = conditions[0]
    assert "condition_type" in cond, (
        "condition_type must be present in active_condition response; "
        "its absence causes ResponseValidationError (HTTP 500)"
    )
    assert (
        cond["condition_type"] in VALID_CONDITION_TYPES
    ), f"condition_type '{cond['condition_type']}' is not one of {VALID_CONDITION_TYPES}"
    assert cond["id"] == 7
    assert cond["stronghold_level"] == 1
