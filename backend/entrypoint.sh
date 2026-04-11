#!/bin/sh
# Run database migrations (and demo seed in development) before starting.
# This ensures schema is always up to date when the container starts,
# regardless of environment — works identically in local docker-compose and prod.
set -e

echo "Running database migrations..."
alembic upgrade head
echo "Migrations complete."

# In development mode, seed demo data so the UI is populated on first boot.
# The seed script is idempotent — re-running does not create duplicates.
if [ "${ENVIRONMENT:-}" = "development" ]; then
    echo "Development environment detected — seeding demo data..."
    python scripts/seed_demo.py
    echo "Demo seed complete."
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
