"""Integration tests for POST /api/post-message.

Exercises the live bot sidecar (started by the ``bot_url`` fixture in
``conftest.py``) over a real TCP socket.

Contract source: ``bot/INTERFACE.md`` → ``POST /api/post-message`` section.

Magic trigger values (from ``bot/app/fake_discord.py``)
--------------------------------------------------------
  ``"known-channel"``    → 200 success
  ``"unknown-chan"``     → 404 (channel not found in guild)
  ``"chan-forbidden"``   → 403 (bot lacks send permission)
  ``"chan-http4xx"``     → 502 (Discord 4xx error, rate-limited)
  ``"chan-http5xx"``     → 503 (Discord 5xx error)
  ``"chan-timeout"``     → 503 (asyncio.TimeoutError)
"""

from __future__ import annotations

import httpx

from .conftest import AUTH_HEADERS


def test_post_message_known_channel_returns_200_sent(bot_url: str) -> None:
    """POST /api/post-message to a known channel returns 200 ``{"status": "sent"}``.

    Validates both status code and body shape per acceptance criteria.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.post(
        f"{bot_url}/api/post-message",
        json={"channel_name": "known-channel", "message": "Siege ready!"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    assert response.json() == {"status": "sent"}


def test_post_message_unknown_channel_returns_404_with_detail(bot_url: str) -> None:
    """POST /api/post-message with an unknown channel returns 404 with ``detail``.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.post(
        f"{bot_url}/api/post-message",
        json={"channel_name": "unknown-chan", "message": "Hi"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert isinstance(data["detail"], str)


def test_post_message_missing_channel_name_returns_422(bot_url: str) -> None:
    """POST /api/post-message with missing ``channel_name`` field returns 422.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.post(
        f"{bot_url}/api/post-message",
        json={"message": "Hi"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 422
    data = response.json()
    assert isinstance(data["detail"], list)
    assert len(data["detail"]) > 0
    item = data["detail"][0]
    assert "loc" in item
    assert "msg" in item
    assert "type" in item


def test_post_message_missing_message_returns_422(bot_url: str) -> None:
    """POST /api/post-message with missing ``message`` field returns 422.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.post(
        f"{bot_url}/api/post-message",
        json={"channel_name": "known-channel"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 422
    data = response.json()
    assert isinstance(data["detail"], list)


def test_post_message_discord_forbidden_returns_403(bot_url: str) -> None:
    """POST /api/post-message when bot lacks send permission returns 403.

    ``FakeDiscordClient.post_message("chan-forbidden", ...)`` raises
    ``discord.Forbidden``, translated to 403 by the global exception handler.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.post(
        f"{bot_url}/api/post-message",
        json={"channel_name": "chan-forbidden", "message": "Hi"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 403
    data = response.json()
    assert "detail" in data
    assert "permission denied" in data["detail"].lower()


def test_post_message_discord_4xx_returns_502(bot_url: str) -> None:
    """POST /api/post-message on Discord 4xx returns 502.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.post(
        f"{bot_url}/api/post-message",
        json={"channel_name": "chan-http4xx", "message": "Hi"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 502
    data = response.json()
    assert "detail" in data
    assert "429" in data["detail"]


def test_post_message_discord_5xx_returns_503(bot_url: str) -> None:
    """POST /api/post-message on Discord 5xx returns 503.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.post(
        f"{bot_url}/api/post-message",
        json={"channel_name": "chan-http5xx", "message": "Hi"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 503
    data = response.json()
    assert "unavailable" in data["detail"].lower()


def test_post_message_timeout_returns_503(bot_url: str) -> None:
    """POST /api/post-message on asyncio.TimeoutError returns 503.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.post(
        f"{bot_url}/api/post-message",
        json={"channel_name": "chan-timeout", "message": "Hi"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 503
    data = response.json()
    assert "unavailable" in data["detail"].lower()
