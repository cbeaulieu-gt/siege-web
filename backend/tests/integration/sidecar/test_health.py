"""Integration tests for GET /api/health.

Exercises the live bot sidecar (started by the ``bot_url`` fixture in
``conftest.py``) over a real TCP socket.

Contract source: ``bot/INTERFACE.md`` → ``GET /api/health`` section.
"""

from __future__ import annotations

import httpx


def test_health_returns_200(bot_url: str) -> None:
    """GET /api/health responds 200 with the correct status/body shape.

    Validates both status code and body simultaneously — per the acceptance
    criteria that every success-path test checks both.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.get(f"{bot_url}/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert isinstance(data["bot_connected"], bool)


def test_health_bot_connected_is_true_in_fake_mode(bot_url: str) -> None:
    """GET /api/health reports ``bot_connected: true`` in fake mode.

    ``FakeDiscordClient.is_ready()`` always returns ``True``, so the
    sidecar must report connected after startup.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.get(f"{bot_url}/api/health")
    assert response.status_code == 200
    assert response.json()["bot_connected"] is True


def test_health_no_auth_required(bot_url: str) -> None:
    """GET /api/health succeeds without an Authorization header.

    This is a public endpoint per the interface contract.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.get(f"{bot_url}/api/health")
    assert response.status_code == 200


def test_health_response_shape_has_exactly_two_keys(bot_url: str) -> None:
    """GET /api/health body contains exactly ``status`` and ``bot_connected``.

    Catches accidental key additions or renames that would break the
    documented shape.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.get(f"{bot_url}/api/health")
    assert response.status_code == 200
    assert set(response.json().keys()) == {"status", "bot_connected"}
