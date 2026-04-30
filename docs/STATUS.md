# Siege Assignment App — Status

## Current State

v1.0.0 shipped and v1.0.1 delivered. The application is feature-complete and live at `rslsiege.com`
(custom domain via Cloudflare Origin Cert). All core backend logic (CRUD, assignment board, validation
engine, auto-fill, attack day, comparison, Discord bot, image generation, notifications, and Excel import)
is implemented and covered by 3500+ backend tests. Playwright end-to-end tests cover the full siege
lifecycle. Vitest component tests cover the assignment board and notification polling. Azure Bicep IaC
is fully deployed for both dev and prod environments via GitHub Actions CD pipelines.

As of 2026-04-30 (v1.0.1, issue #246), the observability layer is live in both dev and prod: an
Application Insights workbook (5 tiles — request rates, latency p50/p95, exception counts, bot restarts,
image gen latency) plus 4 active alert rules (`alert5xxRate`, `alertLatencyP95`, `alertBotRestart`,
`alertImageGenSlow`) wired to an email action group. SQLAlchemy/asyncpg OTel instrumentation shipped in PR #265; dev verification on 2026-04-30 confirmed
Pattern A (type `"postgresql"`, no span duplication). The DB connection error alert and DB p95 tile
can now be wired as follow-on work. See RUNBOOK.md §6 for workbook URLs, alert inventory, and acknowledgement policy.

## Phase Completion

| Phase | Status | Description |
|---|---|---|
| 0 — Foundation | Complete | Monorepo, Docker, CI pipeline, Azure dev environment, health endpoints |
| 1 — Schema | Complete | Full DB schema, all migrations, seed data (36 post conditions, BuildingTypeConfig) |
| 2 — Core API | Complete | CRUD for members, sieges, buildings, SiegeMember; all tested |
| 3 — Board API | Complete | Board read/write, bulk assignments, lifecycle transitions, clone, post management |
| 4 — Business Logic | Complete | All 16 validation rules, auto-fill preview/apply, comparison, attack day algorithm |
| 5 — Discord Bot | Complete | discord.py rewrite, HTTP sidecar, image generation via Playwright, DM batch notifications |
| 6 — Frontend Core | Complete | Member CRUD, siege management, assignment board, auto-fill UI, validation panel |
| 7 — Frontend Discord/Compare | Complete | Comparison view, DM notification panel, channel post action, image preview/download |
| 8 — Excel Import | Complete | One-time CLI script using openpyxl; imports historical .xlsm siege files |
| 9 — Hardening/Launch | Complete | E2E tests, Bicep IaC, CD pipelines, custom domain (`rslsiege.com`), RUNBOOK.md — all shipped in v1.0.0 |
| 10 — Auth | Complete | Discord OAuth2 authentication: JWT session cookies, RequireAuth routing, `/api/auth/*` endpoints, role-based access gating |

## What's Working

- Discord OAuth2 authentication: login/callback/logout endpoints, JWT session cookies (24h expiry), guild membership + required Discord role enforcement, `RequireAuth` frontend wrapper, per-route auth bypass for `/api/auth/*`, `/api/health`, and `/api/version`
- Full siege lifecycle: create → configure buildings → assign members → validate → activate → complete
- Assignment board with per-position state (assigned / RESERVE / No Assignment / empty / disabled)
- Auto-fill: Fisher-Yates shuffle respecting defense_scroll_count; preview → apply flow
- All 16 validation rules (9 errors, 7 warnings) wired into activation gate
- Attack day algorithm with pinned-member support and 10-member Day 2 threshold
- Assignment comparison: per-member diffs (added / removed / unchanged) between any two sieges
- Discord bot: DM batches with per-member delivery status tracking, channel image posts
- Playwright image generation: assignments PNG and reserves PNG from headless HTML/CSS
- Excel import: historical .xlsm files imported as completed siege records
- 3500+ backend tests covering all routes, business logic, and constraint enforcement
- CI pipeline: black, ruff, pytest (backend) + ESLint, build (frontend) on every PR

## Phase 10 — Auth (Complete)

Discord OAuth2 authentication is fully implemented:
- Backend: `/api/auth/login`, `/api/auth/callback`, `/api/auth/logout`, `/api/auth/me` endpoints
- JWT session cookies (HS256, 24-hour expiry) issued after successful OAuth2 callback
- Guild membership enforced via bot's `get_member()` lookup — non-members redirected to `/login?error=unauthorized`
- Role-based access gating: user must also hold the Discord role named by `DISCORD_REQUIRED_ROLE` (default: `Clan Deputies`; exact, case-sensitive match; configurable by self-hosters)
- `get_current_user` dependency applied globally (excludes public routes); `auth_disabled` flag for local dev
- Frontend: `AuthContext` + `useAuth` hook; `RequireAuth` wrapper on all protected routes; `LoginPage` with Discord button; 401 interceptor redirects to login
- 19 backend auth tests; 6 frontend auth tests (LoginPage + AuthContext)

## Phase 9 — Hardening/Launch (Complete)

**Delivered:**
- RUNBOOK.md — restart procedures, rollback, DB restore, secret rotation, log queries, incident playbooks
- Playwright end-to-end tests: full siege lifecycle covered; 22 flaky tests fixed
- Azure Bicep IaC: all modules authored (ACR, Log Analytics, App Insights, PostgreSQL, Key Vault, Container Apps); dev + prod param files in place and deployed
- Vitest frontend unit tests: BoardPage and notification polling (SiegeSettingsPage) covered
- Azure Container Apps health check fixes (Key Vault role assignments, nginx envsubst, ACR naming)
- GitHub Actions CD pipeline: `deploy.yml` (push to main → dev; `v*` tag → prod) and `infra-deploy.yml` (manual Bicep) both operational
- Custom domain `rslsiege.com`: Cloudflare Origin Cert stored as PFX in Key Vault; user-assigned managed identity grants Container Apps environment `Key Vault Secrets User`; two-phase `enableCustomDomain` deploy gate in Bicep
- Production Azure environment provisioned and v1.0.0 deployed

**Post-launch (tracked):**
- Planner sign-off walkthrough (issue #174)
- 48-hour post-launch monitoring window (issue #175)
- Application Insights SDK integration in backend and bot services (still pending)
- Performance validation: board load target < 2s, image generation target < 5s (still pending)

## How to Run Locally

```bash
docker-compose up --build
```

Services: frontend `localhost:5173`, backend `localhost:8000`, bot `localhost:8001`.

Copy `.env.example` to `.env` and fill in required values before starting.

## Deployment

CI via GitHub Actions on every PR to `main`:
- Backend: black check → ruff → pytest
- Frontend: npm ci → eslint → npm build

`deploy.yml` auto-deploys to dev on push to `main` and to prod on `v*` tag push. `infra-deploy.yml` is triggered manually (`workflow_dispatch`) for any Bicep infrastructure changes.

## Post-Launch Activities

1. Planner sign-off walkthrough (issue #174)
2. 48-hour post-launch monitoring window (issue #175; see RUNBOOK.md Section 6 checklist)
3. ~~Enable Application Insights SDK in backend and bot~~ — complete; telemetry live as of #245
4. Validate performance: board load < 2s, image generation < 5s

## Active Workstream — Infra Hygiene & Cost (Milestone #6)

Issue #246 (workbook + alerts) is closed. **#257** (SQLAlchemy/asyncpg OTel instrumentation) shipped in PR #265 (commit `9a11733`) and is resolved: dev verification on 2026-04-30 confirmed Pattern A — `type == "postgresql"`, single row per `target`, no span duplication; both instrumentors retained. RUNBOOK.md §6 updated accordingly (PR #268). The DB connection error alert rule and DB p95 workbook tile can now be wired as follow-on work.
