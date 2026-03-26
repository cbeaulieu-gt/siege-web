"""Tests for the bot HTTP API endpoints."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

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
# GET /version
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_version_returns_200(client):
    """GET /version responds 200 with a 'version' key."""
    async with client as c:
        response = await c.get("/version")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data


@pytest.mark.asyncio
async def test_version_bare_semver_in_local_dev(client, monkeypatch, tmp_path):
    """When BUILD_NUMBER / GIT_SHA are absent the version is the bare semver."""
    version_file = tmp_path / "VERSION"
    version_file.write_text("2.3.4")
    monkeypatch.delenv("BUILD_NUMBER", raising=False)
    monkeypatch.delenv("GIT_SHA", raising=False)

    original = http_api_module._VERSION_FILE
    http_api_module._VERSION_FILE = version_file
    try:
        async with client as c:
            response = await c.get("/version")
    finally:
        http_api_module._VERSION_FILE = original

    assert response.status_code == 200
    assert response.json()["version"] == "2.3.4"


@pytest.mark.asyncio
async def test_version_includes_build_suffix_when_env_vars_set(client, monkeypatch, tmp_path):
    """When BUILD_NUMBER and GIT_SHA are set, version is 'semver+build.sha7'."""
    version_file = tmp_path / "VERSION"
    version_file.write_text("1.0.1")
    monkeypatch.setenv("BUILD_NUMBER", "42")
    monkeypatch.setenv("GIT_SHA", "abc1234567890")

    original = http_api_module._VERSION_FILE
    http_api_module._VERSION_FILE = version_file
    try:
        async with client as c:
            response = await c.get("/version")
    finally:
        http_api_module._VERSION_FILE = original

    assert response.status_code == 200
    assert response.json()["version"] == "1.0.1+42.abc1234"


@pytest.mark.asyncio
async def test_version_unknown_when_version_file_missing(client, monkeypatch, tmp_path):
    """When the VERSION file is absent, semver falls back to 'unknown'."""
    monkeypatch.delenv("BUILD_NUMBER", raising=False)
    monkeypatch.delenv("GIT_SHA", raising=False)

    original = http_api_module._VERSION_FILE
    http_api_module._VERSION_FILE = tmp_path / "NONEXISTENT"
    try:
        async with client as c:
            response = await c.get("/version")
    finally:
        http_api_module._VERSION_FILE = original

    assert response.status_code == 200
    assert response.json()["version"] == "unknown"


@pytest.mark.asyncio
async def test_version_bare_semver_when_env_vars_are_unknown_literal(client, monkeypatch, tmp_path):
    """Env vars explicitly set to 'unknown' should yield bare semver (no suffix)."""
    version_file = tmp_path / "VERSION"
    version_file.write_text("1.2.3")
    monkeypatch.setenv("BUILD_NUMBER", "unknown")
    monkeypatch.setenv("GIT_SHA", "unknown")

    original = http_api_module._VERSION_FILE
    http_api_module._VERSION_FILE = version_file
    try:
        async with client as c:
            response = await c.get("/version")
    finally:
        http_api_module._VERSION_FILE = original

    assert response.status_code == 200
    assert response.json()["version"] == "1.2.3"


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
