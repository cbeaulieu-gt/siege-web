# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-04-17

### Added

**Siege lifecycle**
- Full siege lifecycle: create → configure buildings → assign members → validate → activate → complete
- Assignment board with per-position state (assigned / RESERVE / No Assignment / empty / disabled)
- Siege clone: copy an existing siege as a starting point for the next one
- Post management: create and manage siege posts with per-post condition tracking

**Assignment logic**
- Auto-fill algorithm using Fisher-Yates shuffle respecting `defense_scroll_count`; preview → apply flow (apply commits exactly what was previewed)
- All 16 validation rules (9 errors, 7 warnings) wired into the activation gate
- Attack day algorithm with pinned-member support and configurable 10-member Day 2 threshold
- Assignment comparison view: per-member diffs (added / removed / unchanged) between any two sieges

**Member management**
- Full CRUD for clan members with `defense_scroll_count` tracking
- Bulk assignment endpoints for efficient board population

**Discord bot integration**
- Direct-message notification batches with per-member delivery status tracked in the database
- Channel image posts: assignments PNG and reserves PNG generated from headless HTML/CSS via Playwright
- HTTP sidecar (port 8001) on the bot process; backend communicates exclusively through this API

**Image generation**
- Playwright headless HTML/CSS → PNG pipeline for assignments and reserves boards
- Images posted to a dedicated Discord channel; CDN links stored for retrieval

**Historical data**
- Excel import: one-time CLI script (openpyxl) ingests historical `.xlsm` siege files as completed siege records

**Frontend**
- React 18 + TypeScript single-page app with React Router v6 and React Query
- shadcn/ui component library with Tailwind CSS
- Member CRUD, siege management, assignment board, auto-fill UI, validation panel
- Comparison view (side-by-side diff between two sieges)
- DM notification panel with real-time delivery status polling
- Image preview and download from the assignment board

### Security

- Discord OAuth2 authentication flow: `/api/auth/login` → OAuth2 callback → JWT session cookie (HS256, 24-hour expiry)
- Guild membership enforced via bot `get_member()` lookup — non-members redirected to `/login?error=unauthorized`
- Role-based access gating: user must hold the Discord role named by `DISCORD_REQUIRED_ROLE` (default: `Clan Deputies`; exact, case-sensitive; configurable by self-hosters)
- `get_current_user` FastAPI dependency applied globally; auth bypass allowlist for `/api/auth/*`, `/api/health`, and `/api/version`
- `auth_disabled` flag available for local development without a Discord application
- Frontend `AuthContext` + `RequireAuth` wrapper guards all protected routes; 401 interceptor redirects to `/login`

### Infrastructure

- Azure Bicep IaC: full module set for ACR, Log Analytics, App Insights, PostgreSQL Flexible Server, Key Vault, and Container Apps; separate dev and prod parameter files
- Custom domain via Cloudflare Origin Cert: cert stored as PFX in Key Vault; user-assigned managed identity grants Container Apps environment `Key Vault Secrets User`; two-phase `enableCustomDomain` deploy gate prevents failure before cert upload
- `deploy.yml` CD pipeline: push to `main` auto-deploys to dev; `v*` tag push deploys to prod; builds Docker images, pushes to ACR, updates Container App revisions
- `infra-deploy.yml` manual pipeline: `workflow_dispatch`-only; runs `az deployment group create` for Bicep changes
- `RUNBOOK.md`: restart procedures, rollback, DB restore, secret rotation, log queries, and incident playbooks

### Developer Experience

- `docker-compose` local stack: postgres → backend → frontend → bot in one command
- 3500+ backend tests covering all routes, business logic, and constraint enforcement (pytest + asyncpg test DB)
- Playwright end-to-end tests covering the full siege lifecycle; 22 flaky tests resolved
- Vitest component tests for the assignment board (`BoardPage`) and notification polling (`SiegeSettingsPage`)
- CI on every PR to `main`: black + ruff + pytest (backend); ESLint + build (frontend)

[Unreleased]: https://github.com/cbeaulieu-gt/siege-web/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/cbeaulieu-gt/siege-web/releases/tag/v1.0.0
