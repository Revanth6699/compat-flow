#!/bin/sh
set -eu

run_database_migrations() {
    # When only the existing owner DATABASE_URL is configured, retain it for
    # migrations and derive the restricted application URL before importing app code.
    MIGRATION_DATABASE_URL="${MIGRATION_DATABASE_URL:-${DATABASE_URL:-}}"
    if [ -z "$MIGRATION_DATABASE_URL" ]; then
        echo "MIGRATION_DATABASE_URL or an owner DATABASE_URL is required when migrations are enabled." >&2
        exit 1
    fi
    if [ -z "${RUNTIME_DATABASE_ROLE:-}" ] || [ -z "${RUNTIME_DATABASE_PASSWORD:-}" ]; then
        echo "RUNTIME_DATABASE_ROLE and RUNTIME_DATABASE_PASSWORD are required for restricted runtime setup." >&2
        exit 1
    fi
    export MIGRATION_DATABASE_URL
    if [ -z "${DATABASE_URL:-}" ] || [ "$DATABASE_URL" = "$MIGRATION_DATABASE_URL" ]; then
        export DATABASE_URL="$(python - <<'PY'
import os
from sqlalchemy.engine import make_url
url = make_url(os.environ["MIGRATION_DATABASE_URL"])
owner_username = url.username or ""
runtime_username = os.environ["RUNTIME_DATABASE_ROLE"]
# Supabase session/transaction pooler usernames include the project ref suffix.
if "." in owner_username:
    runtime_username = f"{runtime_username}.{owner_username.rsplit('.', 1)[1]}"
print(url.set(
    username=runtime_username,
    password=os.environ["RUNTIME_DATABASE_PASSWORD"],
).render_as_string(hide_password=False))
PY
)"
    fi
    echo "Applying Alembic migrations with the dedicated migration connection."
    alembic upgrade head
    echo "Provisioning least-privilege runtime database role."
    python ./scripts/bootstrap_runtime_role.py
}

if [ "${APP_ENV:-}" = "staging" ] && [ "${STAGING_AUTO_MIGRATE:-}" = "true" ]; then
    run_database_migrations
elif [ "${APP_ENV:-}" = "production" ] && [ "${PRODUCTION_AUTO_MIGRATE:-}" = "true" ]; then
    run_database_migrations
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
