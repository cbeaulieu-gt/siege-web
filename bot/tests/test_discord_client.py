"""Unit tests for SiegeBot Discord client methods using mock guild/member objects."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.discord_client import SiegeBot


def _make_bot(guild=None) -> SiegeBot:
    """Create a SiegeBot instance with a pre-loaded guild (bypasses Discord connect)."""
    bot = SiegeBot.__new__(SiegeBot)
    bot.guild_id = 12345
    bot._guild = guild
    return bot


def _make_member(
    name: str,
    display_name: str = None,
    user_id: int = 1,
) -> MagicMock:
    member = MagicMock()
    member.id = user_id
    member.name = name
    member.display_name = display_name or name
    member.create_dm = AsyncMock()
    dm_channel = MagicMock()
    dm_channel.send = AsyncMock()
    member.create_dm.return_value = dm_channel
    return member


def _make_text_channel(name: str) -> MagicMock:
    import discord

    channel = MagicMock(spec=discord.TextChannel)
    channel.name = name
    channel.send = AsyncMock()
    return channel


def _make_guild(members=None, channels=None) -> MagicMock:
    guild = MagicMock()
    guild.members = members or []
    guild.channels = channels or []
    return guild


# ---------------------------------------------------------------------------
# send_dm
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_dm_finds_member_and_sends():
    member = _make_member("alice")
    guild = _make_guild(members=[member])
    bot = _make_bot(guild=guild)

    await bot.send_dm("alice", "Hello!")

    member.create_dm.assert_awaited_once()
    dm_channel = await member.create_dm()
    dm_channel.send.assert_awaited_with("Hello!")


@pytest.mark.asyncio
async def test_send_dm_case_insensitive():
    member = _make_member("Alice")
    guild = _make_guild(members=[member])
    bot = _make_bot(guild=guild)

    await bot.send_dm("alice", "Hi")

    member.create_dm.assert_awaited()


@pytest.mark.asyncio
async def test_send_dm_raises_value_error_if_member_not_found():
    guild = _make_guild(members=[])
    bot = _make_bot(guild=guild)

    with pytest.raises(ValueError, match="ghost"):
        await bot.send_dm("ghost", "Hi")


# ---------------------------------------------------------------------------
# post_message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_message_finds_channel_and_sends():
    channel = _make_text_channel("general")
    guild = _make_guild(channels=[channel])
    bot = _make_bot(guild=guild)

    await bot.post_message("general", "Siege ready!")

    channel.send.assert_awaited_once_with("Siege ready!")


@pytest.mark.asyncio
async def test_post_message_raises_value_error_if_channel_not_found():
    guild = _make_guild(channels=[])
    bot = _make_bot(guild=guild)

    with pytest.raises(ValueError, match="missing-channel"):
        await bot.post_message("missing-channel", "Hi")


# ---------------------------------------------------------------------------
# get_members
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# post_image
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_image_returns_cdn_url():
    channel = _make_text_channel("siege-images")
    # Make channel.send return a message mock with attachments
    msg = MagicMock()
    msg.attachments = [MagicMock(url="https://cdn.discordapp.com/attachments/123/board.png")]
    channel.send = AsyncMock(return_value=msg)
    guild = _make_guild(channels=[channel])
    bot = _make_bot(guild=guild)

    import discord
    with patch("app.discord_client.discord.File") as mock_file:
        url = await bot.post_image("siege-images", b"fake-bytes", "board.png")

    assert url == "https://cdn.discordapp.com/attachments/123/board.png"
    channel.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_members_returns_correct_dict_format():
    members = [
        _make_member("alice", display_name="Alice A", user_id=100),
        _make_member("bob", display_name="Bobby", user_id=200),
    ]
    guild = _make_guild(members=members)
    bot = _make_bot(guild=guild)

    result = await bot.get_members()

    assert len(result) == 2
    alice = next(m for m in result if m["username"] == "alice")
    assert alice["id"] == "100"
    assert alice["display_name"] == "Alice A"
    bob = next(m for m in result if m["username"] == "bob")
    assert bob["id"] == "200"
    assert bob["display_name"] == "Bobby"


