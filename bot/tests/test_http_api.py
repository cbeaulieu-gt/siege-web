"""Tests for the bot HTTP API endpoints."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

import app.http_api as http_api_module
from app.http_api import app

API_KEY = "test-key"
AUTH_HEADER = {"Authorization": f"Bearer {API_KEY}"}


@pytest.fixture(autouse=True)
def patch_api_key(monkeypatch):
    """Override the bot_api_key setting for all tests."""
    monkeypatch.setattr(http_api_module.settings, "bot_api_key", API_KEY)


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _make_mock_bot(ready: bool = True) -> MagicMock:
    bot = MagicMock()
    bot.is_ready.return_value = ready
    bot.send_dm = AsyncMock()
    bot.post_message = AsyncMock()
    bot.post_image = AsyncMock()
    bot.get_members = AsyncMock(return_value=[])
    return bot


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_no_bot(client):
    http_api_module._bot = None
    async with client as c:
        response = await c.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["bot_connected"] is False


@pytest.mark.asyncio
async def test_health_with_bot_connected(client):
    http_api_module._bot = _make_mock_bot(ready=True)
    async with client as c:
        response = await c.get("/api/health")
    assert response.status_code == 200
    assert response.json()["bot_connected"] is True
    http_api_module._bot = None


# ---------------------------------------------------------------------------
# POST /api/notify
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_success(client):
    bot = _make_mock_bot()
    http_api_module._bot = bot
    async with client as c:
        response = await c.post(
            "/api/notify",
            json={"username": "testuser", "message": "Hello!"},
            headers=AUTH_HEADER,
        )
    assert response.status_code == 200
    assert response.json() == {"status": "sent"}
    bot.send_dm.assert_awaited_once_with("testuser", "Hello!")
    http_api_module._bot = None


@pytest.mark.asyncio
async def test_notify_bot_not_ready_returns_503(client):
    http_api_module._bot = None
    async with client as c:
        response = await c.post(
            "/api/notify",
            json={"username": "testuser", "message": "Hello!"},
            headers=AUTH_HEADER,
        )
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_notify_member_not_found_returns_404(client):
    bot = _make_mock_bot()
    bot.send_dm.side_effect = ValueError("Member 'ghost' not found in guild")
    http_api_module._bot = bot
    async with client as c:
        response = await c.post(
            "/api/notify",
            json={"username": "ghost", "message": "Hi"},
            headers=AUTH_HEADER,
        )
    assert response.status_code == 404
    assert "ghost" in response.json()["detail"]
    http_api_module._bot = None


# ---------------------------------------------------------------------------
# POST /api/post-message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_message_success(client):
    bot = _make_mock_bot()
    http_api_module._bot = bot
    async with client as c:
        response = await c.post(
            "/api/post-message",
            json={"channel_name": "general", "message": "Siege ready!"},
            headers=AUTH_HEADER,
        )
    assert response.status_code == 200
    assert response.json() == {"status": "sent"}
    bot.post_message.assert_awaited_once_with("general", "Siege ready!")
    http_api_module._bot = None


@pytest.mark.asyncio
async def test_post_message_bot_not_ready_returns_503(client):
    http_api_module._bot = None
    async with client as c:
        response = await c.post(
            "/api/post-message",
            json={"channel_name": "general", "message": "Hi"},
            headers=AUTH_HEADER,
        )
    assert response.status_code == 503


# ---------------------------------------------------------------------------
# POST /api/post-image
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_image_success(client):
    bot = _make_mock_bot()
    bot.post_image.return_value = "https://cdn.discordapp.com/attachments/123/board.png"
    http_api_module._bot = bot
    async with client as c:
        response = await c.post(
            "/api/post-image?channel_name=siege-images",
            files={"file": ("board.png", b"fake-png-bytes", "image/png")},
            headers=AUTH_HEADER,
        )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "sent"
    assert data["url"] == "https://cdn.discordapp.com/attachments/123/board.png"
    bot.post_image.assert_awaited_once_with("siege-images", b"fake-png-bytes", "board.png")
    http_api_module._bot = None


@pytest.mark.asyncio
async def test_post_image_bot_not_ready_returns_503(client):
    http_api_module._bot = None
    async with client as c:
        response = await c.post(
            "/api/post-image?channel_name=siege-images",
            files={"file": ("board.png", b"fake-png-bytes", "image/png")},
            headers=AUTH_HEADER,
        )
    assert response.status_code == 503


# ---------------------------------------------------------------------------
# GET /api/members
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_members_returns_list(client):
    members = [
        {"id": "123", "username": "alice", "display_name": "Alice"},
        {"id": "456", "username": "bob", "display_name": "Bob"},
    ]
    bot = _make_mock_bot()
    bot.get_members.return_value = members
    http_api_module._bot = bot
    async with client as c:
        response = await c.get("/api/members", headers=AUTH_HEADER)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["username"] == "alice"
    http_api_module._bot = None


@pytest.mark.asyncio
async def test_get_members_bot_not_ready_returns_503(client):
    http_api_module._bot = None
    async with client as c:
        response = await c.get("/api/members", headers=AUTH_HEADER)
    assert response.status_code == 503
