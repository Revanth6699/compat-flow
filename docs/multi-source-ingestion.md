# Multi-Source Ingestion

## 1. Capability status

CompatFlow uses separate file-format adapters and source connectors. File adapters parse source data into a shared intermediate representation before mapping, validation, and persistence.

| Input | Parser / preview | Backend commit path | Current boundary |
|---|---|---|---|
| CSV | Implemented | Shared multi-format commit endpoint | Public product-quality CSV validation is a separate legacy path |
| Excel (.xlsx) | Implemented | Shared multi-format commit endpoint | Read-only workbook mode; selected sheet and header row |
| Excel (.xls) | Implemented | Shared multi-format commit endpoint | Legacy XLS reader; selected sheet and header row |
| JSON | Implemented | Shared multi-format commit endpoint | Object/array records; nested objects flattened; ambiguous arrays require explicit path |
| XML | Implemented | Shared multi-format commit endpoint | Safe parser; repeated record groups; ambiguous input requires explicit record tag |
| REST API | One-shot connector implemented | Connector preview and commit endpoints | Page-number pagination only; bounded retries; no generic cursor/next-link support |
| SFTP | One-file connector implemented | Connector preview and commit endpoints | Strict known-host verification; no polling, scheduled sync, or file deduplication |
| SQL Server | Bounded connector primitive implemented | Connector preview and commit endpoints | Microsoft ODBC Driver 18 required; no live source connection verified; manual one-shot watermark |

### How to read the status table

- **Parser support:** Input bytes can be parsed into source records.
- **Preview support:** Mapping and schema validation run without writing catalog data.
- **Backend commit path:** An authenticated endpoint can persist reviewed valid records and record rejected rows.
- **Mock-tested connector:** Code paths are exercised with mocks. This does not prove compatibility with a live supplier system.
- **Live verified:** A successful connection against a real source using a least-privilege credential.
- **Generally available:** A released, supported capability with operational controls. This status is not claimed for any connector or multi-format persistence workflow.

No REST, SFTP, or SQL Server source has been live-verified for this project.

## 2. Canonical intermediate representation

The `parse_source` dispatcher handles CSV, XLSX, XLS, JSON, and XML. Each adapter returns a `ParsedSource` containing format, headers, metadata, and `SourceRecord` entries.

Each record preserves its source location:
- CSV row.
- Worksheet and row.
- JSON item.
- XML element.

Mapping and validation are handled in `record_import.py`. Persistence and tenant referential checks are handled in `catalog_ingestion.py`. Adapters do not write to the database, invent values, or infer relationships.

### Supported catalog record types

1. Products.
2. Product variants.
3. Supplier offers.
4. Inventory snapshots.
5. Product identifiers.

The format matrix covers all five record types across all five file formats: 25 parser-to-schema combinations. PostgreSQL-backed integration tests also commit all 25 combinations and verify import-job source metadata and row lineage. Separate database-backed tests cover explicit partial success and rejection of a cross-tenant product reference.

These tests do not replace live supplier connector verification.

## 3. Parsing and validation

- **CSV:** UTF-8 with BOM; comma, semicolon, tab, or pipe delimiter detection. Malformed quoting, duplicate headers, missing/extra row cells, oversized cells, and record-limit breaches are rejected.
- **XLSX:** Read-only workbook mode and data-only values. Preserves worksheet and row provenance; supports selected sheet and header row.
- **XLS:** Uses xlrd. Preserves worksheet and row provenance; supports selected sheet and header row.
- **JSON:** Nested objects are flattened into dotted paths. Ambiguous multiple record arrays require an explicit `record_path`; nested arrays are not guessed into relationships.
- **XML:** Uses defusedxml, local names for namespaced elements, repeated record groups, and explicit `record_tag` when multiple groups are plausible. Repeated child values within one record are rejected rather than silently overwritten.

All formats enforce bounded record, column, and cell sizes. Uploads are read only up to the configured byte limit plus one byte.

Manual mappings are record-type scoped. Automatic aliases are conservative; ambiguous source columns remain unmapped.

Duplicate detection covers in-file product SKUs, variant SKUs, supplier/SKU pairs, and typed identifier values. Database constraints handle conflicts with stored rows.

Required foreign keys are checked against the authenticated tenant at commit. A missing or cross-tenant reference rejects that row. CompatFlow does not auto-link by SKU, name, barcode, or supplier text.

Each valid row is persisted within a nested transaction. The import job records imported/rejected counts and row errors. The overall job is committed once, making partial success explicit.

The shared validator provides Pydantic schema/type validation and in-file duplicate checks. The legacy CSV product-quality scoring pipeline is separate; do not describe it as applying to JSON, XML, connector payloads, or all five record types.

## 4. REST API connector

The REST connector:
- Requires HTTPS and an exact hostname in `CONNECTOR_ALLOWED_HOSTS`.
- Rejects embedded URL credentials, redirects, private/local/reserved DNS results, and environment proxy configuration.
- Bounds response bytes and total records.
- Accepts JSON objects or arrays of objects.

Page-number pagination is opt-in and requires explicit page and page-size query parameter names. Defaults and limits:
- 20 pages maximum.
- 1,000 records per requested page.
- 10,000 total records.
- Two retries by default, with a maximum of five, for transient transport failures, HTTP 429, and HTTP 5xx responses.
- Retry-After is capped.

If the final permitted page is full, the run fails as potentially truncated rather than claiming a complete import.

Cursor pagination and vendor-specific next links are not implemented. Do not assume every supplier API uses page numbers or the configured records path.

Preview and commit requests are authenticated, tenant-scoped, plan-gated, and rate-limited through Redis (20 operations per organization per minute by default). If Redis is unavailable, connector execution fails closed before contacting the source.

Import history stores connector type and a sanitized host descriptor. Credentials and query tokens are not stored.

**Known SSRF limitation:** The hostname and DNS answers are checked, but the HTTP client resolves the hostname again when connecting. DNS answers are not pinned to the validation result, so DNS-rebinding resistance is incomplete. Keep the allowlist limited to operator-controlled, stable supplier hosts.

## 5. SFTP connector

SFTP requires an allowlisted host, absolute remote path, username, exactly one authentication method, and a managed `SFTP_KNOWN_HOSTS_PATH`.

Paramiko strict reject policy is used; unknown host keys are rejected. Reads are bounded to the configured upload limit plus one byte. Credentials are request-scoped and are not stored in CompatFlow.

Only one file is fetched per invocation. Directory polling, scheduled triggers, remote-file deduplication, retry/recovery orchestration, and durable background jobs are not implemented.

The supplier or operator must provision a read-only SFTP account with directory-level permissions.

## 6. SQL Server connector

SQL Server extraction is limited to a reflected schema/table and selected column projection. The connector issues a bounded SQLAlchemy SELECT; arbitrary SQL is not accepted.

### Runtime requirements

- Python pyodbc package.
- Microsoft ODBC Driver 18 for SQL Server installed in the backend runtime.
- Dedicated SQL-authenticated least-privilege login.
- `Encrypt=yes`.
- `TrustServerCertificate=no`.
- `ApplicationIntent=ReadOnly`.
- Server certificate trusted by the runtime CA store.

The backend Dockerfile installs Microsoft ODBC Driver 18 and checks that pyodbc can see it. This does not prove the deployed Render service uses that Dockerfile. Confirm the deployed runtime image before enabling SQL Server. The connector also checks the driver at execution time.

`ApplicationIntent=ReadOnly` is a client routing hint, not a permission boundary. The database administrator must grant the connector login SELECT only on the approved schema/table/view, with no write, DDL, or broader database permissions. CompatFlow cannot prove those grants from the connection URL.

### Incremental watermark

An optional watermark is supported only for a selected single-column primary key or single-column unique constraint with integer, numeric, date, or datetime type.

- A column that is only part of a composite primary key is not accepted as unique.
- The query applies `watermark_column > watermark_after` and orders ascending.
- The watermark column must be included in the selected projection.
- One sentinel row beyond the requested limit is fetched; if it exists, the run fails rather than accepting a potentially truncated batch.
- Import history stores previous and next values.
- The operator reviews and supplies the next value on the following run.

A monotonic unique key is required. Non-unique timestamps are rejected to avoid skipped ties. There is no automated checkpoint scheduler or durable incremental sync.

No real SQL Server connection or least-privilege permission test has passed. Do not describe SQL Server as operational until a live connection and permission test succeed.

## 7. AI-assisted mapping

`POST /api/v1/catalog/import/suggest-mappings` is an explicit opt-in suggestion endpoint.

It sends headers and up to five bounded sample values per header to a configured HTTPS OpenAI-compatible provider. Candidate fields are allowlisted by record type. Evidence must match submitted headers or sample values. Confidence is model-reported and uncalibrated. Every suggestion requires human confirmation.

Configuration:
- `MAPPING_AI_BASE_URL`
- `MAPPING_AI_API_KEY`
- `MAPPING_AI_MODEL`

No provider credentials are configured in the reviewed environment, so live AI suggestions are not verified. Manual and deterministic mapping remain available. No model is trained.

The 72-example benchmark seed is an evaluation seed, not a training corpus. Keep source families separate in held-out evaluation; do not train on the seed or unconfirmed AI predictions.

## 8. UI and rollout boundaries

- The file upload UI currently performs validation and preview; it does not expose the backend file commit endpoint.
- The connector UI exposes one-shot preview and commit, but does not expose all API pagination or SQL watermark settings.
- UI wording and controls must be updated before claiming complete multi-format or connector support.
- Do not change subscription entitlements or pricing as part of ingestion work.
- Multi-format and connector routes retain the existing `supplier_catalogs` feature gate. The legacy CSV validator retains its `csv_validation` gate.
- A plan gate does not prove that an external integration is live-compatible.

## 9. Remaining work

- Complete source-configuration management and an encrypted credential vault.
- Add API cursor/next-link adapters where supplier contracts require them.
- Add SFTP polling, triggers, remote-file deduplication, and retry/recovery orchestration.
- Add durable SQL Server watermark checkpoint management. Composite-key pagination remains unsupported until a safe tie-breaking cursor is designed.
- Verify DNS pinning and connection-level SSRF controls.
- Run live, least-privilege tests against approved REST, SFTP, and SQL Server test sources.
- Update UI labels so preview-only, mock-tested, live-verified, and generally available capabilities are distinct.
