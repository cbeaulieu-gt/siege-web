# Discord OAuth2 Authentication — Implementation Plan

> **Status: COMPLETED (2026-03)** — Discord OAuth2 is shipped and live. This file is a historical record of the implementation plan. For the canonical ongoing spec, see [`discord-auth-plan.md`](./discord-auth-plan.md). For current project status, see [`docs/STATUS.md`](../../STATUS.md).

> ~~**For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.~~ *(Historical — this plan is complete; do not re-execute.)*

**Goal:** Add Discord OAuth2 login so only verified guild members can access the app — replacing the current zero-auth state.

**Architecture:** Discord OAuth2 (Authorization Code Grant, `identify` scope only) → backend exchanges code for token → verifies guild membership via bot sidecar → issues 24-hour HS256 JWT in HttpOnly cookie. Frontend wraps all routes in `<RequireAuth>` and adds `AuthContext` for user state. Dev bypass via `AUTH_DISABLED=true` (development environment only, enforced by startup guard).

**Tech Stack:** FastAPI (backend), PyJWT, httpx, React 18 + TypeScript (frontend), Axios, React Router v6, MSW (test mocks), vitest + testing-library (frontend tests), pytest + respx (backend tests).

**Spec:** `docs/superpowers/plans/discord-auth-plan.md`

---

## File Structure

### New files

| File | Responsibility |
|---|---|
| `backend/app/dependencies/__init__.py` | Package init |
| `backend/app/dependencies/auth.py` | `AuthenticatedUser` dataclass + `get_current_user` FastAPI dependency |
| `backend/app/api/auth.py` | OAuth2 endpoints: login, callback, logout, me |
| `backend/tests/test_auth.py` | Backend auth tests (middleware + endpoints) |
| `frontend/src/context/AuthContext.tsx` | React context: user state, logout, 401 handling |
| `frontend/src/pages/LoginPage.tsx` | Login page with Discord button + error messages |
| `frontend/src/components/RequireAuth.tsx` | Route guard — redirects unauthenticated to `/login` |
| `frontend/src/test/context/AuthContext.test.tsx` | AuthContext + RequireAuth tests |
| `frontend/src/test/pages/LoginPage.test.tsx` | LoginPage tests |

### Modified files

| File | Change |
|---|---|
| `backend/app/services/bot_client.py` | Add `get_member(discord_user_id)` method |
| `backend/app/main.py` | Register auth router; apply `get_current_user` to protected routers |
| `frontend/src/api/client.ts` | Add 401 → `/login` response interceptor |
| `frontend/src/App.tsx` | Add `/login` route; wrap protected routes in `<RequireAuth>` |
| `frontend/src/components/Layout.tsx` | Add user display + "Sign out" button to nav |
| `frontend/src/test/utils.tsx` | Add `AuthProvider` to test wrapper |

### Already done (no changes needed)

| File | Status |
|---|---|
| `backend/app/config.py` | All auth settings present (`discord_client_id`, `discord_client_secret`, `discord_redirect_uri`, `session_secret`, `bot_service_token`, `auth_disabled`, `environment` with no default) |
| `backend/requirements.txt` | `PyJWT>=2.9`, `cryptography>=43` already listed |
| `backend/requirements-dev.txt` | `respx>=0.21` already listed |
| `.env.example` | All OAuth2 vars already documented |
| `backend/app/main.py` lifespan guard | `AUTH_DISABLED` startup guard already implemented |
| `bot/app/http_api.py` | `GET /api/members/{discord_user_id}` already implemented |
| `backend/tests/conftest.py` | Sets `ENVIRONMENT=test` for all tests |

---

## Task 1 — Completed: BotClient.get_member() method

**Files:**
- Modify: `backend/app/services/bot_client.py:61-72`
- Test: `backend/tests/test_bot_client.py` (existing file — add tests)

The bot sidecar endpoint exists but the backend has no client method to call it. Unlike other `BotClient` methods that swallow errors and return `False`/`None`/`[]`, `get_member` must **raise** on connection failure so the auth callback can distinguish "not in guild" from "bot is down."

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_bot_client.py`:

```python
# --- get_member tests ---

@pytest.mark.asyncio
async def test_get_member_returns_member_dict(mock_bot_api):
    """get_member returns the full member dict when the sidecar responds 200."""
    member_data = {
        "is_member": True,
        "discord_id": "111222333",
        "username": "testuser",
        "display_name": "Test User",
        "roles": ["role1"],
    }
    mock_bot_api.get("/api/members/111222333").mock(
        return_value=httpx.Response(200, json=member_data)
    )
    result = await bot_client.get_member("111222333")
    assert result == member_data


@pytest.mark.asyncio
async def test_get_member_returns_not_member(mock_bot_api):
    """get_member returns is_member=false dict when user is not in guild."""
    mock_bot_api.get("/api/members/999").mock(
        return_value=httpx.Response(200, json={"is_member": False})
    )
    result = await bot_client.get_member("999")
    assert result == {"is_member": False}


@pytest.mark.asyncio
async def test_get_member_raises_on_connection_error(mock_bot_api):
    """get_member raises httpx.HTTPError when the sidecar is unreachable."""
    mock_bot_api.get("/api/members/111222333").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )
    with pytest.raises(httpx.HTTPError):
        await bot_client.get_member("111222333")


@pytest.mark.asyncio
async def test_get_member_raises_on_503(mock_bot_api):
    """get_member raises httpx.HTTPStatusError on 503 from sidecar."""
    mock_bot_api.get("/api/members/111222333").mock(
        return_value=httpx.Response(503, json={"detail": "Guild not available"})
    )
    with pytest.raises(httpx.HTTPStatusError):
        await bot_client.get_member("111222333")
```

Note: Check `test_bot_client.py` for the existing `mock_bot_api` fixture name and import patterns — the tests above assume `respx` is used with a fixture that mocks `httpx` calls. Adapt the fixture name if different.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_bot_client.py -k "get_member" -v`
Expected: FAIL — `AttributeError: 'BotClient' object has no attribute 'get_member'`

- [ ] **Step 3: Implement get_member**

Add to `backend/app/services/bot_client.py`, before `bot_client = BotClient()`:

```python
    async def get_member(self, discord_user_id: str) -> dict:
        """
        Check guild membership via bot sidecar.

        Returns the member dict (including ``is_member`` boolean).
        Raises ``httpx.HTTPError`` if the sidecar is unreachable or returns
        a non-2xx status — callers must distinguish "not in guild" from
        "sidecar outage."
        """
        async with self._make_client() as client:
            response = await client.get(f"/api/members/{discord_user_id}")
            response.raise_for_status()
            return response.json()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_bot_client.py -k "get_member" -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```
git add backend/app/services/bot_client.py backend/tests/test_bot_client.py
git commit -m "feat(auth): add BotClient.get_member() for guild membership lookup

Raises on connection failure (unlike other BotClient methods that swallow
errors) so the auth callback can distinguish 'not in guild' from 'bot down.'

Refs discord-auth-plan.md Phase A0"
```

---

## Task 2 — Completed: Auth middleware — `get_current_user` dependency

**Files:**
- Create: `backend/app/dependencies/__init__.py`
- Create: `backend/app/dependencies/auth.py`
- Test: `backend/tests/test_auth.py` (new file)

This is the FastAPI dependency that protects routes. It checks three paths in order: dev bypass → service Bearer token → JWT session cookie. Applied via `Depends(get_current_user)` to protected routers.

- [ ] **Step 1: Create the dependencies package**

Create `backend/app/dependencies/__init__.py` with empty content (package init).

- [ ] **Step 2: Write the failing tests for the middleware**

Create `backend/tests/test_auth.py`:

```python
"""Tests for Discord OAuth2 auth middleware and endpoints."""

import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jwt(member_id: int, secret: str = "test-session-secret", exp_hours: int = 24) -> str:
    """Create a valid JWT for testing."""
    payload = {
        "sub": str(member_id),
        "name": "TestUser",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=exp_hours),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _make_expired_jwt(member_id: int, secret: str = "test-session-secret") -> str:
    """Create an expired JWT for testing."""
    payload = {
        "sub": str(member_id),
        "name": "TestUser",
        "iat": datetime.now(timezone.utc) - timedelta(hours=48),
        "exp": datetime.now(timezone.utc) - timedelta(hours=24),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    """Mock database session that returns a fake Member on .get()."""
    session = AsyncMock()
    return session


@pytest.fixture
def _override_db(mock_db):
    """Override the get_db dependency with the mock."""
    async def override():
        yield mock_db

    app.dependency_overrides[get_db] = override
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Auth middleware tests — AUTH_DISABLED bypass
# ---------------------------------------------------------------------------

class TestAuthDisabledBypass:

    @pytest.mark.asyncio
    async def test_auth_disabled_allows_access(self, monkeypatch, _override_db):
        """AUTH_DISABLED=true with ENVIRONMENT=development allows all requests."""
        monkeypatch.setattr("app.config.settings.auth_disabled", True)
        monkeypatch.setattr("app.config.settings.environment", "development")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/members")

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Auth middleware tests — service Bearer token
# ---------------------------------------------------------------------------

class TestServiceToken:

    @pytest.mark.asyncio
    async def test_valid_service_token_allows_access(self, monkeypatch, _override_db, mock_db):
        """A valid Bearer token matching bot_service_token returns 200."""
        monkeypatch.setattr("app.config.settings.auth_disabled", False)
        monkeypatch.setattr("app.config.settings.bot_service_token", "secret-bot-token")
        mock_db.execute = AsyncMock(return_value=AsyncMock(scalars=lambda: AsyncMock(all=lambda: [])))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/members",
                headers={"Authorization": "Bearer secret-bot-token"},
            )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_invalid_service_token_returns_401(self, monkeypatch, _override_db):
        """An invalid Bearer token returns 401."""
        monkeypatch.setattr("app.config.settings.auth_disabled", False)
        monkeypatch.setattr("app.config.settings.bot_service_token", "correct-token")
        monkeypatch.setattr("app.config.settings.session_secret", "test-session-secret")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/members",
                headers={"Authorization": "Bearer wrong-token"},
            )

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Auth middleware tests — JWT session cookie
# ---------------------------------------------------------------------------

class TestJwtSessionCookie:

    @pytest.mark.asyncio
    async def test_valid_jwt_cookie_allows_access(self, monkeypatch, _override_db, mock_db):
        """A valid JWT session cookie with a matching Member record returns 200."""
        monkeypatch.setattr("app.config.settings.auth_disabled", False)
        monkeypatch.setattr("app.config.settings.session_secret", "test-session-secret")

        # Mock db.get(Member, 1) to return a fake member
        fake_member = AsyncMock()
        fake_member.id = 1
        fake_member.name = "TestUser"
        fake_member.is_service = False
        mock_db.get = AsyncMock(return_value=fake_member)
        # Also mock execute for the actual route handler
        mock_db.execute = AsyncMock(return_value=AsyncMock(scalars=lambda: AsyncMock(all=lambda: [])))

        token = _make_jwt(member_id=1)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/members",
                cookies={"session": token},
            )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_expired_jwt_returns_401(self, monkeypatch, _override_db):
        """An expired JWT session cookie returns 401."""
        monkeypatch.setattr("app.config.settings.auth_disabled", False)
        monkeypatch.setattr("app.config.settings.session_secret", "test-session-secret")

        token = _make_expired_jwt(member_id=1)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/members",
                cookies={"session": token},
            )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_jwt_with_deleted_member_returns_401(self, monkeypatch, _override_db, mock_db):
        """A valid JWT for a deleted Member record returns 401 (forced revocation)."""
        monkeypatch.setattr("app.config.settings.auth_disabled", False)
        monkeypatch.setattr("app.config.settings.session_secret", "test-session-secret")

        mock_db.get = AsyncMock(return_value=None)  # Member deleted

        token = _make_jwt(member_id=999)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/members",
                cookies={"session": token},
            )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_no_auth_returns_401(self, monkeypatch, _override_db):
        """A request with no auth credentials returns 401."""
        monkeypatch.setattr("app.config.settings.auth_disabled", False)
        monkeypatch.setattr("app.config.settings.session_secret", "test-session-secret")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/members")

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Public routes — no auth required
# ---------------------------------------------------------------------------

class TestPublicRoutes:

    @pytest.mark.asyncio
    async def test_health_no_auth_required(self, monkeypatch, _override_db, mock_db):
        """Health endpoint is accessible without auth."""
        monkeypatch.setattr("app.config.settings.auth_disabled", False)
        mock_db.execute = AsyncMock()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/health")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_version_no_auth_required(self, monkeypatch):
        """Version endpoint is accessible without auth."""
        monkeypatch.setattr("app.config.settings.auth_disabled", False)

        with patch("app.api.version._fetch_bot_version", new=AsyncMock(return_value=None)):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/version")

        assert response.status_code == 200
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_auth.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.dependencies'`

- [ ] **Step 4: Implement `get_current_user` dependency**

Create `backend/app/dependencies/auth.py`:

```python
"""FastAPI dependency for request authentication.

Checks three paths in order:
1. AUTH_DISABLED=true (development only) → stub user
2. Authorization: Bearer <token> → service principal
3. Cookie: session=<jwt> → authenticated user
4. Otherwise → HTTP 401
"""

import secrets
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.models.member import Member


@dataclass
class AuthenticatedUser:
    """Represents the currently authenticated user or service principal."""

    member_id: int | None
    name: str
    is_service: bool


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthenticatedUser:
    """Resolve the current user from the request.

    Priority:
    1. AUTH_DISABLED → dev stub (member_id=None)
    2. Bearer token → service principal
    3. JWT session cookie → authenticated member
    4. Else → 401
    """
    # 1. Dev bypass
    if settings.auth_disabled:
        return AuthenticatedUser(member_id=None, name="dev-user", is_service=False)

    # 2. Service token (Bearer) — timing-safe comparison
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer ") and settings.bot_service_token:
        provided = auth_header.removeprefix("Bearer ")
        if secrets.compare_digest(provided, settings.bot_service_token):
            return AuthenticatedUser(
                member_id=None, name="bot-service", is_service=True
            )

    # 3. User session cookie
    session_token = request.cookies.get("session")
    if session_token:
        try:
            payload = jwt.decode(
                session_token, settings.session_secret, algorithms=["HS256"]
            )
            member = await db.get(Member, int(payload["sub"]))
            if member:
                return AuthenticatedUser(
                    member_id=member.id, name=member.name, is_service=False
                )
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, KeyError, ValueError):
            pass

    raise HTTPException(status_code=401, detail="Not authenticated")
```

- [ ] **Step 5: Wire `get_current_user` into `main.py`**

Modify `backend/app/main.py`:

1. Add import: `from app.dependencies.auth import get_current_user, AuthenticatedUser`
2. Add import: `from fastapi import Depends`
3. For each protected router, add `dependencies=[Depends(get_current_user)]` to the `include_router` call.

Leave these routers **without** the dependency (public):
- `health_router`
- `version_router`
- Auth router (added in Task 3)

All other routers get `dependencies=[Depends(get_current_user)]`:

```python
# Public routes — no auth
app.include_router(health_router, prefix="/api")
app.include_router(version_router, prefix="/api")

# Protected routes — require authentication
_auth_deps = [Depends(get_current_user)]
app.include_router(reference_router, prefix="/api", dependencies=_auth_deps)
app.include_router(discord_sync_router, prefix="/api", dependencies=_auth_deps)
app.include_router(members_router, prefix="/api", dependencies=_auth_deps)
app.include_router(sieges_router, prefix="/api", dependencies=_auth_deps)
app.include_router(buildings_router, prefix="/api", dependencies=_auth_deps)
app.include_router(siege_members_router, prefix="/api", dependencies=_auth_deps)
app.include_router(board_router, prefix="/api", dependencies=_auth_deps)
app.include_router(lifecycle_router, prefix="/api", dependencies=_auth_deps)
app.include_router(posts_router, prefix="/api", dependencies=_auth_deps)
app.include_router(validation_router, prefix="/api", dependencies=_auth_deps)
app.include_router(autofill_router, prefix="/api", dependencies=_auth_deps)
app.include_router(comparison_router, prefix="/api", dependencies=_auth_deps)
app.include_router(attack_day_router, prefix="/api", dependencies=_auth_deps)
app.include_router(images_router, prefix="/api", dependencies=_auth_deps)
app.include_router(notifications_router, prefix="/api", dependencies=_auth_deps)
app.include_router(post_priority_config_router, prefix="/api", dependencies=_auth_deps)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_auth.py -v`
Expected: All tests pass.

Then run the full test suite to verify existing tests still pass (they should, because `conftest.py` sets `ENVIRONMENT=test` and `auth_disabled` defaults to `False`, but most tests override `get_db` which also satisfies the dependency chain):

Run: `cd backend && python -m pytest --ignore=tests/test_schema.py -v`
Expected: All existing tests pass. Some may now return 401 — if so, they need `AUTH_DISABLED=true` or a session cookie. Fix any that fail by adding `monkeypatch.setattr("app.config.settings.auth_disabled", True)` to their setup.

- [ ] **Step 7: Commit**

```
git add backend/app/dependencies/ backend/tests/test_auth.py backend/app/main.py
git commit -m "feat(auth): add get_current_user middleware and protect all routes

Three-path auth check: AUTH_DISABLED bypass → Bearer service token →
JWT session cookie. Health and version endpoints remain public.

Refs discord-auth-plan.md Phase A2"
```

---

## Task 3 — Completed: Backend auth endpoints (login, callback, logout, me)

**Files:**
- Create: `backend/app/api/auth.py`
- Modify: `backend/app/main.py` (register auth router)
- Test: `backend/tests/test_auth.py` (add endpoint tests)

These are the OAuth2 flow endpoints. The callback is the most complex — it exchanges the Discord code for a token, verifies guild membership via the bot sidecar, matches the member record, and issues a JWT.

- [ ] **Step 1: Write the failing tests for auth endpoints**

Add to `backend/tests/test_auth.py`:

```python
# ---------------------------------------------------------------------------
# Auth endpoint tests — /api/auth/*
# ---------------------------------------------------------------------------

class TestLoginEndpoint:

    @pytest.mark.asyncio
    async def test_login_returns_discord_url_and_state_cookie(self, monkeypatch):
        """GET /api/auth/login returns a Discord OAuth URL and sets an oauth_state cookie."""
        monkeypatch.setattr("app.config.settings.auth_disabled", False)
        monkeypatch.setattr("app.config.settings.discord_client_id", "test-client-id")
        monkeypatch.setattr("app.config.settings.discord_redirect_uri", "http://localhost:8000/api/auth/callback")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/auth/login")

        assert response.status_code == 200
        data = response.json()
        assert "url" in data
        assert "discord.com/oauth2/authorize" in data["url"]
        assert "scope=identify" in data["url"]
        assert "client_id=test-client-id" in data["url"]

        # Check state cookie was set
        cookies = response.cookies
        assert "oauth_state" in cookies


class TestCallbackEndpoint:

    @pytest.mark.asyncio
    async def test_callback_invalid_state_redirects(self, monkeypatch):
        """GET /api/auth/callback with mismatched state redirects to /login?error=invalid_state."""
        monkeypatch.setattr("app.config.settings.auth_disabled", False)
        monkeypatch.setattr("app.config.settings.session_secret", "test-session-secret")

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            follow_redirects=False,
        ) as client:
            response = await client.get(
                "/api/auth/callback?code=test&state=wrong-state",
                cookies={"oauth_state": "correct-state"},
            )

        assert response.status_code == 307
        assert "/login?error=invalid_state" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_callback_happy_path(self, monkeypatch, _override_db, mock_db):
        """Valid callback → exchanges code → verifies guild → issues JWT cookie → redirects to /."""
        monkeypatch.setattr("app.config.settings.auth_disabled", False)
        monkeypatch.setattr("app.config.settings.discord_client_id", "test-client-id")
        monkeypatch.setattr("app.config.settings.discord_client_secret", "test-secret")
        monkeypatch.setattr("app.config.settings.discord_redirect_uri", "http://localhost:8000/api/auth/callback")
        monkeypatch.setattr("app.config.settings.session_secret", "test-session-secret")

        # Mock db.get(Member, ...) to return a fake member
        fake_member = AsyncMock()
        fake_member.id = 42
        fake_member.name = "Aethon"
        fake_member.role = AsyncMock()
        fake_member.role.value = "heavy_hitter"
        fake_member.discord_id = "111222333"
        mock_db.get = AsyncMock(return_value=fake_member)
        # Mock the scalar query for finding member by discord_id
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = AsyncMock(return_value=fake_member)
        mock_db.execute = AsyncMock(return_value=mock_result)

        state_nonce = "a" * 64

        with patch("app.api.auth._exchange_code_for_token", new=AsyncMock(return_value="mock-access-token")), \
             patch("app.api.auth._get_discord_user", new=AsyncMock(return_value={"id": "111222333", "username": "aethon"})), \
             patch("app.api.auth._check_guild_membership", new=AsyncMock(return_value={"is_member": True, "discord_id": "111222333"})):

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                follow_redirects=False,
            ) as client:
                response = await client.get(
                    f"/api/auth/callback?code=valid-code&state={state_nonce}",
                    cookies={"oauth_state": state_nonce},
                )

        assert response.status_code == 307
        assert response.headers["location"] == "/"
        assert "session" in response.cookies

    @pytest.mark.asyncio
    async def test_callback_not_in_guild_redirects(self, monkeypatch, _override_db, mock_db):
        """User not in guild → redirect /login?error=unauthorized."""
        monkeypatch.setattr("app.config.settings.auth_disabled", False)
        monkeypatch.setattr("app.config.settings.discord_client_id", "test-client-id")
        monkeypatch.setattr("app.config.settings.discord_client_secret", "test-secret")
        monkeypatch.setattr("app.config.settings.discord_redirect_uri", "http://localhost:8000/api/auth/callback")
        monkeypatch.setattr("app.config.settings.session_secret", "test-session-secret")

        state_nonce = "b" * 64

        with patch("app.api.auth._exchange_code_for_token", new=AsyncMock(return_value="mock-token")), \
             patch("app.api.auth._get_discord_user", new=AsyncMock(return_value={"id": "999", "username": "outsider"})), \
             patch("app.api.auth._check_guild_membership", new=AsyncMock(return_value={"is_member": False})):

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                follow_redirects=False,
            ) as client:
                response = await client.get(
                    f"/api/auth/callback?code=valid-code&state={state_nonce}",
                    cookies={"oauth_state": state_nonce},
                )

        assert response.status_code == 307
        assert "/login?error=unauthorized" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_callback_bot_unreachable_redirects_service_unavailable(self, monkeypatch, _override_db):
        """Bot sidecar unreachable → redirect /login?error=service_unavailable (NOT unauthorized)."""
        monkeypatch.setattr("app.config.settings.auth_disabled", False)
        monkeypatch.setattr("app.config.settings.discord_client_id", "test-client-id")
        monkeypatch.setattr("app.config.settings.discord_client_secret", "test-secret")
        monkeypatch.setattr("app.config.settings.discord_redirect_uri", "http://localhost:8000/api/auth/callback")
        monkeypatch.setattr("app.config.settings.session_secret", "test-session-secret")

        state_nonce = "c" * 64

        import httpx as httpx_mod
        with patch("app.api.auth._exchange_code_for_token", new=AsyncMock(return_value="mock-token")), \
             patch("app.api.auth._get_discord_user", new=AsyncMock(return_value={"id": "111", "username": "test"})), \
             patch("app.api.auth._check_guild_membership", new=AsyncMock(side_effect=httpx_mod.ConnectError("Connection refused"))):

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                follow_redirects=False,
            ) as client:
                response = await client.get(
                    f"/api/auth/callback?code=valid-code&state={state_nonce}",
                    cookies={"oauth_state": state_nonce},
                )

        assert response.status_code == 307
        assert "/login?error=service_unavailable" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_callback_no_member_record_redirects(self, monkeypatch, _override_db, mock_db):
        """discord_id not in DB (no Member match) → redirect /login?error=unauthorized."""
        monkeypatch.setattr("app.config.settings.auth_disabled", False)
        monkeypatch.setattr("app.config.settings.discord_client_id", "test-client-id")
        monkeypatch.setattr("app.config.settings.discord_client_secret", "test-secret")
        monkeypatch.setattr("app.config.settings.discord_redirect_uri", "http://localhost:8000/api/auth/callback")
        monkeypatch.setattr("app.config.settings.session_secret", "test-session-secret")

        # Member not found
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = AsyncMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        state_nonce = "d" * 64

        with patch("app.api.auth._exchange_code_for_token", new=AsyncMock(return_value="mock-token")), \
             patch("app.api.auth._get_discord_user", new=AsyncMock(return_value={"id": "111222333", "username": "test"})), \
             patch("app.api.auth._check_guild_membership", new=AsyncMock(return_value={"is_member": True, "discord_id": "111222333"})):

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                follow_redirects=False,
            ) as client:
                response = await client.get(
                    f"/api/auth/callback?code=valid-code&state={state_nonce}",
                    cookies={"oauth_state": state_nonce},
                )

        assert response.status_code == 307
        assert "/login?error=unauthorized" in response.headers["location"]


class TestLogoutEndpoint:

    @pytest.mark.asyncio
    async def test_logout_clears_session_cookie(self):
        """POST /api/auth/logout clears the session cookie."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/auth/logout")

        assert response.status_code == 200
        assert response.json() == {"status": "logged_out"}
        # Session cookie should be cleared (max_age=0)
        set_cookie = response.headers.get("set-cookie", "")
        assert "session=" in set_cookie


class TestMeEndpoint:

    @pytest.mark.asyncio
    async def test_me_with_valid_session(self, monkeypatch, _override_db, mock_db):
        """GET /api/auth/me with a valid JWT returns user info."""
        monkeypatch.setattr("app.config.settings.auth_disabled", False)
        monkeypatch.setattr("app.config.settings.session_secret", "test-session-secret")

        fake_member = AsyncMock()
        fake_member.id = 1
        fake_member.name = "TestUser"
        fake_member.role = AsyncMock()
        fake_member.role.value = "heavy_hitter"
        fake_member.discord_id = "111222333"
        mock_db.get = AsyncMock(return_value=fake_member)

        token = _make_jwt(member_id=1)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/auth/me",
                cookies={"session": token},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["member_id"] == 1
        assert data["name"] == "TestUser"
        assert data["role"] == "heavy_hitter"
        assert data["discord_id"] == "111222333"

    @pytest.mark.asyncio
    async def test_me_without_auth_returns_401(self, monkeypatch, _override_db):
        """GET /api/auth/me without auth returns 401."""
        monkeypatch.setattr("app.config.settings.auth_disabled", False)
        monkeypatch.setattr("app.config.settings.session_secret", "test-session-secret")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/auth/me")

        assert response.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_auth.py::TestLoginEndpoint -v`
Expected: FAIL — `ModuleNotFoundError` or import error for `app.api.auth`

- [ ] **Step 3: Implement auth endpoints**

Create `backend/app/api/auth.py`:

```python
"""Discord OAuth2 authentication endpoints.

Flow:
1. GET /api/auth/login → returns Discord OAuth URL + sets state cookie
2. GET /api/auth/callback → exchanges code, verifies guild, issues JWT
3. POST /api/auth/logout → clears session cookie
4. GET /api/auth/me → returns current user info (requires auth)
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.dependencies.auth import AuthenticatedUser, get_current_user
from app.models.member import Member
from app.services.bot_client import bot_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

DISCORD_API_BASE = "https://discord.com/api/v10"
DISCORD_OAUTH_AUTHORIZE = "https://discord.com/oauth2/authorize"
DISCORD_OAUTH_TOKEN = f"{DISCORD_API_BASE}/oauth2/token"


# ---------------------------------------------------------------------------
# Internal helpers (patched in tests)
# ---------------------------------------------------------------------------


async def _exchange_code_for_token(code: str) -> str:
    """Exchange an authorization code for a Discord access token."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            DISCORD_OAUTH_TOKEN,
            data={
                "client_id": settings.discord_client_id,
                "client_secret": settings.discord_client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.discord_redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        return response.json()["access_token"]


async def _get_discord_user(access_token: str) -> dict:
    """Fetch the authenticated Discord user's profile (identify scope)."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{DISCORD_API_BASE}/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()


async def _check_guild_membership(discord_id: str) -> dict:
    """Check guild membership via the bot sidecar. Raises on connection failure."""
    return await bot_client.get_member(discord_id)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/login")
async def login(response: Response) -> dict:
    """Start the Discord OAuth2 flow.

    Returns the Discord authorization URL. Sets a short-lived ``oauth_state``
    cookie containing a CSPRNG nonce for CSRF protection.
    """
    state = secrets.token_hex(32)

    params = urlencode({
        "client_id": settings.discord_client_id,
        "redirect_uri": settings.discord_redirect_uri,
        "response_type": "code",
        "scope": "identify",
        "state": state,
    })
    url = f"{DISCORD_OAUTH_AUTHORIZE}?{params}"

    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        max_age=300,
        samesite="lax",
        secure=settings.environment != "development",
    )
    return {"url": url}


@router.get("/callback")
async def callback(
    code: str,
    state: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle the Discord OAuth2 callback.

    Validates state, exchanges code for token, verifies guild membership,
    matches the member record by ``discord_id`` only (no username fallback),
    and issues a 24-hour JWT in an HttpOnly session cookie.
    """
    # 1. Validate state (CSRF protection)
    stored_state = request.cookies.get("oauth_state", "")
    if not stored_state or not secrets.compare_digest(stored_state, state):
        logger.warning("auth_invalid_state")
        return _error_redirect("invalid_state")

    # 2. Exchange code for access token
    try:
        access_token = await _exchange_code_for_token(code)
    except httpx.HTTPError:
        logger.error("auth_token_exchange_failed", exc_info=True)
        return _error_redirect("service_unavailable")

    # 3. Get Discord user profile
    try:
        discord_user = await _get_discord_user(access_token)
    except httpx.HTTPError:
        logger.error("auth_discord_user_fetch_failed", exc_info=True)
        return _error_redirect("service_unavailable")

    discord_id = discord_user["id"]

    # 4. Verify guild membership via bot sidecar
    try:
        guild_check = await _check_guild_membership(discord_id)
    except httpx.HTTPError:
        logger.error("auth_guild_check_failed", extra={"discord_id": discord_id}, exc_info=True)
        return _error_redirect("service_unavailable")

    if not guild_check.get("is_member"):
        logger.warning("auth_guild_check_rejected", extra={"discord_id": discord_id})
        return _error_redirect("unauthorized")

    # 5. Match member by discord_id only — no username fallback
    result = await db.execute(
        select(Member).where(Member.discord_id == discord_id)
    )
    member = result.scalar_one_or_none()

    if not member:
        logger.warning("auth_member_not_found", extra={"discord_id": discord_id})
        return _error_redirect("unauthorized")

    # 6. Issue JWT
    now = datetime.now(timezone.utc)
    token_payload = {
        "sub": str(member.id),
        "name": member.name,
        "iat": now,
        "exp": now + timedelta(hours=24),
    }
    token = jwt.encode(token_payload, settings.session_secret, algorithm="HS256")

    # 7. Set session cookie and redirect to frontend
    redirect = RedirectResponse(url="/", status_code=307)
    redirect.set_cookie(
        key="session",
        value=token,
        httponly=True,
        max_age=86400,
        samesite="lax",
        secure=settings.environment != "development",
    )
    # Clear the oauth_state cookie
    redirect.delete_cookie(key="oauth_state")
    return redirect


@router.post("/logout")
async def logout(response: Response) -> dict:
    """Clear the session cookie."""
    response.delete_cookie(key="session")
    return {"status": "logged_out"}


@router.get("/me")
async def me(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the authenticated user's info."""
    role = None
    discord_id = None
    if current_user.member_id:
        member = await db.get(Member, current_user.member_id)
        if member:
            role = member.role.value if member.role else None
            discord_id = member.discord_id
    return {
        "member_id": current_user.member_id,
        "name": current_user.name,
        "role": role,
        "discord_id": discord_id,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _error_redirect(error: str) -> RedirectResponse:
    """Build a redirect to /login with an error query parameter."""
    return RedirectResponse(url=f"/login?error={error}", status_code=307)
```

- [ ] **Step 4: Register the auth router in main.py**

Add to `backend/app/main.py`:

```python
from app.api.auth import router as auth_router
```

And register it as a public route (no auth dependency):

```python
app.include_router(auth_router, prefix="/api")
```

- [ ] **Step 5: Run all auth tests**

Run: `cd backend && python -m pytest tests/test_auth.py -v`
Expected: All tests pass.

- [ ] **Step 6: Run the full backend test suite**

Run: `cd backend && python -m pytest --ignore=tests/test_schema.py -v`
Expected: All tests pass. If any existing tests now fail with 401, fix them by adding `monkeypatch.setattr("app.config.settings.auth_disabled", True)` to their setup or fixture.

- [ ] **Step 7: Commit**

```
git add backend/app/api/auth.py backend/app/main.py backend/tests/test_auth.py
git commit -m "feat(auth): add Discord OAuth2 endpoints (login, callback, logout, me)

Authorization Code Grant flow with identify scope. State cookie for CSRF.
Guild membership verified via bot sidecar. Member matched by discord_id
only (no username fallback). 24-hour JWT in HttpOnly cookie.

Refs discord-auth-plan.md Phase A1"
```

---

## Task 4 — Completed: Frontend AuthContext and 401 interceptor

**Files:**
- Create: `frontend/src/context/AuthContext.tsx`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/test/utils.tsx`
- Test: `frontend/src/test/context/AuthContext.test.tsx`

The auth context fetches `/api/auth/me` on mount to determine login state. The Axios interceptor catches 401 responses and redirects to `/login`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/test/context/AuthContext.test.tsx`:

```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeAll, afterAll, afterEach, describe, it, expect } from "vitest";
import { server } from "../server";
import { renderWithProviders } from "../utils";
import { useAuth } from "../../context/AuthContext";

beforeAll(() => server.listen({ onUnhandledRequest: "warn" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function TestConsumer() {
  const { user, isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <div>Loading...</div>;
  if (!isAuthenticated) return <div>Not authenticated</div>;
  return <div>Hello {user?.name}</div>;
}

describe("AuthContext", () => {
  it("shows loading state initially then resolves to authenticated", async () => {
    server.use(
      http.get("/api/auth/me", () =>
        HttpResponse.json({
          member_id: 1,
          name: "TestUser",
          is_service: false,
        }),
      ),
    );

    renderWithProviders(<TestConsumer />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Hello TestUser")).toBeInTheDocument();
    });
  });

  it("resolves to not authenticated on 401", async () => {
    server.use(
      http.get("/api/auth/me", () =>
        new HttpResponse(null, { status: 401 }),
      ),
    );

    renderWithProviders(<TestConsumer />);
    await waitFor(() => {
      expect(screen.getByText("Not authenticated")).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/test/context/AuthContext.test.tsx`
Expected: FAIL — module not found `../../context/AuthContext`

- [ ] **Step 3: Implement AuthContext**

Create `frontend/src/context/AuthContext.tsx`:

```tsx
import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import apiClient from "../api/client";

interface AuthUser {
  member_id: number | null;
  name: string;
  role: string | null;
  discord_id: string | null;
}

interface AuthContextValue {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    apiClient
      .get("/api/auth/me")
      .then((res) => {
        if (!cancelled) setUser(res.data);
      })
      .catch(() => {
        if (!cancelled) setUser(null);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const logout = useCallback(async () => {
    await apiClient.post("/api/auth/logout");
    setUser(null);
    window.location.href = "/login";
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: user !== null,
        isLoading,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
```

- [ ] **Step 4: Add 401 interceptor to API client**

Modify `frontend/src/api/client.ts`:

```typescript
import axios from "axios";

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "",
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (
      error.response?.status === 401 &&
      !window.location.pathname.startsWith("/login") &&
      !error.config?.url?.includes("/api/auth/me")
    ) {
      window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);

export default apiClient;
```

Note: The `/api/auth/me` exclusion prevents an infinite redirect loop — when `AuthContext` calls `/me` and gets 401, it should set `user = null` (not redirect), so `RequireAuth` can handle the redirect.

- [ ] **Step 5: Add AuthProvider to test wrapper**

Modify `frontend/src/test/utils.tsx` — wrap with `AuthProvider`:

```tsx
import { type ReactNode } from "react";
import { render, type RenderOptions } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, type MemoryRouterProps } from "react-router-dom";
import { AuthProvider } from "../context/AuthContext";

interface TestRenderOptions extends Omit<RenderOptions, "wrapper"> {
  initialEntries?: MemoryRouterProps["initialEntries"];
}

export function renderWithProviders(
  ui: ReactNode,
  { initialEntries = ["/"], ...renderOptions }: TestRenderOptions = {},
) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={initialEntries}>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>{children}</AuthProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );
  }

  return render(ui, { wrapper: Wrapper, ...renderOptions });
}

export * from "@testing-library/react";
```

- [ ] **Step 6: Add `/api/auth/me` handler to default MSW handlers**

Modify `frontend/src/test/handlers.ts` — add a default handler for `/api/auth/me` that returns 401 (unauthenticated by default; individual tests override as needed):

```typescript
// Add to the handlers array:
http.get('/api/auth/me', () => new HttpResponse(null, { status: 401 })),
```

- [ ] **Step 7: Run AuthContext tests**

Run: `cd frontend && npx vitest run src/test/context/AuthContext.test.tsx`
Expected: All tests pass.

- [ ] **Step 8: Run the full frontend test suite**

Run: `cd frontend && npx vitest run`
Expected: All existing tests still pass. If any fail because `AuthProvider` is now in the wrapper and tries to call `/api/auth/me`, the default MSW handler (401) should make `AuthContext` resolve to unauthenticated, which shouldn't break tests for individual pages. If tests fail, add an authenticated `/api/auth/me` handler override in those specific test files.

- [ ] **Step 9: Commit**

```
git add frontend/src/context/AuthContext.tsx frontend/src/api/client.ts frontend/src/test/utils.tsx frontend/src/test/handlers.ts frontend/src/test/context/
git commit -m "feat(auth): add AuthContext, useAuth hook, and 401 interceptor

AuthProvider fetches /api/auth/me on mount. 401 interceptor redirects
to /login (excludes /me endpoint to avoid loops). Test wrapper updated.

Refs discord-auth-plan.md Phase B1"
```

---

## Task 5 — Completed: LoginPage

**Files:**
- Create: `frontend/src/pages/LoginPage.tsx`
- Test: `frontend/src/test/pages/LoginPage.test.tsx`

Minimal login page with Discord brand button, privacy disclosure, and error message handling.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/test/pages/LoginPage.test.tsx`:

```tsx
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeAll, afterAll, afterEach, describe, it, expect, vi } from "vitest";
import { server } from "../server";
import { renderWithProviders } from "../utils";
import LoginPage from "../../pages/LoginPage";

beforeAll(() => server.listen({ onUnhandledRequest: "warn" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("LoginPage", () => {
  it("renders the sign-in button and privacy disclosure", async () => {
    renderWithProviders(<LoginPage />, { initialEntries: ["/login"] });

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /sign in with discord/i }),
      ).toBeInTheDocument();
    });
    expect(screen.getByText(/username and avatar/i)).toBeInTheDocument();
  });

  it("shows unauthorized error message", async () => {
    renderWithProviders(<LoginPage />, {
      initialEntries: ["/login?error=unauthorized"],
    });

    await waitFor(() => {
      expect(
        screen.getByText(/not authorized to access this app/i),
      ).toBeInTheDocument();
    });
  });

  it("shows service unavailable error message", async () => {
    renderWithProviders(<LoginPage />, {
      initialEntries: ["/login?error=service_unavailable"],
    });

    await waitFor(() => {
      expect(
        screen.getByText(/temporarily unavailable/i),
      ).toBeInTheDocument();
    });
  });

  it("shows generic error for unknown error codes", async () => {
    renderWithProviders(<LoginPage />, {
      initialEntries: ["/login?error=invalid_state"],
    });

    await waitFor(() => {
      expect(
        screen.getByText(/not authorized to access this app/i),
      ).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/test/pages/LoginPage.test.tsx`
Expected: FAIL — module not found `../../pages/LoginPage`

- [ ] **Step 3: Implement LoginPage**

Create `frontend/src/pages/LoginPage.tsx`:

```tsx
import { useSearchParams } from "react-router-dom";
import apiClient from "../api/client";
import { Shield } from "lucide-react";

const ERROR_MESSAGES: Record<string, string> = {
  service_unavailable:
    "Login is temporarily unavailable. Please try again in a moment.",
};
const DEFAULT_ERROR = "You are not authorized to access this app.";

export default function LoginPage() {
  const [searchParams] = useSearchParams();
  const error = searchParams.get("error");

  const handleLogin = async () => {
    const { data } = await apiClient.get("/api/auth/login");
    window.location.href = data.url;
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <div className="w-full max-w-sm space-y-6 rounded-lg border border-slate-200 bg-white p-8 shadow-sm">
        <div className="flex flex-col items-center gap-2">
          <Shield className="h-8 w-8 text-violet-600" />
          <h1 className="text-xl font-semibold text-slate-900">
            Siege Assignments
          </h1>
        </div>

        {error && (
          <div className="rounded-md bg-red-50 p-3 text-center text-sm text-red-700">
            {ERROR_MESSAGES[error] ?? DEFAULT_ERROR}
          </div>
        )}

        <div className="space-y-4">
          <button
            onClick={handleLogin}
            className="flex w-full items-center justify-center gap-2 rounded-md px-4 py-2.5 text-sm font-medium text-white transition-colors"
            style={{ backgroundColor: "#5865F2" }}
          >
            Sign in with Discord
          </button>

          <p className="text-center text-xs text-slate-500">
            We only request access to your Discord username and avatar. Guild
            membership is verified privately using our bot.
          </p>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/test/pages/LoginPage.test.tsx`
Expected: All tests pass.

- [ ] **Step 5: Commit**

```
git add frontend/src/pages/LoginPage.tsx frontend/src/test/pages/LoginPage.test.tsx
git commit -m "feat(auth): add LoginPage with Discord button and error handling

Shows privacy disclosure, brand-colored button, and contextual error
messages (service_unavailable vs generic unauthorized).

Refs discord-auth-plan.md Phase B2"
```

---

## Task 6 — Completed: RequireAuth wrapper and route wiring

**Files:**
- Create: `frontend/src/components/RequireAuth.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Layout.tsx`

Wire up route protection and add user display + sign-out to the nav bar.

- [ ] **Step 1: Create RequireAuth component**

Create `frontend/src/components/RequireAuth.tsx`:

```tsx
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-slate-500">Loading...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
```

- [ ] **Step 2: Update App.tsx — add /login route and wrap protected routes**

Replace `frontend/src/App.tsx`:

```tsx
import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import RequireAuth from "./components/RequireAuth";
import SiegeLayout from "./components/SiegeLayout";
import LoginPage from "./pages/LoginPage";
import MembersPage from "./pages/MembersPage";
import MemberDetailPage from "./pages/MemberDetailPage";
import SiegesPage from "./pages/SiegesPage";
import SiegeCreatePage from "./pages/SiegeCreatePage";
import SiegeSettingsPage from "./pages/SiegeSettingsPage";
import BoardPage from "./pages/BoardPage";
import PostsPage from "./pages/PostsPage";
import SiegeMembersPage from "./pages/SiegeMembersPage";
import ComparisonPage from "./pages/ComparisonPage";
import PostPrioritiesPage from "./pages/PostPrioritiesPage";
import SystemPage from "./pages/SystemPage";

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<Navigate to="/sieges" replace />} />
        <Route path="/members" element={<MembersPage />} />
        <Route path="/members/new" element={<MemberDetailPage />} />
        <Route path="/members/:id" element={<MemberDetailPage />} />
        <Route path="/sieges" element={<SiegesPage />} />
        <Route path="/sieges/new" element={<SiegeCreatePage />} />
        <Route path="/sieges/:id" element={<SiegeLayout />}>
          <Route index element={<SiegeSettingsPage />} />
          <Route path="board" element={<BoardPage />} />
          <Route path="posts" element={<PostsPage />} />
          <Route path="members" element={<SiegeMembersPage />} />
          <Route path="compare" element={<ComparisonPage />} />
        </Route>
        <Route path="/post-priorities" element={<PostPrioritiesPage />} />
        <Route path="/system" element={<SystemPage />} />
      </Route>
    </Routes>
  );
}

export default App;
```

- [ ] **Step 3: Add user display + sign out to Layout nav bar**

Modify `frontend/src/components/Layout.tsx`:

Add import at top:

```tsx
import { useAuth } from "../context/AuthContext";
import { LogOut } from "lucide-react";
```

Inside the `Layout` component, before the return, add:

```tsx
const { user, logout } = useAuth();
```

Replace the `<div className="ml-auto">` section (the System link and its wrapper) with:

```tsx
<div className="ml-auto flex items-center gap-2">
  <NavLink
    to="/system"
    className={({ isActive }) =>
      cn(
        "flex items-center gap-1.5 rounded-md px-3 py-2 text-sm font-medium transition-colors",
        isActive
          ? "bg-slate-100 text-slate-900"
          : "text-slate-400 hover:bg-slate-50 hover:text-slate-600",
      )
    }
  >
    <Info className="h-3.5 w-3.5" />
    System
  </NavLink>

  {user && (
    <>
      <span className="text-sm text-slate-500">{user.name}</span>
      <button
        onClick={logout}
        className="flex items-center gap-1 rounded-md px-2 py-1.5 text-sm text-slate-400 transition-colors hover:bg-slate-50 hover:text-slate-600"
        title="Sign out"
      >
        <LogOut className="h-3.5 w-3.5" />
      </button>
    </>
  )}
</div>
```

- [ ] **Step 4: Wrap the app root with AuthProvider**

Check `frontend/src/main.tsx` — the `AuthProvider` needs to wrap the app. Modify `frontend/src/main.tsx`:

Add import:
```tsx
import { AuthProvider } from "./context/AuthContext";
```

Wrap `<App />` with `<AuthProvider>`:
```tsx
<BrowserRouter>
  <QueryClientProvider client={queryClient}>
    <AuthProvider>
      <App />
    </AuthProvider>
  </QueryClientProvider>
</BrowserRouter>
```

- [ ] **Step 5: Run the full frontend test suite**

Run: `cd frontend && npx vitest run`
Expected: All tests pass. The `AuthProvider` in the test wrapper + the default 401 handler for `/api/auth/me` means existing page tests render in an unauthenticated state — which triggers `RequireAuth` to redirect to `/login`. If page tests break because `RequireAuth` redirects them, override the `/api/auth/me` handler in those tests:

```tsx
server.use(
  http.get("/api/auth/me", () =>
    HttpResponse.json({ member_id: 1, name: "TestUser", role: "heavy_hitter", discord_id: "111222333" }),
  ),
);
```

Add this override to the `beforeEach` (or inline `server.use`) in each existing page test file that needs it:
- `SiegesPage.test.tsx`
- `MembersPage.test.tsx`
- `SiegeLayout.test.tsx`
- `BoardPage.test.tsx`
- `SiegeSettingsPage.test.tsx`
- `PostsTab.test.tsx`

- [ ] **Step 6: Commit**

```
git add frontend/src/components/RequireAuth.tsx frontend/src/App.tsx frontend/src/components/Layout.tsx frontend/src/main.tsx
git commit -m "feat(auth): add RequireAuth wrapper, /login route, user display in nav

Protected routes redirect to /login when unauthenticated. Layout shows
username and sign-out button. AuthProvider wraps app root.

Refs discord-auth-plan.md Phase B3"
```

---

## Task 7 — Completed: Fix existing frontend tests for auth

**Files:**
- Modify: `frontend/src/test/handlers.ts`
- Modify: All existing test files that break

After Task 6, existing page tests may fail because `RequireAuth` redirects unauthenticated users. This task fixes them by adding an authenticated `/api/auth/me` handler.

- [ ] **Step 1: Change the default MSW handler to return authenticated**

The simplest fix is to change the default handler in `frontend/src/test/handlers.ts` to return an authenticated user by default (tests that need unauthenticated state can override):

```typescript
http.get('/api/auth/me', () =>
  HttpResponse.json({ member_id: 1, name: "TestUser", role: "heavy_hitter", discord_id: "111222333" }),
),
```

- [ ] **Step 2: Run the full frontend test suite**

Run: `cd frontend && npx vitest run`
Expected: All tests pass. If any still fail, investigate and fix.

- [ ] **Step 3: Update AuthContext tests to override the default handler**

The "resolves to not authenticated on 401" test in `AuthContext.test.tsx` needs to override the default authenticated handler:

```tsx
it("resolves to not authenticated on 401", async () => {
  server.use(
    http.get("/api/auth/me", () => new HttpResponse(null, { status: 401 })),
  );
  // ... rest of test
});
```

This should already be the case since the test uses `server.use()` inline, which overrides the default handler.

- [ ] **Step 4: Run all tests one final time**

Run: `cd frontend && npx vitest run`
Expected: All tests pass.

- [ ] **Step 5: Commit**

```
git add frontend/src/test/
git commit -m "fix(auth): update test fixtures for auth-protected routes

Default MSW handler returns authenticated user so existing page tests
continue to work with RequireAuth wrapper in place.

Refs discord-auth-plan.md Phase B4"
```

---

## Task 8 — Completed: Final verification and documentation

**Files:**
- Modify: `docs/STATUS.md`

- [ ] **Step 1: Run the full backend test suite**

Run: `cd backend && python -m pytest --ignore=tests/test_schema.py -v`
Expected: All tests pass.

- [ ] **Step 2: Run the full frontend test suite**

Run: `cd frontend && npx vitest run`
Expected: All tests pass.

- [ ] **Step 3: Run lint on both sides**

Run: `cd backend && black --check . && ruff check .`
Run: `cd frontend && npx eslint src/ && npx prettier --check src/`
Expected: No lint errors. Fix any that appear.

- [ ] **Step 4: Manual smoke test (if docker-compose is available)**

Run: `docker-compose up --build`

Verify:
1. `http://localhost:5173` → redirects to `/login`
2. Login page shows Discord button and privacy disclosure
3. With `AUTH_DISABLED=true` in `.env` + `ENVIRONMENT=development`: all routes accessible, nav shows "dev-user"

- [ ] **Step 5: Update STATUS.md**

Add a note that Discord OAuth2 auth is implemented. Update the phase status.

- [ ] **Step 6: Commit**

```
git add docs/STATUS.md
git commit -m "docs: update STATUS.md with auth implementation completion"
```
