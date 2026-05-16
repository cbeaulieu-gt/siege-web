"""Integration tests for POST /api/notify.

Exercises the live bot sidecar (started by the ``bot_url`` fixture in
``conftest.py``) over a real TCP socket.

Contract source: ``bot/INTERFACE.md`` → ``POST /api/notify`` section.

Magic trigger values (from ``bot/app/fake_discord.py``)
--------------------------------------------------------
  ``"known-user"``      → 200 success (known member)
  ``"unknown-ghost"``   → 404 (member not in guild cache)
  ``"dm-forbidden"``    → 403 (DMs blocked)
  ``"dm-http4xx"``      → 502 (Discord 4xx error, rate-limited)
  ``"dm-http5xx"``      → 503 (Discord 5xx error)
  ``"dm-timeout"``      → 503 (asyncio.TimeoutError)
"""

from __future__ import annotations

import httpx

from .conftest import AUTH_HEADERS


def test_notify_known_user_returns_200_sent(bot_url: str) -> None:
    """POST /api/notify with a known username returns 200 ``{"status": "sent"}``.

    Validates both status code and body shape (required by acceptance criteria).

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.post(
        f"{bot_url}/api/notify",
        json={"username": "known-user", "message": "Hello!"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    assert response.json() == {"status": "sent"}


def test_notify_unknown_user_returns_404_with_detail(bot_url: str) -> None:
    """POST /api/notify with an unknown username returns 404 with ``detail``.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.post(
        f"{bot_url}/api/notify",
        json={"username": "unknown-ghost", "message": "Hi"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert isinstance(data["detail"], str)


def test_notify_missing_username_returns_422(bot_url: str) -> None:
    """POST /api/notify with missing ``username`` field returns 422.

    The 422 body must be the framework-validation list shape, not the
    handler string shape.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.post(
        f"{bot_url}/api/notify",
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


def test_notify_missing_message_returns_422(bot_url: str) -> None:
    """POST /api/notify with missing ``message`` field returns 422.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.post(
        f"{bot_url}/api/notify",
        json={"username": "known-user"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 422
    data = response.json()
    assert isinstance(data["detail"], list)


def test_notify_dms_blocked_returns_403_with_permission_denied(bot_url: str) -> None:
    """POST /api/notify when DMs are blocked returns 403.

    ``FakeDiscordClient.send_dm("dm-forbidden", ...)`` raises
    ``discord.Forbidden``, which the global exception handler translates
    to 403.  Body must contain ``"Discord permission denied"`` per the
    interface contract.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.post(
        f"{bot_url}/api/notify",
        json={"username": "dm-forbidden", "message": "Hi"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 403
    data = response.json()
    assert "detail" in data
    assert "permission denied" in data["detail"].lower()


def test_notify_discord_4xx_returns_502(bot_url: str) -> None:
    """POST /api/notify on Discord 4xx (rate-limit) returns 502.

    ``FakeDiscordClient.send_dm("dm-http4xx", ...)`` raises
    ``discord.HTTPException(status=429)``.  The global handler translates
    this to 502 with ``{"detail": "Upstream Discord error"}`` — the upstream
    status code is logged server-side and not exposed to callers.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.post(
        f"{bot_url}/api/notify",
        json={"username": "dm-http4xx", "message": "Hi"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 502
    data = response.json()
    assert "detail" in data
    assert data["detail"] == "Upstream Discord error"
    assert "429" not in data["detail"]


def test_notify_discord_5xx_returns_503_unavailable(bot_url: str) -> None:
    """POST /api/notify on Discord 5xx returns 503.

    ``FakeDiscordClient.send_dm("dm-http5xx", ...)`` raises
    ``discord.HTTPException(status=500)``.  The global handler translates
    this to 503 with ``{"detail": "Discord temporarily unavailable"}``.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.post(
        f"{bot_url}/api/notify",
        json={"username": "dm-http5xx", "message": "Hi"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 503
    data = response.json()
    assert "detail" in data
    assert "unavailable" in data["detail"].lower()


def test_notify_timeout_returns_503_unavailable(bot_url: str) -> None:
    """POST /api/notify on asyncio.TimeoutError returns 503.

    ``FakeDiscordClient.send_dm("dm-timeout", ...)`` raises
    ``asyncio.TimeoutError``.  The global handler translates this to 503.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.post(
        f"{bot_url}/api/notify",
        json={"username": "dm-timeout", "message": "Hi"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 503
    data = response.json()
    assert "detail" in data
    assert "unavailable" in data["detail"].lower()
