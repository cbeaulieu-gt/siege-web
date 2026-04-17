# Siege Assignment App — Status

## Current State

The application is feature-complete through Phase 9 (hardening and launch). All core
backend logic (CRUD, assignment board, validation engine, auto-fill, attack day, comparison,
Discord bot, image generation, notifications, and Excel import) is implemented and covered
by 3500+ backend tests. Playwright end-to-end tests cover the full siege lifecycle.
Vitest component tests cover the assignment board and notification polling. Azure Bicep IaC
is authored for both dev and prod environments. The RUNBOOK.md documents all operational
procedures. The remaining Phase 9 items (prod provisioning, GitHub Actions CD pipeline,
planner sign-off, smoke tests, and 48-hour post-launch monitoring) are pre-launch steps
that depend on the production environment being stood up.

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
| 9 — Hardening/Launch | In Progress | E2E tests, Bicep IaC, Vitest, RUNBOOK.md done; prod provisioning + CD pipeline + launch steps remaining |
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

## Phase 9 — In Progress

**Done:**
- RUNBOOK.md — restart procedures, rollback, DB restore, secret rotation, log queries, incident playbooks
- Playwright end-to-end tests: full siege lifecycle covered; 22 flaky tests fixed
- Azure Bicep IaC: all modules authored (ACR, Log Analytics, App Insights, PostgreSQL, Key Vault, Container Apps); dev + prod param files in place
- Vitest frontend unit tests: BoardPage and notification polling (SiegeSettingsPage) covered
- Azure Container Apps health check fixes (Key Vault role assignments, nginx envsubst, ACR naming)
- GitHub Actions CD pipeline: `deploy.yml` (push to main → dev; `v*` tag → prod) and `infra-deploy.yml` (manual Bicep) both operational
- Custom domain Bicep fix (issue #228): switched from Azure-managed cert (incompatible with Cloudflare proxy + apex domain) to Cloudflare Origin Cert stored as PFX in Key Vault; user-assigned managed identity grants Container Apps environment `Key Vault Secrets User` on KV; two-phase deploy gate (`enableCustomDomain` param) prevents failure when cert has not yet been uploaded

**Remaining (pre-launch):**
- Execute custom domain Phase 2: generate Cloudflare Origin Cert, run `scripts/generate-origin-pfx.ps1`, upload PFX to Key Vault, redeploy with `enableCustomDomain = true`
- Production Azure environment provisioning (stand up `siege-web-prod` resource group from Bicep)
- Performance validation: board load target < 2s, image generation target < 5s
- Application Insights SDK integration in backend and bot services
- Planner sign-off walkthrough
- Smoke tests against production
- 48-hour post-launch monitoring

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

Production deployment pipeline (merge to main → ACR push → Container Apps deploy) is
planned as part of Phase 9 and is not yet configured.

## Next Steps (ordered, pre-launch)

1. Provision production Azure environment (`siege-web-prod` resource group) from Bicep templates
2. Configure GitHub Actions CD pipeline (build → ACR push → Container App deploy on merge to main)
3. Enable Application Insights SDK in backend and bot (`azure-monitor-opentelemetry`)
4. Validate performance: board load < 2s, image generation < 5s
5. Validate RUNBOOK.md against the real production environment
6. Run a full walkthrough with the siege planner; address any critical feedback
7. Deploy to production and run smoke tests
8. Monitor for 48 hours post-launch (see RUNBOOK.md Section 6 checklist)
