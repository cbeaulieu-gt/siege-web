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
async def test_post_image_returns_none_on_http_error():
    """post_image() returns None when the bot HTTP call raises an HTTPError."""
    client_mock = _async_client_that_raises(httpx.ConnectError("unreachable"))
    with patch.object(BotClient, "_make_client", return_value=client_mock):
        result = await BotClient().post_image("siege-channel", b"\x89PNG", "board.png")
    assert result is None


@pytest.mark.asyncio
async def test_post_image_sends_channel_name_in_form_body():
    """post_image() must send channel_name as a multipart form field, not query param."""
    response = _make_ok_response(
        status_code=200, json_data={"url": "https://cdn.example.com/img.png"}
    )
    # Use a real-enough mock to capture the call kwargs
    client_mock = AsyncMock()
    client_mock.post = AsyncMock(return_value=response)
    client_mock.__aenter__ = AsyncMock(return_value=client_mock)
    client_mock.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.bot_client.httpx.AsyncClient", return_value=client_mock):
        result = await BotClient().post_image("siege-images", b"\x89PNG", "board.png")

    assert result == "https://cdn.example.com/img.png"
    call_kwargs = client_mock.post.call_args
    # channel_name must be in `data`, not in the URL as a query parameter
    assert (
        "data" in call_kwargs.kwargs
    ), "channel_name must be sent via form data= kwarg, not in URL"
    assert call_kwargs.kwargs["data"] == {"channel_name": "siege-images"}
    # URL must not contain a query string with channel_name
    url_arg = call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs.get("url", "")
    assert (
        "channel_name" not in url_arg
    ), f"channel_name must not appear in URL, found in: {url_arg!r}"


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


# ---------------------------------------------------------------------------
# get_member tests
# ---------------------------------------------------------------------------


_FULL_MEMBER_DATA = {
    "is_member": True,
    "discord_id": "123456789",
    "username": "alice",
    "display_name": "Alice",
    "roles": ["111", "222"],
    "role_names": ["Raider", "Officer"],
}

_NOT_MEMBER_DATA = {
    "is_member": False,
    "discord_id": None,
    "username": None,
    "display_name": None,
    "roles": None,
    "role_names": None,
}


@pytest.mark.asyncio
async def test_get_member_returns_member_dict():
    """get_member() returns the full member dict when sidecar responds 200."""
    response = _make_ok_response(status_code=200, json_data=_FULL_MEMBER_DATA)
    client_mock = _async_client_that_returns(response)
    with patch.object(BotClient, "_make_client", return_value=client_mock):
        result = await BotClient().get_member("123456789")
    assert result == _FULL_MEMBER_DATA


@pytest.mark.asyncio
async def test_get_member_returns_not_member_full_shape():
    """get_member() returns the full key set with None values for non-members."""
    response = _make_ok_response(status_code=200, json_data=_NOT_MEMBER_DATA)
    client_mock = _async_client_that_returns(response)
    with patch.object(BotClient, "_make_client", return_value=client_mock):
        result = await BotClient().get_member("999999999")
    assert result == _NOT_MEMBER_DATA
    assert result["is_member"] is False
    assert result["discord_id"] is None


@pytest.mark.asyncio
async def test_get_member_raises_assertion_on_missing_is_member_key():
    """get_member() raises AssertionError when sidecar omits 'is_member'."""
    malformed = {"username": "alice"}
    response = _make_ok_response(status_code=200, json_data=malformed)
    client_mock = _async_client_that_returns(response)
    with patch.object(BotClient, "_make_client", return_value=client_mock):
        with pytest.raises(AssertionError, match="missing 'is_member' discriminator"):
            await BotClient().get_member("123456789")


@pytest.mark.asyncio
async def test_get_member_raises_assertion_on_non_bool_is_member():
    """get_member() raises AssertionError when 'is_member' is not a bool."""
    malformed = {
        "is_member": "yes",
        "discord_id": "123",
        "username": "alice",
        "display_name": "Alice",
        "roles": [],
        "role_names": [],
    }
    response = _make_ok_response(status_code=200, json_data=malformed)
    client_mock = _async_client_that_returns(response)
    with patch.object(BotClient, "_make_client", return_value=client_mock):
        with pytest.raises(AssertionError, match="is not bool"):
            await BotClient().get_member("123456789")


@pytest.mark.asyncio
async def test_get_member_raises_assertion_on_missing_required_key():
    """get_member() raises AssertionError when a required key is absent."""
    # Missing 'roles' and 'role_names'
    malformed = {
        "is_member": True,
        "discord_id": "123",
        "username": "alice",
        "display_name": "Alice",
        # roles and role_names intentionally absent
    }
    response = _make_ok_response(status_code=200, json_data=malformed)
    client_mock = _async_client_that_returns(response)
    with patch.object(BotClient, "_make_client", return_value=client_mock):
        with pytest.raises(AssertionError, match="missing key"):
            await BotClient().get_member("123456789")


@pytest.mark.asyncio
async def test_get_member_raises_on_connection_error():
    """get_member() raises httpx.HTTPError when the sidecar is unreachable."""
    client_mock = _async_client_that_raises(httpx.ConnectError("unreachable"))
    with patch.object(BotClient, "_make_client", return_value=client_mock):
        with pytest.raises(httpx.HTTPError):
            await BotClient().get_member("123456789")


@pytest.mark.asyncio
async def test_get_member_raises_on_503():
    """get_member() raises httpx.HTTPStatusError when sidecar returns 503."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = 503
    response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "503 Service Unavailable",
            request=MagicMock(),
            response=response,
        )
    )
    client_mock = _async_client_that_returns(response)
    with patch.object(BotClient, "_make_client", return_value=client_mock):
        with pytest.raises(httpx.HTTPStatusError):
            await BotClient().get_member("123456789")
