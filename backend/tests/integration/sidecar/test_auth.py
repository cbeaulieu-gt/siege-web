"""Integration tests for sidecar authentication.

Verifies that all protected endpoints reject missing and wrong Bearer tokens
consistently.  Three different endpoint kinds are exercised so the suite
demonstrates auth is global — not per-endpoint wiring.

Contract source: ``bot/INTERFACE.md`` → Authentication section.

Auth failure modes
------------------
``403 Forbidden`` — ``Authorization`` header entirely absent.
    FastAPI's ``HTTPBearer(auto_error=True)`` (the default) returns 403 with
    ``{"detail": "Not authenticated"}`` when no header is present at all.

``401 Unauthorized`` — header present but token is wrong.
    ``verify_api_key`` runs (because the header is present) and raises 401
    with ``{"detail": "Invalid API key"}`` plus ``WWW-Authenticate: Bearer``.
"""

from __future__ import annotations

import httpx

# ---------------------------------------------------------------------------
# 403 — missing Authorization header
# ---------------------------------------------------------------------------


def test_notify_missing_auth_header_returns_403(bot_url: str) -> None:
    """POST /api/notify without Authorization header returns 403.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.post(
        f"{bot_url}/api/notify",
        json={"username": "anyone", "message": "hi"},
    )
    assert response.status_code == 403
    data = response.json()
    assert "detail" in data
    assert isinstance(data["detail"], str)


def test_post_message_missing_auth_header_returns_403(bot_url: str) -> None:
    """POST /api/post-message without Authorization header returns 403.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.post(
        f"{bot_url}/api/post-message",
        json={"channel_name": "general", "message": "hi"},
    )
    assert response.status_code == 403
    data = response.json()
    assert "detail" in data
    assert isinstance(data["detail"], str)


def test_get_members_missing_auth_header_returns_403(bot_url: str) -> None:
    """GET /api/members without Authorization header returns 403.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.get(f"{bot_url}/api/members")
    assert response.status_code == 403
    data = response.json()
    assert "detail" in data
    assert isinstance(data["detail"], str)


# ---------------------------------------------------------------------------
# 401 — header present but wrong token
# ---------------------------------------------------------------------------


def test_notify_wrong_token_returns_401(bot_url: str) -> None:
    """POST /api/notify with wrong Bearer token returns 401.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.post(
        f"{bot_url}/api/notify",
        json={"username": "anyone", "message": "hi"},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert response.status_code == 401
    data = response.json()
    assert "detail" in data
    assert isinstance(data["detail"], str)
    # WWW-Authenticate header must be present per the interface contract
    assert "WWW-Authenticate" in response.headers


def test_post_message_wrong_token_returns_401(bot_url: str) -> None:
    """POST /api/post-message with wrong Bearer token returns 401.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.post(
        f"{bot_url}/api/post-message",
        json={"channel_name": "general", "message": "hi"},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers


def test_get_members_wrong_token_returns_401(bot_url: str) -> None:
    """GET /api/members with wrong Bearer token returns 401.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.get(
        f"{bot_url}/api/members",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers


def test_get_member_by_id_missing_auth_returns_403(bot_url: str) -> None:
    """GET /api/members/{id} without Authorization header returns 403.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.get(f"{bot_url}/api/members/111000111000111001")
    assert response.status_code == 403


def test_post_image_wrong_token_returns_401(bot_url: str) -> None:
    """POST /api/post-image with wrong Bearer token returns 401.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    # Minimal 1×1 white PNG
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
        b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
        b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    response = httpx.post(
        f"{bot_url}/api/post-image",
        data={"channel_name": "known-channel"},
        files={"file": ("test.png", png_bytes, "image/png")},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers
