"""Endpoint tests for /api/sieges — mocks the service layer directly."""

import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.enums import SiegeStatus


def _make_siege(
    id: int = 1,
    status: SiegeStatus = SiegeStatus.planning,
    defense_scroll_count: int = 5,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        date=datetime.date(2026, 3, 20),
        status=status,
        defense_scroll_count=defense_scroll_count,
        created_at=datetime.datetime(2026, 1, 1, 0, 0, 0),
        updated_at=datetime.datetime(2026, 1, 1, 0, 0, 0),
    )


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# 1. list_sieges returns empty list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_sieges_returns_empty_list(client):
    with patch("app.api.sieges.sieges_service.list_sieges", new_callable=AsyncMock) as mock:
        mock.return_value = []
        async with client as c:
            response = await c.get("/api/sieges")

    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# 2. create_siege returns 201
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_siege_returns_201(client):
    siege = _make_siege()
    with patch("app.api.sieges.sieges_service.create_siege", new_callable=AsyncMock) as mock:
        mock.return_value = siege
        async with client as c:
            response = await c.post(
                "/api/sieges",
                json={"date": "2026-03-20", "defense_scroll_count": 5},
            )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 1
    assert data["date"] == "2026-03-20"
    assert data["status"] == "planning"
    assert data["defense_scroll_count"] == 5


# ---------------------------------------------------------------------------
# 3. get_siege not found returns 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_siege_not_found_returns_404(client):
    with patch("app.api.sieges.sieges_service.get_siege", new_callable=AsyncMock) as mock:
        mock.side_effect = HTTPException(status_code=404, detail="Siege not found")
        async with client as c:
            response = await c.get("/api/sieges/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Siege not found"


# ---------------------------------------------------------------------------
# 4. delete planning siege returns 204
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_planning_siege_returns_204(client):
    with patch("app.api.sieges.sieges_service.delete_siege", new_callable=AsyncMock) as mock:
        mock.return_value = None
        async with client as c:
            response = await c.delete("/api/sieges/1")

    assert response.status_code == 204


# ---------------------------------------------------------------------------
# 5. delete active siege returns 400
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_active_siege_returns_400(client):
    with patch("app.api.sieges.sieges_service.delete_siege", new_callable=AsyncMock) as mock:
        mock.side_effect = HTTPException(
            status_code=400, detail="Only planning sieges can be deleted"
        )
        async with client as c:
            response = await c.delete("/api/sieges/2")

    assert response.status_code == 400
    assert "planning" in response.json()["detail"]
