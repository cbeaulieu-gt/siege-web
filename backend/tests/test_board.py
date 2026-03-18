"""Endpoint tests for board, position update, and bulk assignment routes."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.main import app


def _make_position(
    id: int = 1,
    position_number: int = 1,
    member_id: int | None = None,
    is_reserve: bool = False,
    is_disabled: bool = False,
    matched_condition_id: int | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        building_group_id=1,
        position_number=position_number,
        member_id=member_id,
        is_reserve=is_reserve,
        is_disabled=is_disabled,
        matched_condition_id=matched_condition_id,
    )


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# 1. get_board returns nested structure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_board_returns_nested_structure(client):
    board_dict = {
        "siege_id": 1,
        "buildings": [
            {
                "id": 10,
                "building_type": "stronghold",
                "building_number": 1,
                "level": 3,
                "is_broken": False,
                "groups": [],
            }
        ],
    }
    with patch("app.api.board.board_service.get_board", new_callable=AsyncMock) as mock:
        mock.return_value = board_dict
        async with client as c:
            response = await c.get("/api/sieges/1/board")

    assert response.status_code == 200
    data = response.json()
    assert "buildings" in data
    assert data["siege_id"] == 1
    assert len(data["buildings"]) == 1


# ---------------------------------------------------------------------------
# 2. update_position assigns a member (returns 200)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_position_assign_member(client):
    position = _make_position(id=5, member_id=42)
    with patch("app.api.board.board_service.update_position", new_callable=AsyncMock) as mock:
        mock.return_value = position
        async with client as c:
            response = await c.put(
                "/api/sieges/1/positions/5",
                json={"member_id": 42, "is_reserve": False, "is_disabled": False},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 5
    assert data["member_id"] == 42


# ---------------------------------------------------------------------------
# 3. update_position with reserve=True and member_id set returns 400
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_position_invalid_state_reserve_with_member(client):
    with patch("app.api.board.board_service.update_position", new_callable=AsyncMock) as mock:
        mock.side_effect = HTTPException(
            status_code=400,
            detail="A reserve position cannot have a member assigned",
        )
        async with client as c:
            response = await c.put(
                "/api/sieges/1/positions/5",
                json={"member_id": 42, "is_reserve": True, "is_disabled": False},
            )

    assert response.status_code == 400
    assert "reserve" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 4. update_position for unknown position_id returns 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_position_not_found(client):
    with patch("app.api.board.board_service.update_position", new_callable=AsyncMock) as mock:
        mock.side_effect = HTTPException(status_code=404, detail="Position not found")
        async with client as c:
            response = await c.put(
                "/api/sieges/1/positions/9999",
                json={"member_id": None, "is_reserve": False, "is_disabled": False},
            )

    assert response.status_code == 404
    assert response.json()["detail"] == "Position not found"
