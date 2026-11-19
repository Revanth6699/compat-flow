#!/bin/sh
set -eu

# Migrations are opt-in per environment. Production migration is enabled only
# for an explicitly configured release; ordinary restarts do not auto-migrate.
if [ "${APP_ENV:-}" = "staging" ] && [ "${STAGING_AUTO_MIGRATE:-}" = "true" ]; then
    if [ -z "${DATABASE_URL:-}" ]; then
        echo "STAGING_AUTO_MIGRATE is enabled but DATABASE_URL is missing; refusing to start." >&2
        exit 1
    fi

    echo "Applying Alembic migrations to the explicitly enabled staging database."
    alembic upgrade head
    echo "Staging database migrations completed."
elif [ "${APP_ENV:-}" = "production" ] && [ "${PRODUCTION_AUTO_MIGRATE:-}" = "true" ]; then
    if [ -z "${DATABASE_URL:-}" ]; then
        echo "PRODUCTION_AUTO_MIGRATE is enabled but DATABASE_URL is missing; refusing to start." >&2
        exit 1
    fi

    echo "Applying Alembic migrations to the explicitly enabled production database."
    alembic upgrade head
    echo "Production database migrations completed."
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
