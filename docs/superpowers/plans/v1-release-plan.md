# v1.0 Release Candidate Plan

## Overview

This plan defines the scope, sequencing, and issue breakdown for the siege-web v1.0 release candidate. It covers everything required to go from the current state (feature-complete, no auth, no production deployment) to a production-ready application with Discord OAuth2 authentication.

---

## Current State Assessment

### What exists

| Area | Status |
|---|---|
| Member model `discord_id` column | Exists (migration 0009), exposed in API schema |
| Discord sync (preview/apply) | Fully implemented — populates `discord_id` and `discord_username` |
| CD pipeline (`deploy.yml`) | Fully wired — CI on main push, build + push to ACR, deploy to dev (main push) and prod (v-tag push), workflow_dispatch for manual deploys |
| Bicep IaC | Complete for dev + prod (ACR, PostgreSQL, Key Vault, Container Apps, App Insights, Log Analytics) |
| Authentication | None — no auth code, no Discord OAuth env vars, no frontend auth context |
| Discord OAuth env vars in `.env.example` | Missing (`DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `DISCORD_REDIRECT_URI`, `SESSION_SECRET`) |
| Discord OAuth env vars in Bicep | Missing — `main.bicep` and param files have no OAuth-related params |
| Frontend auth | No `AuthContext`, no login page, no route guards |
| Application Insights SDK | Bicep module creates the resource; SDK not yet integrated in backend/bot code |
| PR #124 (image tag preservation) | Open — fixes `infra-deploy.yml` to prevent image rollback during infra-only deploys |

### Key finding: CD pipeline is already built

The `deploy.yml` workflow is fully operational with a mature promotion model (main push builds + deploys to dev; v-tag push promotes the same SHA image to prod). This was listed as "remaining" in STATUS.md but is actually done. The remaining infra work is provisioning the prod resource group and configuring the `prod` GitHub environment secrets/variables.

### Key finding: Discord sync already populates discord_id

Issue #49 (discord_id/username sync on Member records) is implemented. The `discord_sync` service has preview/apply endpoints that write both `discord_id` and `discord_username` to Member records. The auth login flow can rely on `discord_id` matching.

---

## Milestone: v1.0 Release Candidate

**Definition of Done**: A user can log in via Discord OAuth2, access the full siege management UI behind authentication, and the application is deployed to the production Azure environment with monitoring, with a successful planner walkthrough completed.

---

## Scope

### In Scope (v1.0)

1. **Discord OAuth2 authentication** (Authorization Code Grant)
   - Backend auth endpoints (`/api/auth/login`, `/api/auth/callback`, `/api/auth/logout`, `/api/auth/me`)
   - JWT session in HttpOnly cookie
   - CSRF state parameter validation
   - FastAPI auth middleware on all existing routes (except health/version)
   - Member matching by `discord_id` at login time
   - Frontend `AuthContext`, login page, route guards, logout in nav bar
2. **Infrastructure: OAuth env vars in Bicep + Key Vault**
   - Add `discordClientId`, `discordClientSecret`, `discordRedirectUri`, `sessionSecret` to Bicep params and Key Vault
   - Update `.env.example` with new variables
3. **Infrastructure: production environment provisioning**
   - Deploy `siege-web-prod` resource group from Bicep
   - Configure `prod` GitHub environment secrets and variables
4. **Merge PR #124** (image tag preservation during infra deploys)
5. **Application Insights SDK integration** (backend + bot)
6. **Performance validation** (board load < 2s, image gen < 5s)
7. **Planner sign-off walkthrough**
8. **Smoke tests against production**
9. **48-hour post-launch monitoring**

### Out of Scope (deferred post-v1.0)

| Item | Reason |
|---|---|
| Role-based access control (Leader/Officer gating) | Issue #51 explicitly defers this; Member model already has `role` field for future use |
| RBAC middleware and UI permission checks | Depends on RBAC design decisions not yet made |
| Refresh token rotation | JWT with short TTL + re-auth on expiry is sufficient for v1; refresh tokens add complexity |
| Multi-guild support | App is single-guild by design; `DISCORD_GUILD_ID` is already configured |
| User registration (non-member login) | Only existing Member records can log in; unknown Discord users are rejected |
| Automated E2E auth tests | Manual validation for v1; automated auth E2E tests are a fast-follow |

---

## Issue Breakdown

### Phase A: Authentication (Backend)

Issues in this phase implement the Discord OAuth2 flow on the backend.

| # | Title | Description | Labels | Size | Dependencies |
|---|---|---|---|---|---|
| A1 | Backend: Discord OAuth2 endpoints | Implement `GET /api/auth/login`, `GET /api/auth/callback`, `POST /api/auth/logout`, `GET /api/auth/me`. Authorization Code Grant flow with `identify` + `guilds` scopes. Exchange code for token, fetch `/users/@me` and `/users/@me/guilds`, verify guild membership, match to Member by `discord_id`, issue signed JWT in HttpOnly/Secure/SameSite=Lax cookie. CSRF state in short-lived cookie. | `backend`, `auth`, `v1.0` | L | None |
| A2 | Backend: auth middleware for existing routes | Create `get_current_user` FastAPI dependency that validates JWT from cookie. Apply to all route registrations except `/api/health`, `/api/version`, and `/api/auth/*`. Return 401 for unauthenticated requests. | `backend`, `auth`, `v1.0` | M | A1 |
| A3 | Backend: add OAuth env vars to config | Add `discord_client_id`, `discord_client_secret`, `discord_redirect_uri`, `session_secret` to `Settings` in `config.py`. Update `.env.example`. | `backend`, `auth`, `v1.0` | S | None |
| A4 | Backend: auth endpoint tests | Unit and integration tests for all auth endpoints — happy path, invalid state, non-member rejection, expired JWT, guild membership check failure. Mock Discord API responses. | `backend`, `auth`, `testing`, `v1.0` | M | A1, A2 |

### Phase B: Authentication (Frontend)

Issues in this phase add the login UI and route protection.

| # | Title | Description | Labels | Size | Dependencies |
|---|---|---|---|---|---|
| B1 | Frontend: AuthContext and useAuth hook | Create `AuthProvider` that calls `GET /api/auth/me` on mount. Expose `user`, `isAuthenticated`, `isLoading`, `logout()` via context. Handle 401 responses globally (redirect to login). | `frontend`, `auth`, `v1.0` | M | A1 |
| B2 | Frontend: login page | New `/login` route with "Login with Discord" button. On click, fetch `/api/auth/login` to get Discord OAuth URL, then redirect. After callback completes, redirect to `/sieges`. | `frontend`, `auth`, `v1.0` | S | B1 |
| B3 | Frontend: protected route wrapper | `<RequireAuth>` component that redirects unauthenticated users to `/login`. Wrap all existing routes. Add username display and logout button to navigation bar. | `frontend`, `auth`, `v1.0` | S | B1, B2 |
| B4 | Frontend: auth component tests | Vitest tests for AuthContext (mock `/api/auth/me` responses), RequireAuth redirect behavior, login page rendering. | `frontend`, `auth`, `testing`, `v1.0` | S | B1, B2, B3 |

### Phase C: Infrastructure

Issues in this phase prepare the production environment and update IaC for auth.

| # | Title | Description | Labels | Size | Dependencies |
|---|---|---|---|---|---|
| C1 | Merge PR #124: preserve image tags during infra deploy | Review and merge the open PR that prevents infra-only deploys from rolling back container images to `:latest`. Closes #123. | `infra`, `v1.0` | S | None |
| C2 | Bicep: add Discord OAuth params to IaC | Add `discordClientId`, `discordClientSecret`, `discordRedirectUri`, `sessionSecret` params to `main.bicep`. Store secrets in Key Vault. Pass as env vars to the API container app. Update dev and prod `.bicepparam` files. | `infra`, `auth`, `v1.0` | M | A3 |
| C3 | Provision production Azure environment | Deploy `siege-web-prod` resource group using Bicep templates with prod param file. Verify all resources (PostgreSQL, Container Apps, Key Vault, ACR, App Insights, Log Analytics) are healthy. Configure `prod` GitHub environment with required secrets (`AZURE_CREDENTIALS`) and variables (`ACR_NAME`, `ACR_LOGIN_SERVER`, `RESOURCE_GROUP`). | `infra`, `v1.0` | L | C1, C2 |
| C4 | Register Discord OAuth2 application | Create the Discord application at discord.com/developers/applications. Configure OAuth2 redirect URIs for both dev and prod. Record `DISCORD_CLIENT_ID` and `DISCORD_CLIENT_SECRET`. Store in Key Vault and GitHub environment secrets. | `infra`, `auth`, `v1.0` | S | None |

### Phase D: Observability

| # | Title | Description | Labels | Size | Dependencies |
|---|---|---|---|---|---|
| D1 | Backend + bot: Application Insights SDK integration | Add `azure-monitor-opentelemetry` to backend and bot. Configure using `APPLICATIONINSIGHTS_CONNECTION_STRING` env var (already passed from Bicep). Verify traces, requests, and exceptions appear in Azure portal. | `backend`, `bot`, `observability`, `v1.0` | M | None |

### Phase E: Validation and Launch

| # | Title | Description | Labels | Size | Dependencies |
|---|---|---|---|---|---|
| E1 | Performance validation | Measure board load time (target < 2s) and image generation time (target < 5s) against the dev environment. Document results. If targets are missed, create follow-up issues for optimization. | `testing`, `v1.0` | M | D1 |
| E2 | Deploy to production and smoke test | Tag a v1.0-rc release to trigger prod deployment. Run smoke tests: health endpoint, login flow, create siege, assign members, generate image, send DM notification. Document results in the issue. | `infra`, `testing`, `v1.0` | M | C3, all A/B issues |
| E3 | Planner sign-off walkthrough | Schedule and conduct a walkthrough with the siege planner. Walk through the full lifecycle: login, create siege, configure buildings, assign members, validate, auto-fill, compare, send notifications, generate image, post to Discord. Record any critical feedback as new issues. | `v1.0` | M | E2 |
| E4 | 48-hour post-launch monitoring | Monitor Application Insights for errors, latency spikes, and failed requests for 48 hours after production deploy. Follow RUNBOOK.md Section 6 checklist. Close this issue when the monitoring window passes clean. | `v1.0`, `observability` | S | E2 |
| E5 | Update STATUS.md for v1.0 release | Mark Phase 9 complete. Update "Current State" and "Next Steps" sections. | `docs`, `v1.0` | S | E4 |

---

## Recommended Sequencing

```
                                  Parallel Track 1          Parallel Track 2
                                  ───────────────          ───────────────
Week 1:                           A1, A3 (backend auth)    C1 (merge PR #124)
                                                            C4 (Discord app registration)
                                                            D1 (App Insights SDK)

Week 2:                           A2 (auth middleware)     C2 (Bicep OAuth params)
                                  A4 (backend auth tests)
                                  B1 (AuthContext)

Week 3:                           B2 (login page)          C3 (provision prod)
                                  B3 (protected routes)
                                  B4 (frontend auth tests)

Week 4:                           E1 (perf validation)
                                  E2 (prod deploy + smoke)
                                  E3 (planner walkthrough)

Week 4–5:                         E4 (48h monitoring)
                                  E5 (update STATUS.md)
```

### Critical path

```
A1 → A2 → B1 → B3 → E2 → E3 → E4
         ↗
A3 → C2 → C3 ──────↗
```

The auth backend (A1) is the single most blocking item. Infrastructure work (C1, C4, D1) can proceed in parallel from day one because it has no code dependencies on the auth implementation.

### What can be parallelized

- **C1** (merge PR #124) — independent, can happen immediately
- **C4** (Discord app registration) — manual setup, no code dependency
- **D1** (App Insights SDK) — independent of auth work
- **A3** (config env vars) — trivial, can land with or before A1
- **A1** and **C2** can proceed in parallel; C2 just needs to know the env var names from A3

### Hard dependencies

- **A2** depends on **A1** (middleware needs the JWT verification logic from the auth endpoints)
- **B1/B2/B3** depend on **A1** (frontend needs working backend auth to test against)
- **C2** depends on **A3** (Bicep params must match the env var names the code expects)
- **C3** depends on **C1** and **C2** (prod provisioning should use the updated Bicep with OAuth params and the image tag fix)
- **E2** depends on **C3** and all auth issues (cannot deploy to prod without auth and infra ready)
- **E3** depends on **E2** (walkthrough requires a running prod environment)

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Discord API rate limits during OAuth callback | Low | Medium | Cache guild membership check; the `guilds` scope call is once per login, not per request |
| Member `discord_id` not populated for some users | Medium | High | Require Discord sync (existing preview/apply flow) to be run before enabling auth. Document in RUNBOOK.md as a pre-launch step. Add clear error message on login rejection. |
| Playwright image gen exceeds 5s on prod Container Apps sizing | Medium | Medium | Performance validation (E1) catches this early. Mitigation: increase API container CPU/memory in prod Bicep params. |
| Cold start latency on Container Apps (scale-to-zero) | Low | Low | Prod params should set `apiMinReplicas = 1` and `botMinReplicas = 1` (bot already stays warm for WebSocket). Frontend can scale to zero since static content loads fast. |
| Discord app OAuth2 redirect URI misconfiguration | Medium | High | Test full login flow against dev before prod deployment. Document exact redirect URIs in RUNBOOK.md. |

---

## Open Questions

These require decisions before or during implementation:

1. **JWT token TTL**: What should the session duration be? Suggested: 24 hours with no refresh — user re-authenticates daily. Shorter (e.g., 4 hours) is more secure but adds friction for a planning tool used in long sessions.

2. **Login rejection UX**: When a Discord user authenticates but has no matching Member record, what should the error page show? Suggested: "You are not a registered clan member. Contact your siege planner." with a button to try again.

3. **Dev environment auth bypass**: Should local development (`ENVIRONMENT=development`) skip auth for convenience, or should developers always authenticate? Suggested: optional bypass via env var `AUTH_DISABLED=true` for local dev only, never in deployed environments.

4. **Existing API clients**: Are there any scripts, bots, or external tools that call the backend API directly (besides the Discord bot sidecar)? If so, they will break when auth middleware is added. The bot-to-backend calls appear to go the other direction (backend calls bot), but this should be confirmed.

---

## GitHub Labels to Create

If not already present, create these labels before filing issues:

- `auth` — authentication-related work
- `v1.0` — v1.0 release candidate milestone
- `observability` — monitoring and telemetry
- `infra` — infrastructure and deployment

---

## Total Issue Count

| Phase | Issues | Total Size |
|---|---|---|
| A: Auth Backend | 4 | 1L + 2M + 1S |
| B: Auth Frontend | 4 | 2S + 2M |
| C: Infrastructure | 4 | 1L + 1M + 2S |
| D: Observability | 1 | 1M |
| E: Validation/Launch | 5 | 3M + 2S |
| **Total** | **18** | **2L + 8M + 8S** |
