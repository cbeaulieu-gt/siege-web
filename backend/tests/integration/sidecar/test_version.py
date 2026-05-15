"""Integration tests for GET /api/version.

Exercises the live bot sidecar (started by the ``bot_url`` fixture in
``conftest.py``) over a real TCP socket.

Contract source: ``bot/INTERFACE.md`` → ``GET /api/version`` section.
"""

from __future__ import annotations

import httpx


def test_version_returns_200_with_version_key(bot_url: str) -> None:
    """GET /api/version responds 200 with a non-empty ``version`` string.

    Validates both the status code and the response body shape as required
    by the acceptance criteria: every success-path assertion MUST check
    status AND body.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.get(f"{bot_url}/api/version")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert isinstance(data["version"], str)
    assert len(data["version"]) > 0


def test_version_no_auth_required(bot_url: str) -> None:
    """GET /api/version succeeds without an Authorization header.

    This is a public endpoint per the interface contract.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    # Deliberately omit auth header
    response = httpx.get(f"{bot_url}/api/version")
    assert response.status_code == 200


def test_version_response_has_exactly_one_key(bot_url: str) -> None:
    """GET /api/version body contains exactly the ``version`` key.

    Catches accidental key additions or renames that would break the
    documented shape.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.get(f"{bot_url}/api/version")
    assert response.status_code == 200
    assert set(response.json().keys()) == {"version"}
