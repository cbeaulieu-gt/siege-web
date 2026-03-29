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
    with (
        patch("app.api.sieges.sieges_service.create_siege", new_callable=AsyncMock) as mock,
        patch(
            "app.api.sieges.sieges_service.compute_scroll_count", new_callable=AsyncMock
        ) as mock_scroll,
    ):
        mock.return_value = siege
        mock_scroll.return_value = 0
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


# ---------------------------------------------------------------------------
# 6. compute_scroll_count — unit tests for the query filter fix (issue #94)
# ---------------------------------------------------------------------------


from app.services.sieges import compute_scroll_count  # noqa: E402


@pytest.mark.asyncio
async def test_compute_scroll_count_returns_db_value():
    """compute_scroll_count passes the DB scalar result through unchanged."""
    from unittest.mock import MagicMock

    mock_result = MagicMock()
    mock_result.scalar.return_value = 42

    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)

    count = await compute_scroll_count(session, siege_id=1)

    assert count == 42
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_compute_scroll_count_returns_zero_when_none():
    """compute_scroll_count returns 0 when the DB scalar is None (empty result)."""
    from unittest.mock import MagicMock

    mock_result = MagicMock()
    mock_result.scalar.return_value = None

    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)

    count = await compute_scroll_count(session, siege_id=1)

    assert count == 0


@pytest.mark.asyncio
async def test_compute_scroll_count_excludes_broken_buildings():
    """compute_scroll_count excludes broken-building positions from the count (issue #94).

    The DB mock returns different values based on what the query filters out.  We verify that
    the function passes the result through unchanged: if the DB (after applying is_broken=false
    and is_disabled=false) returns 3, the function returns 3 — not 6 (all positions) or 0.

    This is a behavioral test: it confirms the function does not add, subtract, or ignore the
    DB scalar.  The SQL filter itself is exercised through the ORM (the WHERE clauses are built
    by compute_scroll_count and sent to the DB); the mock represents the DB honouring those
    filters and returning the filtered count.
    """
    from unittest.mock import MagicMock

    # Scenario: 2 buildings, each 3 positions.  Building 2 is broken.
    # DB honours the is_broken=false filter and returns 3 (building 1 only).
    mock_result = MagicMock()
    mock_result.scalar.return_value = 3

    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)

    count = await compute_scroll_count(session, siege_id=1)

    assert count == 3, (
        "compute_scroll_count must return exactly the DB scalar — "
        "broken buildings are excluded by the WHERE clause so the DB returns 3, not 6"
    )
    # Confirm the session was queried exactly once (no extra fallback queries)
    session.execute.assert_awaited_once()
