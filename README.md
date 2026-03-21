# Siege Assignment Web App

Web application for managing Raid Shadow Legends clan siege assignments. Replaces the manual Discord/Excel workflow with a unified web UI backed by a relational database.

## Architecture

| Service | Stack | Port |
|---|---|---|
| Backend | FastAPI, SQLAlchemy async, PostgreSQL | 8000 |
| Frontend | React 18, TypeScript, Vite, Tailwind, shadcn/ui | 5173 |
| Bot | discord.py + FastAPI HTTP sidecar | 8001 |
| Database | PostgreSQL 16 | 5432 |

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Python 3.12+
- Node.js 20+

## Quick Start (Docker)

Runs all services in containers.

```bash
# 1. Create .env from example
cp .env.example .env

# 2. Start all services
docker-compose up --build

# 3. Run database migrations (first time only)
docker-compose exec backend alembic upgrade head

# 4. Seed reference data (first time only)
docker-compose exec backend python seed.py
```

Open http://localhost:5173 in your browser.

## Dev Mode (recommended for active development)

Runs PostgreSQL in Docker, backend and frontend natively for hot reload and debugging.

```bash
# 1. Start PostgreSQL
docker-compose up postgres

# 2. Backend setup (first time)
cd backend
pip install -r requirements-dev.txt
alembic upgrade head
python seed.py

# 3. Start backend (new terminal)
cd backend
uvicorn app.main:app --reload

# 4. Start frontend (new terminal)
cd frontend
npm ci
npm run dev
```

- Frontend: http://localhost:5173 (proxies `/api/*` to backend)
- Backend API docs: http://localhost:8000/api/docs

### VS Code

Launch configurations are included in `.vscode/`:

- **F5 → "Full Stack"** launches both backend and frontend
- **Ctrl+Shift+P → "Run Task"** for Docker, migrations, seeding, and tests

Requires "Docker: Start PostgreSQL" task to be running first.

## Database

Migrations and seeds only need to run once. Data persists in the `postgres_data` Docker volume across restarts.

```bash
# Run migrations
cd backend && alembic upgrade head

# Seed reference data (36 post conditions + 5 building type configs)
cd backend && python seed.py

# Create a new migration after model changes
cd backend && alembic revision --autogenerate -m "description"
```

## Tests

```bash
# Backend
cd backend && python -m pytest --ignore=tests/test_schema.py -v

# Bot
cd bot && python -m pytest -v

# Excel import script
cd scripts && python -m pytest tests/ -v

# Frontend type check + build
cd frontend && npm run build
```

## Linting

```bash
# Backend
cd backend && black . && ruff check .

# Frontend
cd frontend && npm run lint
```

## Environment Variables

Copy `.env.example` to `.env`. All variables are required for Docker Compose. For dev mode, the backend reads from `backend/.env`.

| Variable | Used by | Description |
|---|---|---|
| `DATABASE_URL` | backend | PostgreSQL connection string |
| `DISCORD_BOT_API_URL` | backend | Bot sidecar URL |
| `DISCORD_BOT_API_KEY` / `BOT_API_KEY` | backend, bot | Shared API key |
| `DISCORD_TOKEN` | bot | Discord bot token |
| `DISCORD_GUILD_ID` | backend, bot | Discord server ID |
| `ENVIRONMENT` | all | `development` or `production` |
