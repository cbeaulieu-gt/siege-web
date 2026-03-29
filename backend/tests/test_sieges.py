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
async def test_compute_scroll_count_query_filters_broken_and_disabled():
    """compute_scroll_count query filters broken buildings and disabled positions.

    Verifies that the compiled SQL string contains both filter predicates, ensuring broken
    buildings and disabled positions are excluded from the scroll count baseline (issue #94).
    """
    import re
    from unittest.mock import MagicMock

    captured_stmt = {}

    async def capture_execute(stmt):
        captured_stmt["stmt"] = stmt
        result = MagicMock()
        result.scalar.return_value = 0
        return result

    session = AsyncMock()
    session.execute = capture_execute

    await compute_scroll_count(session, siege_id=5)

    assert "stmt" in captured_stmt, "execute was never called"
    sql = str(captured_stmt["stmt"].compile(compile_kwargs={"literal_binds": True}))

    # Both filters must appear in the compiled query
    assert re.search(
        r"building\.is_broken\s*=\s*false", sql, re.IGNORECASE
    ), f"Expected 'building.is_broken = false' filter in query, got:\n{sql}"
    assert re.search(
        r"position\.is_disabled\s*=\s*false", sql, re.IGNORECASE
    ), f"Expected 'position.is_disabled = false' filter in query, got:\n{sql}"
