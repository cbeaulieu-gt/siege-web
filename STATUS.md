# Siege Assignment App — Status

## Current State

The application is feature-complete through Phase 8. All core backend logic (CRUD,
assignment board, validation engine, auto-fill, attack day, comparison, Discord bot,
image generation, notifications, and Excel import) is implemented and covered by 3500+
lines of backend tests. The React frontend covers the full planner workflow including the
assignment board, post/member management, the comparison view, and Discord notification
controls. Phase 9 (hardening and launch) is in progress: the RUNBOOK.md has been written,
and the remaining gaps are Playwright end-to-end tests, Azure Bicep IaC, Vitest frontend
unit tests, and production environment provisioning.

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
| 9 — Hardening/Launch | In Progress | RUNBOOK.md done; E2E tests, Bicep IaC, Vitest frontend tests, and prod provisioning remaining |

## What's Working

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

## Phase 9 — In Progress

**Done:**
- RUNBOOK.md — restart procedures, rollback, DB restore, secret rotation, log queries, incident playbooks

**Remaining:**
- Playwright end-to-end tests: full siege lifecycle in CI against staging
- Azure Bicep IaC: production environment definition (Container Apps, PostgreSQL, ACR, Key Vault)
- Vitest frontend unit tests: component tests for board interactions and notification polling
- Performance validation: board load target < 2s, image generation target < 5s
- Application Insights configuration: error monitoring and request tracing
- Production Azure environment provisioning (separate from dev)
- GitHub Actions deployment pipeline: merge to main → build → push to ACR → deploy to prod
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

1. Write Playwright E2E tests covering the full siege lifecycle
2. Write Vitest component tests for the assignment board and notification polling
3. Author Azure Bicep IaC for the production environment
4. Configure Application Insights on all three Container Apps
5. Provision production Azure environment from Bicep templates
6. Configure GitHub Actions CD pipeline (build → ACR push → Container App deploy on merge to main)
7. Validate RUNBOOK.md against the real production environment
8. Run a full walkthrough with the siege planner; address any critical feedback
9. Deploy to production and run smoke tests
10. Monitor for 48 hours post-launch (see RUNBOOK.md Section 6 checklist)
