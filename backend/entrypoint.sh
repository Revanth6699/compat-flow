#!/bin/sh
set -eu

run_staging_migrations() {
    if [ -z "${MIGRATION_DATABASE_URL:-}" ]; then
        echo "MIGRATION_DATABASE_URL is required when staging migrations are enabled." >&2
        exit 1
    fi
    if [ -z "${RUNTIME_DATABASE_ROLE:-}" ] || [ -z "${RUNTIME_DATABASE_PASSWORD:-}" ]; then
        echo "RUNTIME_DATABASE_ROLE and RUNTIME_DATABASE_PASSWORD are required for restricted runtime setup." >&2
        exit 1
    fi
    echo "Applying Alembic migrations with the dedicated migration connection."
    alembic upgrade head
    echo "Provisioning least-privilege runtime database role."
    python ./scripts/bootstrap_runtime_role.py
}

if [ "${APP_ENV:-}" = "staging" ] && [ "${STAGING_AUTO_MIGRATE:-}" = "true" ]; then
    run_staging_migrations
elif [ "${APP_ENV:-}" = "production" ] && [ "${PRODUCTION_AUTO_MIGRATE:-}" = "true" ]; then
    run_staging_migrations
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
