"""Tests for GET /api/members/{discord_user_id} — guild member lookup endpoint."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

import app.http_api as http_api_module
from app.http_api import app

# Import the fake exception classes that conftest installed into sys.modules so
# we can raise them in mocks without importing the real discord library.
import sys

_discord = sys.modules["discord"]

API_KEY = "test-key"
AUTH_HEADER = {"Authorization": f"Bearer {API_KEY}"}
GUILD_ID = 123456789
USER_ID = "987654321"


@pytest.fixture(autouse=True)
def patch_api_key(monkeypatch):
    """Override the bot_api_key setting for all tests."""
    monkeypatch.setattr(http_api_module.settings, "bot_api_key", API_KEY)


@pytest.fixture(autouse=True)
def patch_guild_id(monkeypatch):
    """Override the discord_guild_id setting for all tests."""
    monkeypatch.setattr(http_api_module.settings, "discord_guild_id", str(GUILD_ID))


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _make_mock_member(
    discord_id: int = int(USER_ID),
    name: str = "siegemaster",
    display_name: str = "SiegeMaster",
    role_ids: list[int] | None = None,
) -> MagicMock:
    """Build a mock discord.Member with realistic attributes.

    ``role_ids`` defaults to ``[111, 222]`` when ``None`` (not provided).
    Pass an explicit empty list ``[]`` to get a member with no roles beyond
    ``@everyone``.
    """
    member = MagicMock()
    member.id = discord_id
    member.name = name
    member.display_name = display_name

    roles = []
    # Always add the @everyone role (excluded from output by the endpoint)
    everyone = MagicMock()
    everyone.id = GUILD_ID
    everyone.name = "@everyone"
    roles.append(everyone)

    # Use None as the explicit sentinel; [] means "no extra roles".
    for rid in ([111, 222] if role_ids is None else role_ids):
        role = MagicMock()
        role.id = rid
        role.name = f"role-{rid}"
        roles.append(role)

    member.roles = roles
    return member


def _make_mock_bot_with_guild(guild: MagicMock | None) -> MagicMock:
    """Build a mock bot whose get_guild() returns the given guild object."""
    bot = MagicMock()
    bot.is_ready.return_value = True
    bot.get_guild = MagicMock(return_value=guild)
    return bot


# ---------------------------------------------------------------------------
# Happy path: member found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_guild_member_found_returns_200_with_member_data(client):
    """When the member exists, respond 200 with is_member=true and full payload."""
    member = _make_mock_member(role_ids=[111, 222])
    guild = MagicMock()
    guild.fetch_member = AsyncMock(return_value=member)

    http_api_module._bot = _make_mock_bot_with_guild(guild)
    try:
        async with client as c:
            response = await c.get(f"/api/members/{USER_ID}", headers=AUTH_HEADER)
    finally:
        http_api_module._bot = None

    assert response.status_code == 200
    data = response.json()
    assert data["is_member"] is True
    assert data["discord_id"] == USER_ID
    assert data["username"] == "siegemaster"
    assert data["display_name"] == "SiegeMaster"
    # @everyone role must be excluded; only real role IDs present
    assert "111" in data["roles"]
    assert "222" in data["roles"]
    assert str(GUILD_ID) not in data["roles"]
    # role_names must parallel roles (name strings, @everyone excluded)
    assert "role-111" in data["role_names"]
    assert "role-222" in data["role_names"]
    assert "@everyone" not in data["role_names"]


@pytest.mark.asyncio
async def test_get_guild_member_roles_exclude_everyone(client):
    """The @everyone role must never appear in the roles list."""
    member = _make_mock_member(role_ids=[])  # no extra roles beyond @everyone
    guild = MagicMock()
    guild.fetch_member = AsyncMock(return_value=member)

    http_api_module._bot = _make_mock_bot_with_guild(guild)
    try:
        async with client as c:
            response = await c.get(f"/api/members/{USER_ID}", headers=AUTH_HEADER)
    finally:
        http_api_module._bot = None

    assert response.status_code == 200
    data = response.json()
    assert data["roles"] == []
    assert data["role_names"] == []


# ---------------------------------------------------------------------------
# Not in guild: Discord 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_guild_member_not_found_returns_200_is_member_false(client):
    """When Discord returns NotFound, respond 200 with is_member=false."""
    guild = MagicMock()
    guild.fetch_member = AsyncMock(side_effect=_discord.NotFound())

    http_api_module._bot = _make_mock_bot_with_guild(guild)
    try:
        async with client as c:
            response = await c.get(f"/api/members/{USER_ID}", headers=AUTH_HEADER)
    finally:
        http_api_module._bot = None

    assert response.status_code == 200
    assert response.json() == {"is_member": False}


# ---------------------------------------------------------------------------
# Discord API error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_guild_member_discord_http_exception_returns_503(client):
    """When Discord raises an unexpected HTTPException, respond 503."""
    guild = MagicMock()
    guild.fetch_member = AsyncMock(side_effect=_discord.HTTPException("rate limited"))

    http_api_module._bot = _make_mock_bot_with_guild(guild)
    try:
        async with client as c:
            response = await c.get(f"/api/members/{USER_ID}", headers=AUTH_HEADER)
    finally:
        http_api_module._bot = None

    assert response.status_code == 503
    assert "Discord API error" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Guild not available (bot not set / get_guild returns None)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_guild_member_guild_none_returns_503(client):
    """When get_guild() returns None (bot not in guild), respond 503."""
    http_api_module._bot = _make_mock_bot_with_guild(None)
    try:
        async with client as c:
            response = await c.get(f"/api/members/{USER_ID}", headers=AUTH_HEADER)
    finally:
        http_api_module._bot = None

    assert response.status_code == 503
    assert response.json()["detail"] == "Guild not available"


@pytest.mark.asyncio
async def test_get_guild_member_bot_none_returns_503(client):
    """When _bot is None entirely, guild lookup yields None and we get 503."""
    http_api_module._bot = None
    async with client as c:
        response = await c.get(f"/api/members/{USER_ID}", headers=AUTH_HEADER)

    assert response.status_code == 503
    assert response.json()["detail"] == "Guild not available"


# ---------------------------------------------------------------------------
# Authentication: missing Bearer token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_guild_member_no_auth_returns_403(client):
    """Requests without a Bearer token must be rejected (403 or 401)."""
    http_api_module._bot = None
    async with client as c:
        response = await c.get(f"/api/members/{USER_ID}")

    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_guild_member_wrong_api_key_returns_401(client):
    """Requests with a wrong Bearer token must be rejected with 401."""
    member = _make_mock_member()
    guild = MagicMock()
    guild.fetch_member = AsyncMock(return_value=member)
    http_api_module._bot = _make_mock_bot_with_guild(guild)
    try:
        async with client as c:
            response = await c.get(
                f"/api/members/{USER_ID}",
                headers={"Authorization": "Bearer wrong-key"},
            )
    finally:
        http_api_module._bot = None

    assert response.status_code == 401
