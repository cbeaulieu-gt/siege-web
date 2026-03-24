from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import app


@pytest.fixture
def mock_db():
    session = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_health_returns_healthy(mock_db):
    """Health endpoint returns 200 and healthy status when DB is reachable."""

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/health")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
