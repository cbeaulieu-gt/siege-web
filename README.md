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

That's it for the Quick Start. Python and Node are only needed if you want to run services outside Docker.

## Quick Start

Get a populated local UI running in under 5 minutes — no Discord setup required.

```bash
# 1. Clone and enter the repo
git clone https://github.com/cbeaulieu-gt/siege-web.git
cd siege-web

# 2. Copy the example env (auth is disabled by default for local dev)
cp .env.example .env

# 3. Start everything
docker-compose up --build
```

Open http://localhost:5173 — the app will load with 25 demo members and an active siege already populated. A thin amber banner at the top confirms you are in demo mode.

> **What happens on first boot:** the backend container runs `alembic upgrade head` then `python scripts/seed_demo.py` before starting. The seed script is idempotent — restarting the stack does not create duplicates.

To stop and wipe data: `docker-compose down -v`

## Dev Mode (hot reload)

Runs PostgreSQL in Docker; backend and frontend run natively for fast iteration.

```bash
# 1. Start PostgreSQL only
docker-compose up postgres

# 2. Backend (new terminal)
cd backend
pip install -r requirements-dev.txt
alembic upgrade head
python scripts/seed_demo.py   # populate demo data
uvicorn app.main:app --reload

# 3. Frontend (new terminal)
cd frontend
npm ci
npm run dev
```

- Frontend: http://localhost:5173 (proxies `/api/*` to backend)
- API docs: http://localhost:8000/api/docs

### VS Code

Launch configurations are included in `.vscode/`:

- **F5 → "Full Stack"** launches both backend and frontend
- **Ctrl+Shift+P → "Run Task"** for Docker, migrations, seeding, and tests

Requires the "Docker: Start PostgreSQL" task to be running first.

## Running with real Discord OAuth

1. Set `AUTH_DISABLED=false` in `.env`
2. Fill in the **Tier 2** variables in `.env` (Discord OAuth2 app credentials, bot token, guild ID)
3. Restart the stack

See `.env.example` for the full variable reference organized by tier.

## Database

Migrations and seeds only need to run once per fresh volume. Data persists across restarts in the `postgres_data` Docker volume.

```bash
# Run migrations
cd backend && alembic upgrade head

# Seed reference + demo data
cd backend && python scripts/seed_demo.py

# Reference data only (no demo members/siege)
cd backend && python scripts/seed.py

# Create a new migration after model changes
cd backend && alembic revision --autogenerate -m "description"
```

## Tests

```bash
# Backend
cd backend && python -m pytest --ignore=tests/test_schema.py -v

# Frontend type check + build
cd frontend && npm run build

# Bot
cd bot && python -m pytest -v
```

## Linting

```bash
# Backend
cd backend && black . && ruff check .

# Frontend
cd frontend && npm run lint
```

## Run it yourself

Full self-host guides live in the [project wiki](https://github.com/cbeaulieu-gt/siege-web/wiki):

- **[Self-Host on Any VPS](https://github.com/cbeaulieu-gt/siege-web/wiki/Self-Host-on-Any-VPS)** — any Linux host that runs Docker, with Caddy for free TLS and an optional Cloudflare Tunnel path if you can't open ports. The portable path — no cloud account required.
- **[Self-Host on Azure](https://github.com/cbeaulieu-gt/siege-web/wiki/Self-Host-on-Azure)** — Container Apps + Key Vault + PostgreSQL Flexible Server, with a GitHub Actions deploy pipeline. The managed, hands-off path.

New to the project? Start at **[Getting Started](https://github.com/cbeaulieu-gt/siege-web/wiki/Getting-Started)** in the wiki.

## Deploy Environments

Secrets for Azure deployments are stored in per-environment files (both gitignored):

| File | Purpose |
|---|---|
| `.env.deploy.dev` | Secrets for the dev Azure instance (`siege-web-dev` resource group) |
| `.env.deploy.prod` | Secrets for the prod Azure instance (`siege-web-prod` resource group) |

Copy `.env.deploy.example` to both files and fill in the values.

```powershell
# Build and deploy to dev
.\bootstrap-images.ps1 -Env dev -EnvFile .env.deploy.dev

# Build and deploy to prod
.\bootstrap-images.ps1 -Env prod -EnvFile .env.deploy.prod
```

## Environment Variables

`.env.example` is organized into three tiers:

| Tier | Description |
|---|---|
| **1 — Always required** | `DATABASE_URL`, `ENVIRONMENT`, `AUTH_DISABLED`, `SESSION_SECRET` |
| **2 — Discord / real auth** | OAuth2 credentials, bot token, guild ID, channel names, API keys, `DISCORD_REQUIRED_ROLE` |
| **3 — Azure / deploy only** | `ALLOWED_ORIGINS`, `IMPORT_EXCEL_PATH` and anything used only by Bicep or CI |

`AUTH_DISABLED=true` (the default in `.env.example`) bypasses login entirely — anyone who can reach the URL has full access. Never use this outside a local dev environment.

`SESSION_SECRET` is required when `AUTH_DISABLED=false`. Generate a secure value with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for the full text.

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) before opening a PR.
