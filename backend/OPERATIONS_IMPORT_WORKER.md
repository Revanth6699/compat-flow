# Background import worker

The API and the worker must share the same PostgreSQL database, Redis broker,
Supabase project URL, service-role credential, and private import bucket.

## Required worker environment

- `APP_ENV`: `production`
- `DATABASE_URL`: same database URL as the API
- `CELERY_BROKER_URL`: same Redis broker URL as the API
- `CELERY_RESULT_BACKEND`: same Redis result backend as the API
- `SUPABASE_URL`: same Supabase project URL as the API
- `SUPABASE_SERVICE_ROLE_KEY`: server-only Supabase service credential
- `IMPORT_STORAGE_BUCKET`: `compatflow-imports`
- `IMPORT_MAX_UPLOAD_BYTES`: configured per deployment, never above 100 MB

Never expose the service-role credential to the browser or commit it to the repository.

## Render worker start command

Run from the `backend` directory:

```sh
celery -A app.workers.celery_app.celery_app worker --loglevel=INFO --concurrency=1
```

The worker must be a separate background worker service, not a second Uvicorn process.
Start with concurrency 1 until representative memory and duration measurements justify
raising it. Keep the worker on the same region/network as the API, database, and Redis
where practical.

## Current implementation boundary

The private object-storage adapter supports the existing CSV compatibility task and
streams file transfer to/from Supabase Storage. The legacy CSV parser still materializes
the parsed validation result in memory. This change does **not** make multi-format
ingestion bounded-memory and does not authorize removing record-count or archive-expansion
safeguards. The multi-format chunked parser and batch persistence work remain subsequent
phases.

## Activation order

1. Apply the reviewed Alembic migration to create/update the private bucket.
2. Configure the API and worker environment variables with the same credentials.
3. Deploy the worker with concurrency 1 and verify its `compatflow.health_check` task.
4. Only then wire durable job submission to the worker; do not enable a route that
   enqueues jobs until storage and worker health checks pass.
