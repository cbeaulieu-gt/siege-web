"""Endpoint tests for siege lifecycle transitions: activate, complete, clone."""

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
    date: datetime.date | None = datetime.date(2026, 3, 20),
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        date=date,
        status=status,
        defense_scroll_count=defense_scroll_count,
        created_at=datetime.datetime(2026, 1, 1, 0, 0, 0),
        updated_at=datetime.datetime(2026, 1, 1, 0, 0, 0),
    )


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# 1. activate planning siege returns 200 with status=active
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activate_planning_siege(client):
    siege = _make_siege(status=SiegeStatus.active)
    with patch(
        "app.api.lifecycle.lifecycle_service.activate_siege", new_callable=AsyncMock
    ) as mock:
        mock.return_value = siege
        async with client as c:
            response = await c.post("/api/sieges/1/activate")

    assert response.status_code == 200
    assert response.json()["status"] == "active"


# ---------------------------------------------------------------------------
# 2. activating an already-active siege returns 400
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activate_already_active_returns_400(client):
    with patch(
        "app.api.lifecycle.lifecycle_service.activate_siege", new_callable=AsyncMock
    ) as mock:
        mock.side_effect = HTTPException(
            status_code=400, detail="Cannot activate a siege with status 'active'"
        )
        async with client as c:
            response = await c.post("/api/sieges/2/activate")

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# 3. complete an active siege returns 200 with status=complete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_complete_active_siege(client):
    siege = _make_siege(status=SiegeStatus.complete)
    with patch(
        "app.api.lifecycle.lifecycle_service.complete_siege", new_callable=AsyncMock
    ) as mock:
        mock.return_value = siege
        async with client as c:
            response = await c.post("/api/sieges/1/complete")

    assert response.status_code == 200
    assert response.json()["status"] == "complete"


# ---------------------------------------------------------------------------
# 4. completing a planning siege returns 400
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_complete_planning_siege_returns_400(client):
    with patch(
        "app.api.lifecycle.lifecycle_service.complete_siege", new_callable=AsyncMock
    ) as mock:
        mock.side_effect = HTTPException(
            status_code=400, detail="Cannot complete a siege with status 'planning'"
        )
        async with client as c:
            response = await c.post("/api/sieges/1/complete")

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# 5. clone returns 201 with new siege id, status=planning, date=None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clone_siege_returns_201(client):
    cloned = _make_siege(id=99, status=SiegeStatus.planning, date=None)
    with patch(
        "app.api.lifecycle.lifecycle_service.clone_siege", new_callable=AsyncMock
    ) as mock:
        mock.return_value = cloned
        async with client as c:
            response = await c.post("/api/sieges/1/clone")

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 99
    assert data["status"] == "planning"
    assert data["date"] is None
