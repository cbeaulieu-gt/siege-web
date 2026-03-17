"""Endpoint tests for post management routes."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.building import Building
from app.models.post import Post
from app.models.enums import BuildingType


def _make_building(id: int = 10, building_number: int = 1) -> Building:
    b = Building.__new__(Building)
    b.id = id
    b.siege_id = 1
    b.building_type = BuildingType.post
    b.building_number = building_number
    b.level = 1
    b.is_broken = False
    return b


def _make_post(
    id: int = 1,
    siege_id: int = 1,
    building_id: int = 10,
    priority: int = 1,
    description: str | None = None,
) -> Post:
    p = Post.__new__(Post)
    p.id = id
    p.siege_id = siege_id
    p.building_id = building_id
    p.priority = priority
    p.description = description
    p.active_conditions = []
    p.building = _make_building(id=building_id)
    return p


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
    with patch(
        "app.api.posts.posts_service.set_post_conditions", new_callable=AsyncMock
    ) as mock:
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
