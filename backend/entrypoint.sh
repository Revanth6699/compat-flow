#!/bin/sh
set -eu

# Database migrations are opt-in and restricted to the staging environment.
# Production and local development always start the API without auto-migrating.
if [ "${APP_ENV:-}" = "staging" ] && [ "${STAGING_AUTO_MIGRATE:-}" = "true" ]; then
    if [ -z "${DATABASE_URL:-}" ]; then
        echo "STAGING_AUTO_MIGRATE is enabled but DATABASE_URL is missing; refusing to start." >&2
        exit 1
    fi

    echo "Applying Alembic migrations to the explicitly enabled staging database."
    alembic upgrade head
    echo "Staging database migrations completed."
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
