"""Endpoint tests for /api/members — mocks the service layer directly."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.enums import MemberRole
from app.models.member import Member


def _make_member(
    id: int = 1,
    name: str = "Alice",
    role: MemberRole = MemberRole.advanced,
    is_active: bool = True,
) -> Member:
    m = Member.__new__(Member)
    m.id = id
    m.name = name
    m.discord_username = None
    m.role = role
    m.power = None
    m.sort_value = None
    m.is_active = is_active
    m.created_at = __import__("datetime").datetime(2026, 1, 1, 0, 0, 0)
    return m


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# 1. list_members returns empty list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_members_returns_empty_list(client):
    with patch("app.api.members.members_service.list_members", new_callable=AsyncMock) as mock:
        mock.return_value = []
        async with client as c:
            response = await c.get("/api/members")

    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# 2. create_member returns 201 with member data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_member_returns_201(client):
    member = _make_member()
    with patch("app.api.members.members_service.create_member", new_callable=AsyncMock) as mock:
        mock.return_value = member
        async with client as c:
            response = await c.post(
                "/api/members",
                json={"name": "Alice", "role": "advanced"},
            )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "Alice"
    assert data["role"] == "advanced"
    assert data["is_active"] is True


# ---------------------------------------------------------------------------
# 3. create_member with duplicate name returns 409
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_member_duplicate_name_returns_409(client):
    from fastapi import HTTPException

    with patch("app.api.members.members_service.create_member", new_callable=AsyncMock) as mock:
        mock.side_effect = HTTPException(
            status_code=409, detail="A member with this name already exists"
        )
        async with client as c:
            response = await c.post(
                "/api/members",
                json={"name": "Alice", "role": "advanced"},
            )

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


# ---------------------------------------------------------------------------
# 4. get_member not found returns 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_member_not_found_returns_404(client):
    from fastapi import HTTPException

    with patch("app.api.members.members_service.get_member", new_callable=AsyncMock) as mock:
        mock.side_effect = HTTPException(status_code=404, detail="Member not found")
        async with client as c:
            response = await c.get("/api/members/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Member not found"


# ---------------------------------------------------------------------------
# 5. delete_member returns 204
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_member_returns_204(client):
    member = _make_member(is_active=False)
    with patch(
        "app.api.members.members_service.deactivate_member", new_callable=AsyncMock
    ) as mock:
        mock.return_value = member
        async with client as c:
            response = await c.delete("/api/members/1")

    assert response.status_code == 204
