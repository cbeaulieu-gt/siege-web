#!/bin/sh
# Run database migrations before starting the application.
# This ensures schema is always up to date when the container starts,
# regardless of environment — works identically in local docker-compose and prod.
set -e

echo "Running database migrations..."
alembic upgrade head
echo "Migrations complete."

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
