"""Tests for bot HTTP client graceful degradation."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.bot_client import BotClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ok_response(status_code=200, json_data=None):
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.raise_for_status = MagicMock()
    if json_data is not None:
        response.json = MagicMock(return_value=json_data)
    return response


def _async_client_that_raises(exc):
    """Return a context-manager-compatible mock AsyncClient that raises on any request."""
    client_mock = AsyncMock()
    client_mock.post = AsyncMock(side_effect=exc)
    client_mock.get = AsyncMock(side_effect=exc)
    client_mock.__aenter__ = AsyncMock(return_value=client_mock)
    client_mock.__aexit__ = AsyncMock(return_value=False)
    return client_mock


def _async_client_that_returns(response):
    """Return a context-manager-compatible mock AsyncClient that returns a response."""
    client_mock = AsyncMock()
    client_mock.post = AsyncMock(return_value=response)
    client_mock.get = AsyncMock(return_value=response)
    client_mock.__aenter__ = AsyncMock(return_value=client_mock)
    client_mock.__aexit__ = AsyncMock(return_value=False)
    return client_mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_returns_false_on_http_error():
    """notify() returns False when the bot HTTP call raises an HTTPError."""
    client_mock = _async_client_that_raises(httpx.ConnectError("unreachable"))
    with patch.object(BotClient, "_make_client", return_value=client_mock):
        result = await BotClient().notify("alice", "hello")
    assert result is False


@pytest.mark.asyncio
async def test_post_message_returns_false_on_http_error():
    """post_message() returns False when the bot HTTP call raises an HTTPError."""
    client_mock = _async_client_that_raises(httpx.ConnectError("unreachable"))
    with patch.object(BotClient, "_make_client", return_value=client_mock):
        result = await BotClient().post_message("general", "siege ready")
    assert result is False


@pytest.mark.asyncio
async def test_post_image_returns_false_on_http_error():
    """post_image() returns False when the bot HTTP call raises an HTTPError."""
    client_mock = _async_client_that_raises(httpx.ConnectError("unreachable"))
    with patch.object(BotClient, "_make_client", return_value=client_mock):
        result = await BotClient().post_image("siege-channel", b"\x89PNG", "board.png")
    assert result is False


@pytest.mark.asyncio
async def test_get_members_returns_empty_on_http_error():
    """get_members() returns [] when the bot HTTP call raises an HTTPError."""
    client_mock = _async_client_that_raises(httpx.ConnectError("unreachable"))
    with patch.object(BotClient, "_make_client", return_value=client_mock):
        result = await BotClient().get_members()
    assert result == []


@pytest.mark.asyncio
async def test_notify_returns_true_on_success():
    """notify() returns True when the bot returns a 200 response."""
    response = _make_ok_response(status_code=200)
    client_mock = _async_client_that_returns(response)
    with patch.object(BotClient, "_make_client", return_value=client_mock):
        result = await BotClient().notify("alice", "siege activated")
    assert result is True
