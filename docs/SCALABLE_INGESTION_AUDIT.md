# Scalable ingestion architecture audit

Audit date: 2026-11-22
Base audited: `main` at `4cea5f85439f37e0459cb51adb71fc611b6d2072`

## Executive finding

CompatFlow already has Celery, Redis configuration, an import-job model, and a worker service. The immediate gap is not the absence of a queue. The newer multi-format and connector ingestion paths do not use the existing worker pipeline: they read complete uploads into memory, parse all records into lists, validate into additional lists, and (for commits) persist synchronously in the request.

Do not remove customer-facing record quotas until a bounded-memory processing path is implemented and verified. Removing the entitlement limit alone would expose existing in-memory parsers and validators to unbounded work.

## Verified current architecture

### File adapters

- `backend/app/services/ingestion_adapters.py` returns a `ParsedSource` containing a complete `list[SourceRecord]`.
- CSV reads the complete byte payload, decodes it to a complete string, then creates a list of every parsed record.
- XLSX uses openpyxl read-only iteration, but still accumulates every record in a Python list. It also checks worksheet dimensions against the configured record cap.
- XLS uses xlrd and accumulates every record in a list.
- JSON uses `json.loads` on the complete payload and builds a complete record list.
- XML uses `defusedxml.fromstring`, builds an in-memory element tree, and then builds a complete record list.
- Existing safety checks include upload bytes, XLSX archive entries, uncompressed archive bytes, compression ratio, columns, header row and cell length. These are useful safeguards and must not be removed as part of scaling work.

### Validation and persistence

- `backend/app/services/record_import.py` validates the complete `ParsedSource` and accumulates valid records, source locations, source keys, duplicate-key state, and bounded error details in memory.
- `backend/app/services/catalog_ingestion.py` persists a complete validation result synchronously. It loops through records and creates row-level nested transactions and lineage rows.
- `backend/app/api/routes.py` reads complete uploads and performs multi-format profile/validation synchronously. The profile route also creates a second list of row dictionaries and computes exact duplicate detection and column distributions over the complete dataset.
- `backend/app/api/connector_import_routes.py` fetches API/SFTP/SQL Server data and runs parse, validation, and commit synchronously. REST API pages are accumulated into one list; SQL Server rows are bounded but accumulated before JSON serialization and validation.
- The current file UI exposes preview/validation, not the full durable multi-format commit workflow.

### Existing worker infrastructure

- `backend/app/workers/celery_app.py` configures Celery with Redis broker/backend, late acknowledgements, and worker prefetch multiplier 1.
- `backend/app/workers/tasks.py` has a legacy CSV product-import task. It calls `read_bytes()`, decodes the whole file, parses all rows, and then persists them. It is not a bounded-memory multi-format worker.
- Therefore, reusing Celery is sensible, but simply routing new work to the existing task would not solve memory usage.

### Plan limits

- `backend/app/core/auth.py` returns `max_records` and `max_upload_bytes` from subscription entitlements.
- Approved demo access currently has a 10,000-record cap and 5 MB file cap.
- The paid-plan migration `20261116_0011_upload_limits.py` stores both record and byte limits for Starter, Growth, and Business.
- API routes and the frontend import page display/use both limits.
- Connector extraction also uses record caps; the REST connector has a 10,000-record default and SQL Server extraction has a bounded row limit.
- Removing only the paid-plan record entitlement would not remove parser, connector, or public-demo row caps and would not make processing memory-safe.

## Target architecture

1. Keep the FastAPI API responsible for authentication, authorization, entitlement checks, upload admission, job creation, and status/results.
2. Store original uploads in durable object storage using an opaque object key. Do not rely on a worker-local filesystem path unless the storage is explicitly shared and durable.
3. Enqueue a durable import job with tenant ID, object key, source metadata, selected format/options, and idempotency key. Never put raw credentials or full file contents in the queue message.
4. Use the existing Celery/Redis infrastructure for workers, with explicit queue names, bounded concurrency, task time limits, late-acknowledgement/retry policy, and job lease/recovery behavior.
5. Implement format-specific iterators that yield source records in bounded batches while preserving source locations and values. XLSX should retain read-only iteration; CSV should use a streaming text wrapper; JSON and XML need carefully selected streaming parsers rather than whole-document `json.loads` / `fromstring` for large inputs.
6. Validate batches incrementally. Keep only bounded previews/errors and the minimum duplicate-detection state required by each record type. For exact duplicate detection at scale, use a durable staging table with tenant/job-scoped unique keys or another explicit disk-backed strategy; do not silently weaken duplicate semantics.
7. Persist validated batches transactionally with idempotent job/batch checkpoints. Preserve partial-success accounting, row lineage, and source provenance.
8. Keep job status and summary data in Postgres/Supabase-backed application tables. Store original files and generated artifacts in object storage, not in database rows or ephemeral container storage.
9. Enforce resource controls independently of commercial record quotas: per-file byte limits, archive expansion limits, maximum columns/cell length, batch size, worker concurrency, execution time, memory-aware worker sizing, per-organization active-job limits, and queue backpressure.
10. Expose progress/status and paginated errors/results to the UI. Do not keep long-running import requests open.

## Commercial limit decision to implement after the safe processing path

The agreed direction is to remove customer-facing record-count quotas and retain file-size limits:
- Demo: 5 MB
- Starter: 10 MB
- Growth: 20 MB
- Business: 100 MB
- Enterprise: contract-defined

This is a target decision, not a statement that the current code already enforces it. Existing row caps must remain until the target architecture and test coverage are complete. Keep the existing byte, archive, column, cell, timeout, and concurrency safeguards. Do not compress, truncate, rewrite, or discard customer input to force it under a limit.

## Implementation phases

### Phase A — job and storage foundation
- Confirm the production Redis/Celery and shared storage configuration.
- Define durable job states, idempotency, retries, cancellation, lease recovery, and tenant isolation.
- Add object-storage abstraction and lifecycle/retention policy.
- Add worker health/queue observability and per-tenant admission controls.

### Phase B — streaming parser and validator foundation
- Add batch iterator interfaces while preserving existing parser behavior for current preview routes.
- Implement and test streaming CSV and XLSX first.
- Add streaming JSON and XML implementations with explicit supported input shapes and safe parser limits.
- Build incremental validation, duplicate tracking, bounded error collection, and batch persistence.

### Phase C — route and UI migration
- Migrate multi-format file imports to create jobs and return job IDs.
- Migrate connector ingestion to bounded page/batch processing; avoid concatenating all pages into one list.
- Add progress polling, paginated errors, cancellation, and retry visibility.
- Keep legacy endpoints compatible until the replacement paths are verified.

### Phase D — remove customer record quotas
- Remove plan-specific record-count entitlements and all corresponding UI display only after Phases A-C pass.
- Retain the agreed per-plan file-size caps and all technical resource safeguards.
- Update connector limits separately; a source connector must not become unbounded just because file-upload quotas are removed.
- Update migration tests, API tests, UI tests, docs, and plan entitlement fixtures.

## Required acceptance tests

- Every supported file format preserves all source records, values, types, and source locations across batch boundaries.
- No silent truncation: a technical safety limit produces an explicit failed/rejected job with a clear reason.
- Memory use remains bounded as record count increases; tests should exercise datasets materially larger than the former 10,000-row default.
- CSV/XLSX/JSON/XML parsing and validation have cross-batch regression tests.
- Exact duplicate behavior and tenant-scoped foreign-key checks remain correct across batches.
- Batch persistence is idempotent after worker retry or crash; no duplicate catalog rows or duplicate lineage.
- Job state recovery works after worker restart; failed jobs do not remain stuck in processing.
- Concurrent jobs respect per-tenant and global concurrency limits.
- Object storage failures, Redis outages, malformed files, oversized XLSX expansion, and timeouts fail safely.
- API requests return promptly with a job identifier; UI displays progress and terminal status.
- Connector API pagination does not concatenate an unbounded source; SFTP and SQL Server remain bounded and never silently truncate.
- Existing authentication, organization isolation, subscription feature gates, billing, and account deletion tests continue to pass.

## Rollout constraints

- No Render, Supabase, or Vercel plan upgrades as part of this work.
- No production environment variable changes until the required services and deployment configuration have been reviewed.
- No direct commits to `main`; work proceeds through a separate PR and CI.
- Merge only after the implementation is complete, tests pass, and the deployment impact is understood.
