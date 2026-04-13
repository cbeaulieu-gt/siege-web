# Discord OAuth2 Integration Plan

## Context

The app currently has zero authentication — all API endpoints and UI routes are fully open. This plan implements Discord OAuth2 as the login mechanism for v1.0, using the standard Authorization Code Grant flow. Discord is the natural fit since all users are already clan members in a Discord server and the app already has a bot running in the guild.

### Decisions locked in

- **JWT TTL**: 24 hours, no refresh — re-authenticate daily
- **Rejected user UX**: "You are not authorized to access this app." (generic, no detail)
- **Dev bypass**: `AUTH_DISABLED=true` env var — skips auth for local development only; enforced by runtime startup guard
- **Service token path**: Auth middleware supports both user cookies and `Authorization: Bearer <token>` for the bot's future standalone extraction
- **No username fallback**: Member matching uses `discord_id` only. Pre-launch checklist requires Discord sync to be run and verified (zero NULL `discord_id` rows) before auth is enabled. See issue #125.
- **Forced revocation**: Deleting a Member record is the revocation mechanism. The per-request `db.get(Member, member_id)` check returns `None` → 401. Document in RUNBOOK.md.
- **CSRF protection**: The state nonce (`secrets.token_hex(32)`) is the real CSRF defense. `SameSite=Lax` on the state cookie adds defense-in-depth but does not protect GET callbacks from top-level cross-origin navigations.

---

## Discord Scopes — Minimal and Transparent

**Scope requested: `identify` only.**

The authorization consent screen will show:
> *"This will allow [app] to: Know who you are (your Discord username and avatar)."*

That's it. No server list. No email. No message access. This is the most minimal possible OAuth2 grant.

Guild membership and roles are verified **server-side** using the bot token — not via the user's OAuth token. The backend calls the bot sidecar after login to confirm the user is in the guild. Users never grant access to that check; it happens transparently using the bot's existing guild permissions.

**Why this is better than `guilds` scope:**
- `guilds` scope exposes the user's full list of Discord servers to the app — invasive and unnecessary
- `guilds.members.read` is narrower but still asks users to grant guild data
- `identify` + bot-side check is the minimal and most privacy-respecting approach

---

## Architecture

### OAuth2 Flow

```
1. User clicks "Login with Discord" on /login page
2. Frontend: GET /api/auth/login → gets Discord OAuth URL
   (secrets.token_hex(32) nonce stored in short-lived cookie for CSRF)
3. Browser redirects to Discord authorization page
   Scope shown to user: "Know who you are (username + avatar)"
4. Discord redirects to: GET /api/auth/callback?code=...&state=...
5. Backend: validates state cookie (CSRF — nonce is the actual protection)
6. Backend: exchanges code for access token via Discord token endpoint
7. Backend: calls GET /users/@me (identify scope) → gets discord_id
8. Backend: calls bot sidecar GET /api/members/{discord_id}
   - Bot unreachable / HTTP error → 503, redirect /login?error=service_unavailable
   - is_member=false → redirect /login?error=unauthorized
   - is_member=true but user lacks the role named by DISCORD_REQUIRED_ROLE → redirect /login?error=unauthorized
   (DISCORD_REQUIRED_ROLE defaults to "Clan Deputies"; exact case-sensitive match against the member's role names)
9. Backend: matches Member WHERE discord_id = discord_id only (NO username fallback)
   - No match → redirect /login?error=unauthorized
10. Backend: issues 24-hour JWT in HttpOnly/Secure/SameSite=Lax cookie
    Redirects browser to frontend /
11. Frontend AuthContext: calls GET /api/auth/me on load → populates user context
```

### Auth Middleware

The `get_current_user` FastAPI dependency checks in this order:
1. **`AUTH_DISABLED=true`** → return stub user `{member_id: None, name: "dev-user", is_service: False}` *(development only — enforced by startup guard)*
2. **`Authorization: Bearer <token>`** → if matches `settings.bot_service_token`, use `secrets.compare_digest` → return service principal `{member_id: None, name: "bot-service", is_service: True}`
3. **`Cookie: session=<jwt>`** → decode JWT, db.get(Member, id) → return authenticated user
4. **Else** → raise HTTP 401

Applied to all routes except: `/api/health`, `/api/version`, `/api/auth/*`

### Concurrent User Safety

The design is stateless — **no shared mutable session state**. Each request independently:
- Decodes its own JWT (CPU-only, no DB for verification)
- Does a single `db.get(Member, member_id)` lookup using the async connection pool

There are no race conditions because there is no server-side session to coordinate. Simultaneous logins, logouts, and authenticated requests are all independent operations.

**Edge case handled:** If a Member record is deleted while a user is logged in, `db.get(Member, member_id)` returns `None` and the request gets a 401. The next request will redirect to `/login`. This is the intended forced-revocation mechanism — document in RUNBOOK.md as "To immediately revoke a member's access, delete their Member record."

**`AUTH_DISABLED` stub note:** The stub user has `member_id=None` and `is_service=False`. Any code path that accesses `current_user.member_id` must handle `None` in dev mode.

---

## AUTH_DISABLED Production Guard

**Approach: runtime startup guard (not CI grep)**

Why not a CI check: Environment variables in deployed Container Apps come from Key Vault references and GitHub Environment secrets — not from committed files. A CI grep cannot catch runtime misconfiguration.

**`environment` must be a required field with no default** in `Settings`. This closes the failure mode where a deployment with `ENVIRONMENT` unset would default to `"development"` and silently permit `AUTH_DISABLED=true`.

**Implementation in `backend/app/main.py`** using FastAPI lifespan:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.auth_disabled and settings.environment != "development":
        raise RuntimeError(
            "AUTH_DISABLED=true is not permitted outside development. "
            f"Current environment: {settings.environment}"
        )
    yield

app = FastAPI(..., lifespan=lifespan)
```

If `AUTH_DISABLED=true` ends up in any non-development Container App, the container will **refuse to start**. The health check fails, the Container App stays in restart loop, and the deployment is visibly broken — not silently insecure. Because `environment` has no default, an unset `ENVIRONMENT` variable causes startup to fail before even reaching the guard.

---

## Bot Sidecar Extension

The backend cannot call Discord API directly (it does not have `DISCORD_TOKEN`). Guild membership is verified through the bot sidecar, which already has the bot token.

**New endpoint on bot sidecar (`bot/app/http_api.py`):**

```
GET /api/members/{discord_user_id}
Authorization: Bearer <BOT_API_KEY>
```

**Critical: use `await guild.fetch_member()` (API call), not `guild.get_member()` (cache-only).** The cache-only lookup will return `None` for members who joined after the last cache sync, producing false rejections. `fetch_member` is authoritative and the latency (~100ms) is acceptable for a once-per-24-hours login operation.

```python
@router.get("/api/members/{discord_user_id}")
async def get_guild_member(
    discord_user_id: str,
    _: None = Depends(verify_api_key),
):
    guild = bot.get_guild(int(settings.discord_guild_id))
    if guild is None:
        raise HTTPException(status_code=503, detail="Guild not available")
    try:
        member = await guild.fetch_member(int(discord_user_id))
    except discord.NotFound:
        return {"is_member": False}
    except discord.HTTPException as e:
        raise HTTPException(status_code=503, detail=f"Discord API error: {e}")
    return {
        "is_member": True,
        "discord_id": str(member.id),
        "username": member.name,
        "display_name": member.display_name,
        "roles": [str(r.id) for r in member.roles if r.name != "@everyone"],
    }
```

> **Role gating note:** the callback uses the `roles` list returned above (role IDs) together with `DISCORD_REQUIRED_ROLE` (a role *name*) to verify access. The backend resolves role names via a separate `fetch_member` lookup or by including role names in the sidecar response. If the required role is absent from the member's roles, the callback redirects to `/login?error=unauthorized` — the same path as a non-member. `DISCORD_REQUIRED_ROLE` defaults to `"Clan Deputies"` but is fully configurable; self-hosters should set it to whatever Discord role their clan uses for siege managers.

**New method on `backend/app/services/bot_client.py`:**

`get_member` must **raise** `httpx.HTTPError` on connection failure (not swallow it). The callback distinguishes:
- `{"is_member": false}` → user not in guild → reject as unauthorized
- `httpx.HTTPError` / HTTP 503 from bot → sidecar outage → surface as `service_unavailable`

```python
async def get_member(self, discord_user_id: str) -> dict:
    """
    Check guild membership via bot sidecar.
    Returns {"is_member": bool, ...}.
    Raises httpx.HTTPError if the sidecar is unreachable.
    """
    async with self._make_client() as client:
        response = await client.get(f"/api/members/{discord_user_id}")
        response.raise_for_status()
        return response.json()
```

---

## Implementation

### New Dependencies

**`backend/requirements.txt`** — add:
- `PyJWT>=2.9` — JWT encoding/decoding
- `cryptography>=43` — required by PyJWT for HS256

**`backend/requirements-dev.txt`** — add:
- `respx>=0.21` — mock httpx calls in tests

No new frontend dependencies needed.

---

### Phase A3 — Backend Config (do first, unblocks everything)

**File: `backend/app/config.py`** — changes to `Settings`:
```python
# Remove default from environment — must be explicitly set
environment: str  # no default; deployment must set ENVIRONMENT explicitly

# Add auth fields
discord_client_id: str
discord_client_secret: str
discord_redirect_uri: str
session_secret: str          # HS256 signing key for JWTs
bot_service_token: str = ""  # Bearer token for future bot→backend calls; empty = disabled
auth_disabled: bool = False  # Dev bypass; startup guard rejects True outside development
```

**File: `.env.example`** — add section:
```env
# Discord OAuth2 (register app at discord.com/developers/applications)
DISCORD_CLIENT_ID=your-discord-app-client-id
DISCORD_CLIENT_SECRET=your-discord-app-client-secret
DISCORD_REDIRECT_URI=http://localhost:8000/api/auth/callback
SESSION_SECRET=changeme-use-a-long-random-string-in-production

# Service auth (for future bot→backend calls when bot is extracted to standalone)
BOT_SERVICE_TOKEN=

# Dev auth bypass — backend WILL NOT START if this is set outside development environment
# AUTH_DISABLED=true
```

---

### Phase A0 — Bot Sidecar: Guild Member Lookup Endpoint (S, unblocks A1)

**File: `bot/app/http_api.py`** — add endpoint as shown in Bot Sidecar Extension section above.

**File: `bot/tests/`** — add tests:
- Happy path: member in guild → `{"is_member": true, ...}`
- Not in guild: `discord.NotFound` → `{"is_member": false}`
- Discord API error: `discord.HTTPException` → 503
- Auth: missing/wrong Bearer token → 401

---

### Phase A1 — Backend Auth Endpoints (L)

**New file: `backend/app/api/auth.py`**

Router prefix: `/api/auth`. No auth dependency on this router.

#### `GET /api/auth/login`
- Generate nonce: `secrets.token_hex(32)` (64-char hex, CSPRNG)
- Store in response cookie: `oauth_state=<nonce>` (httponly, max_age=300, samesite=lax)
- Build and return Discord OAuth URL with scope=`identify` only
- Return `{"url": "<discord-oauth-url>"}`

#### `GET /api/auth/callback?code=...&state=...`
Steps:
1. Read `oauth_state` cookie; compare to `state` param using `secrets.compare_digest` → redirect `/login?error=invalid_state` if mismatch
2. Clear `oauth_state` cookie in response
3. POST to `https://discord.com/api/oauth2/token` (form-encoded) → get access token
4. GET `https://discord.com/api/users/@me` → get `id` (discord_id)
5. Call `await bot_client.get_member(discord_id)`:
   - `httpx.HTTPError` or 503 from bot → `logger.error("auth_guild_check_failed", discord_id=..., error=...)` → redirect `/login?error=service_unavailable`
   - `is_member=False` → `logger.warning("auth_guild_check_rejected", discord_id=...)` → redirect `/login?error=unauthorized`
6. `SELECT * FROM member WHERE discord_id = ?` — **no username fallback**
   - No match → `logger.warning("auth_member_not_found", discord_id=...)` → redirect `/login?error=unauthorized`
7. Issue JWT with `secrets`-derived payload, signed with HS256
8. Set session cookie (httponly, secure=(env!="development"), samesite=lax, max_age=86400)
9. Redirect to frontend `/`

#### `POST /api/auth/logout`
- Set `session` cookie with max_age=0
- Return `{"status": "logged_out"}`

#### `GET /api/auth/me`
- Explicitly uses `get_current_user` dependency
- Returns: `{"member_id": int | None, "name": str, "role": str | None, "discord_id": str | None}`

---

### Phase A2 — Auth Middleware (M)

**New file: `backend/app/dependencies/auth.py`**

```python
import secrets
from dataclasses import dataclass
import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.member import Member
from app.config import settings

@dataclass
class AuthenticatedUser:
    member_id: int | None
    name: str
    is_service: bool

async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthenticatedUser:

    # 1. Dev bypass
    if settings.auth_disabled:
        return AuthenticatedUser(member_id=None, name="dev-user", is_service=False)

    # 2. Service token (Bearer) — timing-safe comparison
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer ") and settings.bot_service_token:
        provided = auth_header.removeprefix("Bearer ")
        if secrets.compare_digest(provided, settings.bot_service_token):
            return AuthenticatedUser(member_id=None, name="bot-service", is_service=True)

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

Apply `Depends(get_current_user)` to all existing routers in `backend/app/main.py`. Health, version, and auth routers are registered without it.

---

### Phase A4 — Backend Auth Tests (M)

**New file: `backend/tests/test_auth.py`**

Uses `pytest-asyncio` + `httpx.AsyncClient` + `respx` for mocking Discord API and bot sidecar calls.

Test cases:
- `test_login_returns_discord_url_and_state_cookie` — nonce is 64 hex chars, cookie set
- `test_callback_happy_path` — valid code+state → session cookie set, redirect to /
- `test_callback_invalid_state` — mismatched state → error redirect
- `test_callback_bot_unreachable` — `httpx.HTTPError` from bot → `service_unavailable` redirect (NOT unauthorized)
- `test_callback_not_in_guild` — `is_member=false` → `unauthorized` redirect
- `test_callback_no_matching_member` — discord_id not in DB → `unauthorized` redirect (no username fallback)
- `test_callback_no_username_fallback` — discord_id null in DB, username matches → still rejected
- `test_logout_clears_cookie`
- `test_me_with_valid_session` → returns member info
- `test_me_with_expired_token` → 401
- `test_me_with_service_token` → 200 as service principal
- `test_service_token_timing_safe` — verify `secrets.compare_digest` used (not `==`)
- `test_protected_route_no_auth` → 401
- `test_protected_route_with_valid_cookie` → 200
- `test_auth_disabled_bypass` — `AUTH_DISABLED=true` with `ENVIRONMENT=development` → accessible
- `test_startup_rejects_auth_disabled_in_non_dev` — lifespan raises RuntimeError when env=staging or production
- `test_startup_rejects_missing_environment` — `ENVIRONMENT` unset → pydantic validation error at startup

---

### Phase B1 — Frontend AuthContext (M)

**New file: `frontend/src/context/AuthContext.tsx`**

```typescript
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
```

- On mount: calls `GET /api/auth/me`
  - 200 → set user, `isAuthenticated = true`
  - 401 → user remains null, `isAuthenticated = false`
- `logout()`: calls `POST /api/auth/logout` → clears user state → navigate to `/login`
- Wrap entire app in `<AuthProvider>`

**Update `frontend/src/api/client.ts`** — add Axios response interceptor:
```typescript
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (
      error.response?.status === 401 &&
      !window.location.pathname.startsWith("/login")
    ) {
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);
```

---

### Phase B2 — Login Page (S)

**New file: `frontend/src/pages/LoginPage.tsx`**

- Transparent disclosure above button:
  ```
  "We only request access to your Discord username and avatar.
   Guild membership is verified privately using our bot."
  ```
- "Sign in with Discord" button (Discord brand color: #5865F2)
- On click: calls `GET /api/auth/login` → `window.location.href = data.url`
- Reads `?error=` query param:
  - `service_unavailable` → **"Login is temporarily unavailable. Please try again in a moment."**
  - Any other value (including `unauthorized`, `not_in_guild`, `invalid_state`) → **"You are not authorized to access this app."**
- If already `isAuthenticated` → redirect to `/sieges`

---

### Phase B3 — Protected Routes (S)

**New file: `frontend/src/components/RequireAuth.tsx`**

```typescript
function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <LoadingSpinner />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
```

**Update `frontend/src/App.tsx`**: add `/login` route outside `<RequireAuth>`; wrap all existing routes inside `<RequireAuth>`.

**Update `frontend/src/components/Layout.tsx`**: add username + "Sign out" button to nav bar right side.

---

### Phase B4 — Frontend Tests (S)

**New file: `frontend/src/test/context/AuthContext.test.tsx`**

- AuthContext: `isLoading` true on mount → resolves to user on 200 from `/me`
- AuthContext: user null after 401 from `/me`
- `RequireAuth`: renders children when authenticated
- `RequireAuth`: redirects to `/login` when not authenticated
- `LoginPage`: renders button + disclosure; click redirects to Discord URL
- `LoginPage`: `?error=unauthorized` → "not authorized" message
- `LoginPage`: `?error=service_unavailable` → "temporarily unavailable" message
- `LoginPage`: any other `?error=` value → "not authorized" message
- Axios interceptor: 401 response triggers redirect to `/login`

---

## File Change Summary

### New files
| File | Description |
|---|---|
| `backend/app/api/auth.py` | OAuth2 endpoints (login, callback, logout, me) |
| `backend/app/dependencies/auth.py` | `get_current_user` dependency |
| `backend/tests/test_auth.py` | Auth endpoint + middleware tests |
| `frontend/src/context/AuthContext.tsx` | Auth context + provider |
| `frontend/src/pages/LoginPage.tsx` | Login page with disclosure |
| `frontend/src/components/RequireAuth.tsx` | Route guard |
| `frontend/src/test/context/AuthContext.test.tsx` | Frontend auth tests |

### Modified files
| File | Change |
|---|---|
| `backend/app/config.py` | Remove default from `environment`; add 5 auth settings + `auth_disabled` |
| `backend/app/main.py` | Add lifespan startup guard; register auth router; apply `get_current_user` to all other routers |
| `backend/requirements.txt` | Add `PyJWT>=2.9`, `cryptography>=43` |
| `backend/requirements-dev.txt` | Add `respx>=0.21` |
| `bot/app/http_api.py` | Add `GET /api/members/{discord_user_id}` using `fetch_member` (not cache) |
| `backend/app/services/bot_client.py` | Add `get_member()` — raises on connection failure, does not swallow |
| `frontend/src/App.tsx` | Add `/login` route; wrap routes in `<RequireAuth>` |
| `frontend/src/api/client.ts` | Add 401 → `/login` interceptor |
| `frontend/src/components/Layout.tsx` | Add user display + sign out button |
| `.env.example` | Add OAuth vars, BOT_SERVICE_TOKEN, AUTH_DISABLED comment |

---

## Pre-Launch Checklist (before enabling auth in any environment)

1. Run Discord sync: `POST /api/members/discord-sync/apply`
2. Verify zero unsynced members: `SELECT COUNT(*) FROM member WHERE discord_id IS NULL` must be 0
3. Register Discord application at discord.com/developers/applications; add redirect URI
4. Set `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `DISCORD_REDIRECT_URI`, `SESSION_SECRET` in environment

If step 2 is not satisfied, members with `discord_id IS NULL` will be permanently locked out until synced.

---

## Concurrency Policy

### Auth sessions — fully safe

JWTs are stateless. Each request decodes its own token independently. No shared session state, no coordination needed. Logout clears the current browser's cookie only; other active sessions continue until expiry.

**Forced revocation**: Delete the Member record. The per-request `db.get(Member, member_id)` returns `None` → 401 on next request. Document in RUNBOOK.md.

### Data writes — last write wins (pre-existing, no change in this plan)

PostgreSQL default `READ COMMITTED` isolation, no row-level locks, no optimistic locking. Last write wins silently. Acceptable for v1.0 given single-planner workflow. Tracked as known limitation; fix path is `version` column + `WHERE version = :expected`.

---

## Blocked Issues (tracked separately)

- **#125** — `discord_username` fallback identity hijack: resolved by removing the fallback entirely (this plan has no fallback)
- **#126** — Bot sidecar outage indistinguishable from rejection: resolved by `get_member` raising on connection failure + `service_unavailable` error path

---

## Verification

1. **Dev bypass**: `AUTH_DISABLED=true` + `ENVIRONMENT=development` → all routes accessible, nav shows "dev-user"
2. **Startup guard — bad env**: `AUTH_DISABLED=true` + `ENVIRONMENT=staging` → backend refuses to start
3. **Startup guard — missing env**: `ENVIRONMENT` unset → pydantic validation error at startup
4. **Consent screen**: Discord shows only "Know who you are" — no server list, no email
5. **Happy path**: Log in with synced Discord account → session cookie set, redirected to `/sieges`, name in nav
6. **Not in guild**: Discord account not in guild → "You are not authorized to access this app."
7. **No member record**: In guild, no `discord_id` match → same "not authorized" message
8. **Bot down**: Stop bot container, attempt login → "Login is temporarily unavailable. Please try again."
9. **Forced revocation**: Delete Member record → next authenticated request → 401 → redirect to `/login`
10. **Concurrent sessions**: Two browsers logged in → both work independently
11. **Logout**: Sign out → cookie cleared → next visit redirects to `/login`
12. **Expired JWT**: Backdate JWT exp → 401 → redirect to login
13. **Service token**: `curl -H "Authorization: Bearer <BOT_SERVICE_TOKEN>" /api/members` → 200
14. **Timing-safe token**: Service token comparison uses `secrets.compare_digest`
15. **Tests**: `pytest backend/tests/test_auth.py -v` → all green; `npm test` → all green
