---
name: Siege Assignment System — Project Structure
description: Monorepo layout, tech stack, and key file locations for the Siege Assignment System web app
type: project
---

Phase 0 foundation is complete. Monorepo at `I:/games/raid/siege-web`.

**Why:** Raid Shadow Legends guild tool — assigns players to siege map positions, posts boards to Discord.

**How to apply:** Follow existing patterns when adding new features in each subproject.

## Tech Stack
- Backend: Python 3.12, FastAPI, SQLAlchemy async, Alembic, asyncpg, pytest
- Frontend: React 18, TypeScript, Vite, React Router v6, TanStack Query v5, Tailwind CSS
- Bot: Python 3.12, discord.py 2.4, FastAPI HTTP sidecar (port 8001)
- Infra: Docker + docker-compose (local), Azure planned

## Key Directories
- `backend/app/` — FastAPI app (api/, db/, models/, schemas/, services/, config.py, main.py)
- `backend/alembic/` — Alembic async migrations (env.py imports Base + all models)
- `backend/tests/` — pytest tests; use dependency_overrides to mock get_db
- `frontend/src/` — React SPA (api/client.ts, pages/, components/, lib/utils.ts)
- `bot/app/` — discord_client.py (SiegeBot class), http_api.py (FastAPI sidecar), main.py (asyncio.TaskGroup runs both)
- `.github/workflows/ci.yml` — PR CI: backend lint/test + frontend lint/build

## Conventions
- Backend line-length 100, black + ruff (E/F/I/UP), asyncio_mode=auto
- Frontend: ESLint flat config (eslint.config.js), Prettier with tailwindcss plugin, no semicolons skipped
- Bot HTTP sidecar port: 8001; backend port: 8000; frontend (nginx) port: 5173→80
- All models imported in `backend/app/models/__init__.py` so Alembic detects them
- Pydantic Settings reads from .env; all services use env_file in docker-compose
