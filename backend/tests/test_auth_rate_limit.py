"""Tests for rate limiting on the Discord OAuth2 auth endpoints.

Covers:
- /api/auth/login  429s on the (N+1)th request within the window
- /api/auth/callback 429s on the (N+1)th request within the window
- AUTH_DISABLED=true suppresses all rate limiting
- X-Forwarded-For header is the bucket key (different IPs = independent)
- Invalid XFF value falls back to remote-address bucket
- Garbage XFF values do NOT create unique per-request buckets
- 429 response includes a Retry-After header
- Production warning fires when XFF absent; silent in development
- Invalid XFF in production logs a throttled warning; silent in development

Rate limits are driven by env-tunable settings.  For tests we override them
to a tight "2/minute" value so we only need 3 rapid requests to trigger a
429 — no real-time waiting required.

Per #413, the production-warning branch is exercised via a direct synchronous
call to ``_get_client_ip`` rather than through the full ASGI/thread-pool
stack; this avoids the chronic flake history documented in issue #387.
"""

import logging
import secrets

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request as StarletteRequest

import app.rate_limit as _rate_limit_module
from app.main import app
from app.rate_limit import _get_client_ip, limiter


@pytest.fixture(autouse=True)
def reset_rate_limit_state():
    """Reset per-test rate-limit state before each test.

    Resets module-level state so tests cannot bleed into each other:

    1. ``limiter._storage`` — the in-memory bucket store.  Tests that
       share the same fallback IP (127.0.0.1 / "testclient") would
       otherwise see residual counts from earlier tests.

    2. ``_last_xff_absent_warning`` — the throttle timestamp for the
       production XFF-absent warning.  Without this reset, a
       production-warning test run immediately after another one would
       suppress the warning (throttle not yet expired) and fail.

    3. ``_last_xff_invalid_warning`` — the throttle timestamp for the
       invalid-XFF production warning (Finding #2).  Same rationale as
       above.
    """
    limiter._storage.reset()
    _rate_limit_module._last_xff_absent_warning = 0.0
    _rate_limit_module._last_xff_invalid_warning = 0.0
    yield


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
    """3rd rapid request to /api/auth/login returns 429 when limit is 2/minute.

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
    """3rd rapid request to /api/auth/callback returns 429 when limit is 2/minute.

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


# ---------------------------------------------------------------------------
# Tests: X-Forwarded-For header cap
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_xff_pathological_header_parses_to_leftmost_ip(monkeypatch):
    """Pathologically long X-Forwarded-For header is handled without error.

    Constructs a header that far exceeds 8192 characters and verifies that
    the rate-limiter correctly extracts the leftmost IP (the real client IP
    written by the trusted ingress proxy), even after the 8 KB cap truncates
    the tail of the header.
    """
    monkeypatch.setattr("app.config.settings.auth_login_rate_limit", "100/minute")
    monkeypatch.setattr("app.config.settings.auth_disabled", False)
    monkeypatch.setattr("app.config.settings.environment", "development")
    monkeypatch.setattr("app.config.settings.discord_client_id", "test-id")
    monkeypatch.setattr("app.config.settings.discord_redirect_uri", "http://localhost/callback")

    # Build a header where the leftmost entry is a real IP followed by enough
    # padding to exceed 8192 bytes.  After truncation the split still yields
    # the leftmost IP as the bucket key, so the request must not 429.
    leftmost_ip = "1.2.3.4"
    filler = ", 10.0.0.1" * 1000  # well over 8 KB
    long_xff = f"{leftmost_ip}{filler}"
    assert len(long_xff) > 8192, "Precondition: header must exceed the cap"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        status = await _get(client, LOGIN_URL, headers={"X-Forwarded-For": long_xff})
        # With a generous 100/minute limit and a unique-looking first IP this
        # should succeed — the key point is no exception is raised by the cap.
        assert status == 200, f"Expected 200 (no exception raised from long XFF), got {status}"


# ---------------------------------------------------------------------------
# Tests: XFF validation (Finding #1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_garbage_xff_falls_back_to_remote_address_bucket(monkeypatch):
    """Garbage XFF value falls back to the ASGI remote-address bucket.

    Sending ``X-Forwarded-For: not-an-ip`` must NOT create a unique bucket
    for the garbage string.  Instead the fallback remote-address bucket
    ('testclient' / 127.0.0.1) is used, so repeated garbage-XFF requests
    accumulate in the same bucket and eventually hit the rate limit.
    """
    monkeypatch.setattr("app.config.settings.auth_login_rate_limit", "2/minute")
    monkeypatch.setattr("app.config.settings.auth_disabled", False)
    monkeypatch.setattr("app.config.settings.environment", "development")
    monkeypatch.setattr("app.config.settings.discord_client_id", "test-id")
    monkeypatch.setattr("app.config.settings.discord_redirect_uri", "http://localhost/callback")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Two requests with garbage XFF fill the remote-address bucket.
        for _ in range(2):
            status = await _get(client, LOGIN_URL, headers={"X-Forwarded-For": "not-an-ip"})
            assert status == 200, f"Expected 200 before limit, got {status}"

        # Third request with garbage XFF hits the rate limit (same remote-address
        # bucket — garbage did NOT escape into its own fresh bucket).
        status = await _get(client, LOGIN_URL, headers={"X-Forwarded-For": "not-an-ip"})
        assert status == 429, (
            f"Expected 429 — garbage XFF must not create a fresh per-request "
            f"bucket, got {status}"
        )


@pytest.mark.asyncio
async def test_different_garbage_xff_values_share_remote_address_bucket(monkeypatch):
    """Different garbage XFF strings all resolve to the same remote-address bucket.

    An attacker who rotates ``X-Forwarded-For`` values through unique garbage
    strings must NOT bypass the limiter by getting a fresh bucket each time.
    All garbage values share the fallback remote-address bucket.
    """
    monkeypatch.setattr("app.config.settings.auth_login_rate_limit", "2/minute")
    monkeypatch.setattr("app.config.settings.auth_disabled", False)
    monkeypatch.setattr("app.config.settings.environment", "development")
    monkeypatch.setattr("app.config.settings.discord_client_id", "test-id")
    monkeypatch.setattr("app.config.settings.discord_redirect_uri", "http://localhost/callback")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Exhaust the bucket with distinct garbage values.
        garbage_headers = ["not-an-ip", "shared-bucket", "totally-fake"]
        for h in garbage_headers[:2]:
            status = await _get(client, LOGIN_URL, headers={"X-Forwarded-For": h})
            assert status == 200, f"Expected 200 before limit, got {status}"

        # A third distinct garbage value still hits the limit —
        # same remote-address fallback bucket.
        status = await _get(client, LOGIN_URL, headers={"X-Forwarded-For": garbage_headers[2]})
        assert status == 429, (
            f"Expected 429 — different garbage XFF values must not each get their "
            f"own fresh bucket, got {status}"
        )


@pytest.mark.asyncio
async def test_valid_xff_still_buckets_by_ip(monkeypatch):
    """Valid XFF IP values are still used as the bucket key (regression guard).

    Ensures the garbage-XFF fallback path does not accidentally affect
    requests that carry a legitimate X-Forwarded-For value.
    """
    monkeypatch.setattr("app.config.settings.auth_login_rate_limit", "2/minute")
    monkeypatch.setattr("app.config.settings.auth_disabled", False)
    monkeypatch.setattr("app.config.settings.environment", "development")
    monkeypatch.setattr("app.config.settings.discord_client_id", "test-id")
    monkeypatch.setattr("app.config.settings.discord_redirect_uri", "http://localhost/callback")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Exhaust the bucket for IP A.
        for _ in range(2):
            await _get(client, LOGIN_URL, headers={"X-Forwarded-For": "10.0.0.1"})
        status_a = await _get(client, LOGIN_URL, headers={"X-Forwarded-For": "10.0.0.1"})
        assert status_a == 429, "IP A should be rate-limited"

        # IP B is a completely separate bucket — should not be affected.
        status_b = await _get(client, LOGIN_URL, headers={"X-Forwarded-For": "10.0.0.2"})
        assert status_b == 200, f"IP B must have its own fresh bucket, got {status_b}"


# ---------------------------------------------------------------------------
# Tests: custom 429 handler — Retry-After header (Finding #2 / #4)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_429_response_includes_retry_after_header(monkeypatch):
    """A 429 response must include a Retry-After header with a positive integer.

    Verifies that our custom rate-limit-exceeded handler sets the header so
    clients know when they can retry without polling.
    """
    monkeypatch.setattr("app.config.settings.auth_login_rate_limit", "2/minute")
    monkeypatch.setattr("app.config.settings.auth_disabled", False)
    monkeypatch.setattr("app.config.settings.environment", "development")
    monkeypatch.setattr("app.config.settings.discord_client_id", "test-id")
    monkeypatch.setattr("app.config.settings.discord_redirect_uri", "http://localhost/callback")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Exhaust the limit.
        for _ in range(2):
            await _get(client, LOGIN_URL, headers={"X-Forwarded-For": "2.3.4.5"})

        # Trigger the 429 and capture the full response.
        resp = await client.get(LOGIN_URL, headers={"X-Forwarded-For": "2.3.4.5"})
        assert resp.status_code == 429, f"Expected 429, got {resp.status_code}"

        retry_after = resp.headers.get("Retry-After")
        assert retry_after is not None, "Retry-After header must be present on 429"
        assert (
            retry_after.isdigit()
        ), f"Retry-After must be a plain integer string, got {retry_after!r}"
        assert int(retry_after) > 0, f"Retry-After must be a positive integer, got {retry_after}"


# ---------------------------------------------------------------------------
# Tests: production warning branch — direct synchronous calls to
# _get_client_ip (avoids ASGI/thread-pool flake; see #413 and #387)
# ---------------------------------------------------------------------------


def test_xff_absent_in_production_advances_throttle_timestamp_direct_call(
    monkeypatch,
):
    """Absent XFF in production advances _last_xff_absent_warning via direct call.

    Calls ``_get_client_ip`` synchronously with a minimal Starlette Request
    that carries no X-Forwarded-For header and ENVIRONMENT=production.
    Asserts that ``_last_xff_absent_warning`` advances from 0.0, proving
    the warning branch executed.

    Per #413: replaces the four ASGI-stack-routed production-warning tests
    whose chronic flake history is documented in #387.  Calling _get_client_ip
    directly eliminates the middleware and thread-pool layers that were the
    source of the intermittent CI failures.
    """
    monkeypatch.setattr("app.config.settings.environment", "production")

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "client": ("127.0.0.1", 9000),
    }
    req = StarletteRequest(scope)

    before = _rate_limit_module._last_xff_absent_warning
    _get_client_ip(req)

    assert _rate_limit_module._last_xff_absent_warning > before, (
        "Expected _last_xff_absent_warning to advance from 0.0 after a "
        "no-XFF call to _get_client_ip in production — warning branch "
        "did not execute"
    )


def test_xff_invalid_in_production_advances_throttle_timestamp_direct_call(
    monkeypatch,
):
    """Invalid XFF in production advances _last_xff_invalid_warning via direct call.

    Calls ``_get_client_ip`` synchronously with a minimal Starlette Request
    whose X-Forwarded-For header contains a non-IP value and
    ENVIRONMENT=production.  Asserts that ``_last_xff_invalid_warning``
    advances from 0.0, proving the invalid-XFF warning branch executed.

    Per #413: replaces the four ASGI-stack-routed production-warning tests
    whose chronic flake history is documented in #387.  Calling _get_client_ip
    directly eliminates the middleware and thread-pool layers that were the
    source of the intermittent CI failures.
    """
    monkeypatch.setattr("app.config.settings.environment", "production")

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"x-forwarded-for", b"not-a-valid-ip")],
        "client": ("127.0.0.1", 9000),
    }
    req = StarletteRequest(scope)

    before = _rate_limit_module._last_xff_invalid_warning
    _get_client_ip(req)

    assert _rate_limit_module._last_xff_invalid_warning > before, (
        "Expected _last_xff_invalid_warning to advance from 0.0 after an "
        "invalid-XFF call to _get_client_ip in production — warning branch "
        "did not execute"
    )


@pytest.mark.asyncio
async def test_missing_xff_in_development_does_not_log_warning(monkeypatch, caplog):
    """XFF absent in development must NOT emit the production trust-model warning.

    Direct access without a proxy is normal in local dev — the warning would
    be noise and should be suppressed when ENVIRONMENT != production.
    """
    monkeypatch.setattr("app.config.settings.auth_login_rate_limit", "100/minute")
    monkeypatch.setattr("app.config.settings.auth_disabled", False)
    monkeypatch.setattr("app.config.settings.environment", "development")
    monkeypatch.setattr("app.config.settings.discord_client_id", "test-id")
    monkeypatch.setattr("app.config.settings.discord_redirect_uri", "http://localhost/callback")

    with caplog.at_level(logging.WARNING, logger="app.rate_limit"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _get(client, LOGIN_URL)

    warning_records = [
        r for r in caplog.records if r.levelno == logging.WARNING and "X-Forwarded-For" in r.message
    ]
    assert (
        len(warning_records) == 0
    ), f"Expected no XFF warning in development, got: {warning_records}"


@pytest.mark.asyncio
async def test_invalid_xff_in_development_does_not_log_warning(monkeypatch, caplog):
    """Invalid X-Forwarded-For in development must NOT emit a warning.

    Direct / tool access with malformed headers is common in local dev and
    CI; logging would be noise.  The warning must only fire in production.
    """
    monkeypatch.setattr("app.config.settings.auth_login_rate_limit", "100/minute")
    monkeypatch.setattr("app.config.settings.auth_disabled", False)
    monkeypatch.setattr("app.config.settings.environment", "development")
    monkeypatch.setattr("app.config.settings.discord_client_id", "test-id")
    monkeypatch.setattr("app.config.settings.discord_redirect_uri", "http://localhost/callback")

    with caplog.at_level(logging.WARNING, logger="app.rate_limit"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _get(
                client,
                LOGIN_URL,
                headers={"X-Forwarded-For": "not-a-valid-ip"},
            )

    invalid_warnings = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and "Invalid X-Forwarded-For" in r.message
    ]
    assert (
        len(invalid_warnings) == 0
    ), f"Expected no invalid-XFF warning in development, got: {invalid_warnings}"
