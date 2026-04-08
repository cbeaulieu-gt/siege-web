"""Tests for Discord OAuth2 auth middleware and endpoints."""

import secrets
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.main import app
from app.models.enums import MemberRole

# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

TEST_SESSION_SECRET = "test-session-secret"


def _make_jwt(
    member_id: int,
    secret: str = TEST_SESSION_SECRET,
    exp_hours: int = 24,
) -> str:
    payload = {
        "sub": str(member_id),
        "name": "TestUser",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=exp_hours),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _make_expired_jwt(member_id: int, secret: str = TEST_SESSION_SECRET) -> str:
    payload = {
        "sub": str(member_id),
        "name": "TestUser",
        "iat": datetime.now(timezone.utc) - timedelta(hours=48),
        "exp": datetime.now(timezone.utc) - timedelta(hours=24),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


# ---------------------------------------------------------------------------
# DB + member fixtures
# ---------------------------------------------------------------------------


def _make_member(
    id: int = 1,
    name: str = "TestUser",
    discord_id: str = "discord-999",
    role: MemberRole = MemberRole.advanced,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        name=name,
        discord_id=discord_id,
        discord_username=None,
        role=role,
        power_level=None,
        is_active=True,
    )


def _make_mock_db(member=None):
    """Return an AsyncMock session whose db.get() returns `member`."""
    session = AsyncMock()
    session.get = AsyncMock(return_value=member)
    session.execute = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# A protected endpoint to probe middleware behaviour
# The /api/members endpoint requires auth — use it as the probe.
# ---------------------------------------------------------------------------

PROTECTED_URL = "/api/members"


# ===========================================================================
# Middleware tests
# ===========================================================================


@pytest.mark.asyncio
async def test_auth_disabled_allows_access(monkeypatch):
    """AUTH_DISABLED=true + ENVIRONMENT=development bypasses auth entirely."""
    monkeypatch.setattr("app.config.settings.auth_disabled", True)
    monkeypatch.setattr("app.config.settings.environment", "development")

    mock_db = _make_mock_db()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("app.api.members.members_service.list_members", new_callable=AsyncMock) as m:
            m.return_value = []
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(PROTECTED_URL)
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_valid_service_token_allows_access(monkeypatch):
    """A correct Bearer token grants access as the bot-service principal."""
    token = "super-secret-service-token"
    monkeypatch.setattr("app.config.settings.bot_service_token", token)
    monkeypatch.setattr("app.config.settings.auth_disabled", False)

    mock_db = _make_mock_db()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("app.api.members.members_service.list_members", new_callable=AsyncMock) as m:
            m.return_value = []
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    PROTECTED_URL, headers={"Authorization": f"Bearer {token}"}
                )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_invalid_service_token_returns_401(monkeypatch):
    """A wrong Bearer token is rejected with 401."""
    monkeypatch.setattr("app.config.settings.bot_service_token", "correct-token")
    monkeypatch.setattr("app.config.settings.auth_disabled", False)
    monkeypatch.setattr("app.config.settings.session_secret", TEST_SESSION_SECRET)

    async def override_get_db():
        yield _make_mock_db()

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                PROTECTED_URL, headers={"Authorization": "Bearer wrong-token"}
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_valid_jwt_cookie_allows_access(monkeypatch):
    """A valid JWT session cookie with an existing member grants access."""
    monkeypatch.setattr("app.config.settings.auth_disabled", False)
    monkeypatch.setattr("app.config.settings.bot_service_token", "")
    monkeypatch.setattr("app.config.settings.session_secret", TEST_SESSION_SECRET)

    member = _make_member(id=42)
    mock_db = _make_mock_db(member=member)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    token = _make_jwt(member_id=42)
    try:
        with patch("app.api.members.members_service.list_members", new_callable=AsyncMock) as m:
            m.return_value = []
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                client.cookies.set("session", token)
                response = await client.get(PROTECTED_URL)
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_expired_jwt_returns_401(monkeypatch):
    """An expired JWT cookie is rejected with 401."""
    monkeypatch.setattr("app.config.settings.auth_disabled", False)
    monkeypatch.setattr("app.config.settings.bot_service_token", "")
    monkeypatch.setattr("app.config.settings.session_secret", TEST_SESSION_SECRET)

    async def override_get_db():
        yield _make_mock_db()

    app.dependency_overrides[get_db] = override_get_db
    expired_token = _make_expired_jwt(member_id=1)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            client.cookies.set("session", expired_token)
            response = await client.get(PROTECTED_URL)
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_jwt_with_deleted_member_returns_401(monkeypatch):
    """A valid JWT whose member no longer exists in the DB returns 401."""
    monkeypatch.setattr("app.config.settings.auth_disabled", False)
    monkeypatch.setattr("app.config.settings.bot_service_token", "")
    monkeypatch.setattr("app.config.settings.session_secret", TEST_SESSION_SECRET)

    # db.get returns None — member was deleted
    mock_db = _make_mock_db(member=None)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    token = _make_jwt(member_id=99)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            client.cookies.set("session", token)
            response = await client.get(PROTECTED_URL)
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_no_auth_returns_401(monkeypatch):
    """No credentials at all → 401."""
    monkeypatch.setattr("app.config.settings.auth_disabled", False)
    monkeypatch.setattr("app.config.settings.bot_service_token", "")
    monkeypatch.setattr("app.config.settings.session_secret", TEST_SESSION_SECRET)

    async def override_get_db():
        yield _make_mock_db()

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(PROTECTED_URL)
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_health_no_auth_required(monkeypatch):
    """/api/health is accessible without any credentials."""
    monkeypatch.setattr("app.config.settings.auth_disabled", False)
    monkeypatch.setattr("app.config.settings.bot_service_token", "")

    async def override_get_db():
        yield _make_mock_db()

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/health")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_version_no_auth_required(monkeypatch):
    """/api/version is accessible without any credentials."""
    monkeypatch.setattr("app.config.settings.auth_disabled", False)
    monkeypatch.setattr("app.config.settings.bot_service_token", "")

    with patch("app.api.version._fetch_bot_version", new=AsyncMock(return_value=None)):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/version")

    assert response.status_code == 200


# ===========================================================================
# Auth endpoint tests
# ===========================================================================


@pytest.mark.asyncio
async def test_login_returns_discord_url_and_state_cookie(monkeypatch):
    """GET /api/auth/login returns a Discord authorization URL and sets a state cookie."""
    monkeypatch.setattr("app.config.settings.discord_client_id", "test-client-id")
    monkeypatch.setattr(
        "app.config.settings.discord_redirect_uri", "http://localhost:8000/api/auth/callback"
    )
    monkeypatch.setattr("app.config.settings.environment", "development")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/auth/login")

    assert response.status_code == 200
    data = response.json()
    assert "url" in data
    assert "discord.com/oauth2/authorize" in data["url"]
    assert "test-client-id" in data["url"]
    assert "oauth_state" in response.cookies


@pytest.mark.asyncio
async def test_callback_invalid_state_redirects(monkeypatch):
    """Mismatched OAuth state redirects to /login?error=invalid_state."""
    monkeypatch.setattr("app.config.settings.environment", "development")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False
    ) as client:
        # Send a state cookie that doesn't match the query-param state
        client.cookies.set("oauth_state", "correct-state")
        response = await client.get(
            "/api/auth/callback", params={"code": "auth-code", "state": "wrong-state"}
        )

    assert response.status_code == 307
    assert response.headers["location"] == "/login?error=invalid_state"


@pytest.mark.asyncio
async def test_callback_happy_path(monkeypatch):
    """Full valid callback flow issues a session cookie and redirects to /."""
    monkeypatch.setattr("app.config.settings.session_secret", TEST_SESSION_SECRET)
    monkeypatch.setattr("app.config.settings.environment", "development")

    member = _make_member(id=7, discord_id="discord-777")
    mock_db = _make_mock_db(member=member)
    # scalar_one_or_none is a sync method on the SQLAlchemy result object
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=member)
    mock_db.execute = AsyncMock(return_value=mock_result)

    async def override_get_db():
        yield mock_db

    state = secrets.token_hex(32)
    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch(
            "app.api.auth._exchange_code_for_token",
            new=AsyncMock(return_value="discord-access-token"),
        ):
            with patch(
                "app.api.auth._get_discord_user",
                new=AsyncMock(return_value={"id": "discord-777"}),
            ):
                with patch(
                    "app.api.auth._check_guild_membership",
                    new=AsyncMock(return_value={"is_member": True}),
                ):
                    async with AsyncClient(
                        transport=ASGITransport(app=app),
                        base_url="http://test",
                        follow_redirects=False,
                    ) as client:
                        client.cookies.set("oauth_state", state)
                        response = await client.get(
                            "/api/auth/callback",
                            params={"code": "auth-code", "state": state},
                        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 307
    assert response.headers["location"] == "/"
    assert "session" in response.cookies


@pytest.mark.asyncio
async def test_callback_not_in_guild_redirects(monkeypatch):
    """User not in the guild redirects to /login?error=unauthorized."""
    monkeypatch.setattr("app.config.settings.environment", "development")

    state = secrets.token_hex(32)
    with patch(
        "app.api.auth._exchange_code_for_token",
        new=AsyncMock(return_value="discord-access-token"),
    ):
        with patch(
            "app.api.auth._get_discord_user",
            new=AsyncMock(return_value={"id": "discord-outsider"}),
        ):
            with patch(
                "app.api.auth._check_guild_membership",
                new=AsyncMock(return_value={"is_member": False}),
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                    follow_redirects=False,
                ) as client:
                    client.cookies.set("oauth_state", state)
                    response = await client.get(
                        "/api/auth/callback",
                        params={"code": "auth-code", "state": state},
                    )

    assert response.status_code == 307
    assert response.headers["location"] == "/login?error=unauthorized"


@pytest.mark.asyncio
async def test_callback_bot_unreachable_redirects_service_unavailable(monkeypatch):
    """Bot sidecar connection error redirects to /login?error=service_unavailable."""
    monkeypatch.setattr("app.config.settings.environment", "development")

    state = secrets.token_hex(32)
    with patch(
        "app.api.auth._exchange_code_for_token",
        new=AsyncMock(return_value="discord-access-token"),
    ):
        with patch(
            "app.api.auth._get_discord_user",
            new=AsyncMock(return_value={"id": "discord-abc"}),
        ):
            with patch(
                "app.api.auth._check_guild_membership",
                side_effect=httpx.ConnectError("bot unreachable"),
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                    follow_redirects=False,
                ) as client:
                    client.cookies.set("oauth_state", state)
                    response = await client.get(
                        "/api/auth/callback",
                        params={"code": "auth-code", "state": state},
                    )

    assert response.status_code == 307
    assert response.headers["location"] == "/login?error=service_unavailable"


@pytest.mark.asyncio
async def test_callback_no_member_record_redirects(monkeypatch):
    """Guild member whose discord_id isn't in the DB redirects to /login?error=unauthorized."""
    monkeypatch.setattr("app.config.settings.environment", "development")

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_db.execute = AsyncMock(return_value=mock_result)

    async def override_get_db():
        yield mock_db

    state = secrets.token_hex(32)
    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch(
            "app.api.auth._exchange_code_for_token",
            new=AsyncMock(return_value="discord-access-token"),
        ):
            with patch(
                "app.api.auth._get_discord_user",
                new=AsyncMock(return_value={"id": "discord-unknown"}),
            ):
                with patch(
                    "app.api.auth._check_guild_membership",
                    new=AsyncMock(return_value={"is_member": True}),
                ):
                    async with AsyncClient(
                        transport=ASGITransport(app=app),
                        base_url="http://test",
                        follow_redirects=False,
                    ) as client:
                        client.cookies.set("oauth_state", state)
                        response = await client.get(
                            "/api/auth/callback",
                            params={"code": "auth-code", "state": state},
                        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 307
    assert response.headers["location"] == "/login?error=unauthorized"


@pytest.mark.asyncio
async def test_logout_clears_session_cookie():
    """POST /api/auth/logout clears the session cookie."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        client.cookies.set("session", "some-token")
        response = await client.post("/api/auth/logout")

    assert response.status_code == 200
    assert response.json() == {"status": "logged_out"}
    # Cookie is cleared (max-age=0 or expires in the past)
    assert "session" in response.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_me_with_valid_session(monkeypatch):
    """GET /api/auth/me returns member info when authenticated via session cookie."""
    monkeypatch.setattr("app.config.settings.auth_disabled", False)
    monkeypatch.setattr("app.config.settings.bot_service_token", "")
    monkeypatch.setattr("app.config.settings.session_secret", TEST_SESSION_SECRET)

    member = _make_member(id=5, name="Alice", discord_id="discord-555", role=MemberRole.heavy_hitter)
    mock_db = _make_mock_db(member=member)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    token = _make_jwt(member_id=5)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            client.cookies.set("session", token)
            response = await client.get("/api/auth/me")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    data = response.json()
    assert data["member_id"] == 5
    assert data["name"] == "Alice"
    assert data["role"] == "heavy_hitter"
    assert data["discord_id"] == "discord-555"


@pytest.mark.asyncio
async def test_me_without_auth_returns_401(monkeypatch):
    """GET /api/auth/me without credentials returns 401."""
    monkeypatch.setattr("app.config.settings.auth_disabled", False)
    monkeypatch.setattr("app.config.settings.bot_service_token", "")
    monkeypatch.setattr("app.config.settings.session_secret", TEST_SESSION_SECRET)

    async def override_get_db():
        yield _make_mock_db()

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/auth/me")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 401
