"""Tests for rate limiting on the Discord OAuth2 auth endpoints.

Covers:
- /api/auth/login  429s on the (N+1)th request within the window
- /api/auth/callback 429s on the (N+1)th request within the window
- AUTH_DISABLED=true suppresses all rate limiting
- X-Forwarded-For header is the bucket key (different IPs = independent)

Rate limits are driven by env-tunable settings.  For tests we override them
to a tight "2/minute" value so we only need 3 rapid requests to trigger a
429 — no real-time waiting required.
"""

import secrets

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LOGIN_URL = "/api/auth/login"
CALLBACK_URL = "/api/auth/callback"

# A minimal valid callback request — state validation will reject it, but we
# just need to reach the rate-limiter layer.  We use "wrong-state" so the
# handler redirects to /login?error=invalid_state (302), which is fine for
# rate-limit tests; we only care about the *absence* of a 429 before the
# limit is reached and its *presence* afterwards.
_STATE = secrets.token_hex(32)
CALLBACK_PARAMS = {"code": "auth-code", "state": "mismatch-state"}


async def _get(client: AsyncClient, url: str, headers: dict | None = None) -> int:
    """Send a GET and return the status code."""
    return (await client.get(url, headers=headers or {})).status_code


# ---------------------------------------------------------------------------
# Tests: /api/auth/login rate limit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_rate_limit_triggers_429(monkeypatch):
    """11th rapid request to /api/auth/login returns 429.

    The limit is overridden to "2/minute" via monkeypatch so the test does
    not need to wait for a real one-minute window.
    """
    monkeypatch.setattr("app.config.settings.auth_login_rate_limit", "2/minute")
    monkeypatch.setattr("app.config.settings.auth_disabled", False)
    monkeypatch.setattr("app.config.settings.environment", "development")
    monkeypatch.setattr("app.config.settings.discord_client_id", "test-id")
    monkeypatch.setattr("app.config.settings.discord_redirect_uri", "http://localhost/callback")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # First two requests should succeed (limit is 2/minute)
        for _ in range(2):
            status = await _get(client, LOGIN_URL, headers={"X-Forwarded-For": "1.2.3.4"})
            assert status == 200, f"Expected 200 before limit, got {status}"

        # Third request must be rate-limited
        status = await _get(client, LOGIN_URL, headers={"X-Forwarded-For": "1.2.3.4"})
        assert status == 429, f"Expected 429 after limit exceeded, got {status}"


@pytest.mark.asyncio
async def test_login_rate_limit_independent_per_ip(monkeypatch):
    """Two different X-Forwarded-For IPs have independent rate-limit buckets."""
    monkeypatch.setattr("app.config.settings.auth_login_rate_limit", "2/minute")
    monkeypatch.setattr("app.config.settings.auth_disabled", False)
    monkeypatch.setattr("app.config.settings.environment", "development")
    monkeypatch.setattr("app.config.settings.discord_client_id", "test-id")
    monkeypatch.setattr("app.config.settings.discord_redirect_uri", "http://localhost/callback")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Exhaust the limit for IP A
        for _ in range(2):
            await _get(client, LOGIN_URL, headers={"X-Forwarded-For": "10.0.0.1"})
        status_a = await _get(client, LOGIN_URL, headers={"X-Forwarded-For": "10.0.0.1"})
        assert status_a == 429, "IP A should be rate-limited"

        # IP B is a fresh bucket — first request should succeed
        status_b = await _get(client, LOGIN_URL, headers={"X-Forwarded-For": "10.0.0.2"})
        assert status_b == 200, f"IP B should not be rate-limited, got {status_b}"


# ---------------------------------------------------------------------------
# Tests: /api/auth/callback rate limit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_callback_rate_limit_triggers_429(monkeypatch):
    """6th rapid request to /api/auth/callback returns 429.

    Limit overridden to "2/minute" for speed.  The handler returns 302
    (invalid_state redirect) for valid-rate requests; we only care that
    the (limit+1)th response is 429.
    """
    monkeypatch.setattr("app.config.settings.auth_callback_rate_limit", "2/minute")
    monkeypatch.setattr("app.config.settings.auth_disabled", False)
    monkeypatch.setattr("app.config.settings.environment", "development")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        client.cookies.set("oauth_state", _STATE)

        # First two requests hit the handler (returns 302 invalid_state)
        for _ in range(2):
            resp = await client.get(
                CALLBACK_URL,
                params=CALLBACK_PARAMS,
                headers={"X-Forwarded-For": "5.5.5.5"},
            )
            assert (
                resp.status_code == 302
            ), f"Expected 302 before rate limit, got {resp.status_code}"

        # Third request must be rate-limited
        resp = await client.get(
            CALLBACK_URL,
            params=CALLBACK_PARAMS,
            headers={"X-Forwarded-For": "5.5.5.5"},
        )
        assert resp.status_code == 429, f"Expected 429 after limit exceeded, got {resp.status_code}"


# ---------------------------------------------------------------------------
# Tests: AUTH_DISABLED bypass
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_no_429_when_auth_disabled(monkeypatch):
    """When AUTH_DISABLED=true, 50 rapid requests to /login never return 429."""
    monkeypatch.setattr("app.config.settings.auth_login_rate_limit", "2/minute")
    monkeypatch.setattr("app.config.settings.auth_disabled", True)
    monkeypatch.setattr("app.config.settings.environment", "development")
    monkeypatch.setattr("app.config.settings.discord_client_id", "test-id")
    monkeypatch.setattr("app.config.settings.discord_redirect_uri", "http://localhost/callback")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for i in range(50):
            status = await _get(client, LOGIN_URL, headers={"X-Forwarded-For": "9.9.9.9"})
            assert status != 429, f"Got unexpected 429 on request {i + 1}"


@pytest.mark.asyncio
async def test_callback_no_429_when_auth_disabled(monkeypatch):
    """When AUTH_DISABLED=true, 50 rapid requests to /callback never return 429."""
    monkeypatch.setattr("app.config.settings.auth_callback_rate_limit", "2/minute")
    monkeypatch.setattr("app.config.settings.auth_disabled", True)
    monkeypatch.setattr("app.config.settings.environment", "development")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        client.cookies.set("oauth_state", _STATE)
        for i in range(50):
            resp = await client.get(
                CALLBACK_URL,
                params=CALLBACK_PARAMS,
                headers={"X-Forwarded-For": "9.9.9.9"},
            )
            assert resp.status_code != 429, f"Got unexpected 429 on request {i + 1}"
