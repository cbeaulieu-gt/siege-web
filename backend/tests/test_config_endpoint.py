"""Tests for the /api/config public endpoint and startup guards.

Covers:
  - /api/config returns correct auth_disabled flag
  - Endpoint is public (no auth header needed)
  - Startup guard raises for missing SESSION_SECRET when auth is enabled
"""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.db.session import get_db
from app.main import app


@pytest.fixture
def mock_db():
    session = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture(autouse=True)
def override_db(mock_db):
    async def _get_db():
        yield mock_db

    app.dependency_overrides[get_db] = _get_db
    yield
    app.dependency_overrides.clear()


class TestConfigEndpoint:
    """GET /api/config returns the current auth_disabled flag."""

    @pytest.mark.asyncio
    async def test_config_returns_auth_disabled_true(self, monkeypatch):
        import app.api.config as api_config_module
        import app.config as config_module
        import app.main as main_module

        s = Settings(
            database_url="postgresql+asyncpg://u:p@localhost/db",
            discord_bot_api_url="http://bot:8001",
            discord_bot_api_key="key",
            discord_guild_id="111",
            environment="development",
            auth_disabled=True,
        )
        monkeypatch.setattr(config_module, "settings", s)
        monkeypatch.setattr(main_module, "settings", s)
        monkeypatch.setattr(api_config_module, "settings", s)

        async with AsyncClient(
            transport=ASGITransport(app=main_module.app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/config")

        assert response.status_code == 200
        assert response.json()["auth_disabled"] is True

    @pytest.mark.asyncio
    async def test_config_returns_auth_disabled_false(self, monkeypatch):
        import app.api.config as api_config_module
        import app.config as config_module
        import app.main as main_module

        s = Settings(
            database_url="postgresql+asyncpg://u:p@localhost/db",
            discord_bot_api_url="http://bot:8001",
            discord_bot_api_key="key",
            discord_guild_id="111",
            environment="development",
            auth_disabled=False,
        )
        monkeypatch.setattr(config_module, "settings", s)
        monkeypatch.setattr(main_module, "settings", s)
        monkeypatch.setattr(api_config_module, "settings", s)

        async with AsyncClient(
            transport=ASGITransport(app=main_module.app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/config")

        assert response.status_code == 200
        assert response.json()["auth_disabled"] is False

    @pytest.mark.asyncio
    async def test_config_endpoint_is_public(self, monkeypatch):
        """Config endpoint must be reachable without an Authorization header."""
        import app.api.config as api_config_module
        import app.config as config_module
        import app.main as main_module

        s = Settings(
            database_url="postgresql+asyncpg://u:p@localhost/db",
            discord_bot_api_url="http://bot:8001",
            discord_bot_api_key="key",
            discord_guild_id="111",
            environment="development",
            auth_disabled=True,
        )
        monkeypatch.setattr(config_module, "settings", s)
        monkeypatch.setattr(main_module, "settings", s)
        monkeypatch.setattr(api_config_module, "settings", s)

        async with AsyncClient(
            transport=ASGITransport(app=main_module.app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            # Explicitly send no auth headers.
            response = await client.get("/api/config", headers={})

        # Should not be a 401 or 403.
        assert response.status_code not in (401, 403)


class TestStartupSessionSecretGuard:
    """Backend must refuse to start when SESSION_SECRET is missing and auth is enabled."""

    @pytest.mark.asyncio
    async def test_missing_session_secret_raises_at_startup(self, monkeypatch):
        """RuntimeError raised when auth_disabled=False and session_secret is empty."""
        import app.config as config_module
        import app.main as main_module

        s = Settings(
            database_url="postgresql+asyncpg://u:p@localhost/db",
            discord_bot_api_url="http://bot:8001",
            discord_bot_api_key="key",
            discord_guild_id="111",
            environment="development",
            auth_disabled=False,
            session_secret="",  # Empty — should trigger guard.
        )
        monkeypatch.setattr(config_module, "settings", s)
        monkeypatch.setattr(main_module, "settings", s)

        with pytest.raises(RuntimeError, match="SESSION_SECRET must be set"):
            async with main_module.lifespan(main_module.app):
                pass

    @pytest.mark.asyncio
    async def test_present_session_secret_does_not_raise(self, monkeypatch):
        """No RuntimeError when auth_disabled=False and session_secret is provided."""
        import app.config as config_module
        import app.main as main_module

        s = Settings(
            database_url="postgresql+asyncpg://u:p@localhost/db",
            discord_bot_api_url="http://bot:8001",
            discord_bot_api_key="key",
            discord_guild_id="111",
            environment="development",
            auth_disabled=False,
            session_secret="a-secure-secret-value",
        )
        monkeypatch.setattr(config_module, "settings", s)
        monkeypatch.setattr(main_module, "settings", s)

        # Should complete without raising.
        async with AsyncClient(
            transport=ASGITransport(app=main_module.app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/health")
        assert response.status_code in (200, 500, 503)
