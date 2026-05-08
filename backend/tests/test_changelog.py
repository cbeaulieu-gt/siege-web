"""Endpoint tests for /api/changelog — status and mark-seen endpoints.

Covers AC #5 from issue #295:
  1. GET /api/changelog/status with a fresh user → last_seen_changelog_at: null
  2. POST /api/changelog/mark-seen then GET → returns the timestamp (not null)
  3. POST mark-seen twice → idempotent, both 200, second timestamp >= first
  4. GET status without auth → 401
  5. POST mark-seen without auth → 401
  6. GET status with service Bearer token → 400 (endpoint requires a user session)
"""

import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import app

# ---------------------------------------------------------------------------
# Shared JWT / auth helpers (mirrors test_auth.py pattern)
# ---------------------------------------------------------------------------

TEST_SESSION_SECRET = "test-session-secret"


def _make_jwt(member_id: int) -> str:
    """Return a signed JWT for the given member ID."""
    from datetime import UTC, timedelta

    import jwt

    payload = {
        "sub": str(member_id),
        "name": "TestUser",
        "iat": datetime.datetime.now(UTC),
        "exp": datetime.datetime.now(UTC) + timedelta(hours=24),
    }
    return jwt.encode(payload, TEST_SESSION_SECRET, algorithm="HS256")


# ---------------------------------------------------------------------------
# Member stub + DB mock helpers
# ---------------------------------------------------------------------------


def _make_member(
    id: int = 1,
    name: str = "TestUser",
    last_seen_changelog_at: datetime.datetime | None = None,
) -> SimpleNamespace:
    """Return a minimal Member-like namespace."""
    return SimpleNamespace(
        id=id,
        name=name,
        discord_id="discord-001",
        discord_username=None,
        role=SimpleNamespace(value="advanced"),
        is_active=True,
        last_seen_changelog_at=last_seen_changelog_at,
    )


def _make_mock_db(member=None):
    """Return an AsyncMock session whose db.get() returns ``member``."""
    session = AsyncMock()
    session.get = AsyncMock(return_value=member)
    session.commit = AsyncMock()
    session.execute = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# 1. GET /api/changelog/status with a fresh user → null
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_status_fresh_user_returns_null(monkeypatch):
    """A user who has never viewed the changelog gets last_seen_changelog_at: null."""
    monkeypatch.setattr("app.config.settings.auth_disabled", False)
    monkeypatch.setattr("app.config.settings.bot_service_token", "")
    monkeypatch.setattr("app.config.settings.session_secret", TEST_SESSION_SECRET)

    member = _make_member(id=1, last_seen_changelog_at=None)
    mock_db = _make_mock_db(member=member)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    token = _make_jwt(member_id=1)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("session", token)
            response = await client.get("/api/changelog/status")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    data = response.json()
    assert data["last_seen_changelog_at"] is None


# ---------------------------------------------------------------------------
# 2. POST mark-seen then GET → returns the timestamp set by POST
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_seen_then_get_status_returns_timestamp(monkeypatch):
    """After marking changelog as seen the GET endpoint returns a non-null timestamp."""
    monkeypatch.setattr("app.config.settings.auth_disabled", False)
    monkeypatch.setattr("app.config.settings.bot_service_token", "")
    monkeypatch.setattr("app.config.settings.session_secret", TEST_SESSION_SECRET)

    # Start with no timestamp; the POST endpoint will mutate this object.
    member = _make_member(id=2, last_seen_changelog_at=None)
    mock_db = _make_mock_db(member=member)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    token = _make_jwt(member_id=2)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("session", token)
            post_response = await client.post("/api/changelog/mark-seen")
            get_response = await client.get("/api/changelog/status")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert post_response.status_code == 200
    post_data = post_response.json()
    assert post_data["last_seen_changelog_at"] is not None

    assert get_response.status_code == 200
    get_data = get_response.json()
    # The timestamp must survive the round-trip through the DB mock.
    assert get_data["last_seen_changelog_at"] is not None
    # Both calls return the same timestamp (GET reads what POST wrote).
    assert get_data["last_seen_changelog_at"] == post_data["last_seen_changelog_at"]


# ---------------------------------------------------------------------------
# 3. POST mark-seen twice → idempotent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_seen_twice_is_idempotent(monkeypatch):
    """Calling mark-seen twice both succeed; second timestamp >= first."""
    monkeypatch.setattr("app.config.settings.auth_disabled", False)
    monkeypatch.setattr("app.config.settings.bot_service_token", "")
    monkeypatch.setattr("app.config.settings.session_secret", TEST_SESSION_SECRET)

    member = _make_member(id=3, last_seen_changelog_at=None)
    mock_db = _make_mock_db(member=member)

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    token = _make_jwt(member_id=3)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("session", token)
            first = await client.post("/api/changelog/mark-seen")
            second = await client.post("/api/changelog/mark-seen")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert first.status_code == 200
    assert second.status_code == 200

    ts1 = first.json()["last_seen_changelog_at"]
    ts2 = second.json()["last_seen_changelog_at"]
    assert ts1 is not None
    assert ts2 is not None
    # Second call must set a timestamp >= the first (clocks only move forward).
    assert ts2 >= ts1


# ---------------------------------------------------------------------------
# 4. GET status with no auth → 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_status_no_auth_returns_401(monkeypatch):
    """GET /api/changelog/status without credentials returns 401."""
    monkeypatch.setattr("app.config.settings.auth_disabled", False)
    monkeypatch.setattr("app.config.settings.bot_service_token", "")
    monkeypatch.setattr("app.config.settings.session_secret", TEST_SESSION_SECRET)

    async def override_get_db():
        yield _make_mock_db()

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/changelog/status")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 5. POST mark-seen with no auth → 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_mark_seen_no_auth_returns_401(monkeypatch):
    """POST /api/changelog/mark-seen without credentials returns 401."""
    monkeypatch.setattr("app.config.settings.auth_disabled", False)
    monkeypatch.setattr("app.config.settings.bot_service_token", "")
    monkeypatch.setattr("app.config.settings.session_secret", TEST_SESSION_SECRET)

    async def override_get_db():
        yield _make_mock_db()

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/changelog/mark-seen")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 6. GET status with service Bearer token → 400
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_status_service_token_returns_400(monkeypatch):
    """Service principals (Bearer token) cannot use the changelog endpoint."""
    service_token = "super-secret-service-token"
    monkeypatch.setattr("app.config.settings.auth_disabled", False)
    monkeypatch.setattr("app.config.settings.bot_service_token", service_token)
    monkeypatch.setattr("app.config.settings.session_secret", TEST_SESSION_SECRET)

    mock_db = _make_mock_db()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/changelog/status",
                headers={"Authorization": f"Bearer {service_token}"},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 400
    assert "endpoint requires a user session" in response.json()["detail"]
