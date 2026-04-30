# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Raid Shadow Legends Siege Assignment Web App — replaces a manual Discord-based workflow for assigning clan members to stronghold siege buildings. See `docs/IMPLEMENTATION_PLAN.md` for the phased roadmap and `docs/WEB_DESIGN_DOCUMENT.md` for full domain spec (validation rules, auto-fill algorithm, attack day logic, building configs).

## Architecture

Monorepo with three independently containerized services:

- **`backend/`** — FastAPI (Python 3.12), SQLAlchemy async + asyncpg, Alembic migrations, PostgreSQL
- **`frontend/`** — React 18 + TypeScript, Vite, React Router v6, React Query, Tailwind CSS, shadcn/ui
- **`bot/`** — discord.py client + FastAPI HTTP sidecar (port 8001); backend calls the bot's HTTP API to send DMs / post images

Data flow:
- Unauthenticated users hit `/login` → `/api/auth/login` → Discord OAuth2 → `/api/auth/callback` → JWT session cookie
- Frontend calls `/api/*` with cookie → backend validates via `get_current_user` dependency → PostgreSQL
- Backend calls bot HTTP API for Discord notifications
- Backend generates images via Playwright (headless HTML/CSS → PNG); bot receives the PNG and posts it

See `docs/superpowers/plans/discord-auth-plan.md` for the canonical auth spec.

 - Keep `docs/STATUS.md` with a high level summary of the state of the project and the anticipated next steps. Frequently update it.

## Common Commands

### Full stack (local)
```bash
docker-compose up          # starts postgres → backend → frontend → bot
docker-compose up --build  # rebuild images first
```

Services: frontend `localhost:5173`, backend `localhost:8000`, bot `localhost:8001`.

### Backend
```bash
cd backend
pip install -r requirements-dev.txt

# Run
uvicorn app.main:app --reload

# Test
pytest --ignore=tests/test_schema.py -v     # standard run (test_schema.py requires live DB)
pytest tests/test_health.py                 # single file
pytest -k "test_health"                     # single test by name
pytest --cov=app --cov-report=term-missing

# Lint / format
black .
ruff check .
ruff check . --fix

# Migrations
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1
```

### Frontend
```bash
cd frontend
npm ci

# Dev server (proxies /api/* to localhost:8000)
npm run dev

# Build
npm run build

# Lint / format
npx eslint src/
npx prettier --write src/
```

### Bot
```bash
cd bot
pip install -r requirements-dev.txt
python app/main.py   # runs Discord client + HTTP sidecar concurrently
pytest
```

## Key Conventions

### Backend
- Async everywhere: `AsyncSession`, `asyncpg`, `async def` route handlers.
- Settings via Pydantic `BaseSettings` in `app/config.py`; loaded from `.env`.
- All routes registered under `/api` prefix.
- DB dependency injected via `get_db()` from `app/db/session.py`.
- Models go in `app/models/`; Alembic's `env.py` auto-detects them via `app.db.base`.

### Frontend
- API base URL from `VITE_API_URL` env var; Axios client in `src/api/client.ts`.
- Pages in `src/pages/`; routes wired in `src/App.tsx`.
- `cn()` utility from `src/lib/utils.ts` for Tailwind class merging.
- Prettier enforces double quotes and Tailwind class sorting (`.prettierrc`).

### Bot
- `SiegeBot` (discord.py) and the HTTP API (FastAPI on port 8001) run concurrently via `asyncio.TaskGroup`.
- All bot HTTP endpoints require Bearer token auth (`BOT_API_KEY`).
- Backend communicates with the bot exclusively through the HTTP API (never direct discord.py calls from backend).

## CI (GitHub Actions)

On PR to `main`:
- **Backend**: black check → ruff → pytest (uses test DB URL from env)
- **Frontend**: npm ci → eslint → npm build

Registry image retention is automated via a scheduled ACR Task (`weekly-purge`) in both registries — release tags (`v*`) are preserved forever; SHA/commit tags beyond the last 10 per repo and untagged manifests older than 7 days are deleted every Sunday at 03:00 UTC.

**Application health workbook:** [siege-web-prod](https://portal.azure.com/#@cmbdevoutlook333.onmicrosoft.com/resource/subscriptions/213aa1f8-32d1-4ffe-8f4d-6e60f1cd9dc0/resourceGroups/siege-web-prod/providers/Microsoft.Insights/workbooks/c3bfb777-8256-5580-ab51-65f537101966/overview) — at-a-glance ops vitals (request rates, latency p50/p95, exception count, bot restarts, image gen latency). Dev equivalent at [siege-web-dev](https://portal.azure.com/#@cmbdevoutlook333.onmicrosoft.com/resource/subscriptions/213aa1f8-32d1-4ffe-8f4d-6e60f1cd9dc0/resourceGroups/siege-web-dev/providers/Microsoft.Insights/workbooks/ef1f3d0a-b955-5028-ae97-2b1732a3b5bf/overview).

Two deployment workflows exist and are fully operational:

- **`.github/workflows/deploy.yml`** — triggered automatically on push to `main` (deploys to dev) and on `v*` tag push (deploys to prod). Builds Docker images, pushes to ACR, then updates Container App revisions with the new image tag.
- **`.github/workflows/infra-deploy.yml`** — manual-only (`workflow_dispatch`). Runs `az deployment group create` with the Bicep templates in `infra/`. Use this for any infrastructure change (new resource, config update, cert binding). Requires secrets configured under GitHub Settings → Environments (dev / prod).

## Environment Variables

Copy `.env.example` to `.env`. Required:

| Variable | Used by |
|---|---|
| `DATABASE_URL` | backend, bot |
| `DISCORD_TOKEN` | bot |
| `DISCORD_GUILD_ID` | backend, bot |
| `DISCORD_BOT_API_URL` | backend (calls bot) |
| `DISCORD_BOT_API_KEY` / `BOT_API_KEY` | backend → bot auth |
| `DISCORD_SIEGE_CHANNEL` | backend (channel to post images) |
| `DISCORD_SIEGE_IMAGES_CHANNEL` | backend (channel to post image CDN links) |
| `ENVIRONMENT` | all (controls debug/docs) |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | backend, bot (optional; telemetry no-op when unset) |

## Domain Reference

Key domain docs (read before implementing business logic):
- **Validation rules** (16 total, errors + warnings): `docs/WEB_DESIGN_DOCUMENT.md` and memory `project_validation_rules.md`
- **BuildingTypeConfig** (base groups + last slot counts): memory `project_building_type_config.md`
- **Auto-fill algorithm**: preview stores result; apply commits exactly what was previewed — `project_autofill.md`
- **Attack day algorithm**: pinned members count toward Day 2 threshold — `project_attack_day.md`
- **Board API response**: nested hierarchy (buildings → groups → positions) — `project_api_decisions.md`
- **Image generation**: Playwright headless HTML/CSS → PNG — `project_image_generation.md`
- **Notifications**: async DM batches tracked via `NotificationBatch` + `NotificationBatchResult` DB tables — `project_notifications.md`
- **Excel import**: one-time backend CLI script only, no UI or API endpoint — `project_excel_import.md`

