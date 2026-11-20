# Multi-source ingestion

## Capability status

CompatFlow treats file extensions and source connectors as separate adapter families. CSV, Excel, JSON, and XML are parsed into the same source-preserving intermediate representation before mapping, validation, and persistence.

| Input | Parser / preview | Backend commit path | Current boundary |
|---|---|---|---|
| CSV (.csv) | Implemented | Shared multi-format commit endpoint | Public product-quality CSV validation remains a separate legacy path |
| Excel (.xlsx) | Implemented | Shared multi-format commit endpoint | Read-only workbook mode; selected sheet and header row |
| Excel (.xls) | Implemented | Shared multi-format commit endpoint | Legacy XLS reader; selected sheet and header row |
| JSON (.json) | Implemented | Shared multi-format commit endpoint | Object/array records, nested object flattening, explicit path for ambiguous arrays |
| XML (.xml) | Implemented | Shared multi-format commit endpoint | Safe parser, namespace-local names, repeated record groups; explicit record tag for ambiguity |
| REST API | One-shot connector implemented | Connector preview and commit endpoints | Page-number pagination only; bounded retries; no generic cursor/next-link support |
| SFTP | One-file connector implemented | Connector preview and commit endpoints | Strict known-host verification; no polling, scheduled sync, or file deduplication |
| SQL Server | Bounded connector primitive implemented | Connector preview and commit endpoints | Microsoft ODBC Driver 18 required; no live source connection verified; one-shot/manual watermark |

**Status vocabulary**

- **Parser support** means bytes can be parsed safely into source records.
- **Preview support** means deterministic mapping and schema validation run without writing catalog data.
- **Backend commit path** means an authenticated endpoint can persist reviewed valid records and record rejected rows.
- **Mock-tested connector** means code paths are exercised with mocks; it does not prove compatibility with a supplier live system.
- **Live verified** requires a successful connection against a real source with a least-privilege credential. No REST, SFTP, or SQL Server source has been live-verified for this project.
- **Generally available** is not claimed for any connector or multi-format persistence workflow yet.

## Canonical intermediate representation

The parse_source dispatcher handles .csv, .xlsx, .xls, .json, and .xml. Each adapter returns a ParsedSource with format, headers, metadata, and SourceRecord entries. A record preserves its source location (CSV row, worksheet and row, JSON item, or XML element) and optional source key.

Mapping and validation live in record_import.py; persistence and tenant referential checks live in catalog_ingestion.py. Adapters do not write to the database, invent values, or infer relationships.

The five catalog record types are:

1. products
2. product_variants
3. supplier_offers
4. inventory_snapshots
5. product_identifiers

The format matrix tests each of these five record types against all five file formats (25 parser-to-schema combinations). A PostgreSQL-backed integration test now also commits all 25 file-format/record-type combinations and verifies import-job source metadata and row lineage. Separate database-backed tests verify explicit partial success and rejection of a cross-tenant product reference. These tests do not replace live supplier connector verification.

## Parsing and validation rules

- CSV accepts UTF-8 with BOM and detects comma, semicolon, tab, or pipe delimiters. Malformed quoting, duplicate headers, missing/extra row cells, oversized cells, and record-limit breaches are rejected.
- XLSX uses read-only workbook mode and data-only values. XLS uses xlrd. Both preserve worksheet/row provenance and accept a selected sheet and header row.
- JSON flattens nested objects into dotted paths. Ambiguous multiple record arrays require an explicit record_path; nested arrays are not guessed into relationships.
- XML uses defusedxml, local names for namespaced elements, repeated record groups, and explicit record_tag when more than one group is plausible. Repeated child values inside one record are rejected rather than silently overwritten.
- All formats enforce bounded record, column, and cell sizes. Uploads are read only up to the configured byte limit plus one byte.
- Manual mappings are record-type-scoped. Automatic aliases are conservative; ambiguous source columns remain unmapped.
- Duplicate detection covers in-file product SKUs, variant SKUs, supplier/SKU pairs, and typed identifier values. Database constraints handle conflicts with already stored rows.
- Required foreign keys are checked against the authenticated tenant at commit. A missing or cross-tenant reference rejects that row; CompatFlow does not auto-link by SKU, name, barcode, or supplier text.
- Each valid row is persisted within a nested transaction; the import job records imported/rejected counts and row errors. The overall job is committed once, so partial success is explicit rather than silently dropping rows.

The shared validator currently provides Pydantic schema/type validation and in-file duplicate checks. The legacy CSV product-quality scoring pipeline is not the shared validator and must not be described as applying to JSON, XML, connector payloads, or all five record types.

## REST API connector

fetch_api_records requires HTTPS and an exact CONNECTOR_ALLOWED_HOSTS hostname. It rejects embedded URL credentials, redirects, private/local/reserved DNS results, and environment proxy configuration. Response bytes and total records are bounded. The connector accepts only JSON objects or arrays of objects.

Page-number pagination is opt-in and requires explicit page and page-size query parameter names. Limits are 20 pages, 1,000 records per requested page, and 10,000 total records by default. Transient transport failures, HTTP 429, and HTTP 5xx responses receive bounded retries (two by default, at most five); Retry-After is capped. If the last permitted page is full, the run fails as potentially truncated rather than claiming a complete import.

Cursor-based pagination and vendor-specific next links are not implemented. Do not assume every supplier API uses page numbers or returns the configured records path.

Connector preview and commit requests are authenticated, tenant-scoped, plan-gated, and rate-limited through Redis (20 operations per organization per minute by default). If Redis is unavailable, connector execution fails closed before contacting the source. Committed imports record the connector type and a sanitized host descriptor; credentials and query tokens are not stored.

The hostname is checked against the allowlist and its DNS answers are checked for private/local addresses. The current HTTP client resolves the hostname again when connecting; DNS answers are not pinned to the validation result, so DNS-rebinding resistance is not complete. Keep the allowlist limited to operator-controlled, stable supplier hosts.

## SFTP connector

SFTP requires an allowlisted host, absolute remote path, username, exactly one authentication method, and a managed SFTP_KNOWN_HOSTS_PATH. Paramiko strict reject policy is used; unknown host keys are rejected. The read is bounded to the configured upload limit plus one byte. Credentials are request-scoped and are not stored in CompatFlow.

Only a single file is fetched per invocation. Directory polling, scheduled triggers, remote-file deduplication, retry/recovery orchestration, and durable background jobs are not implemented. A read-only SFTP account and directory-level permissions must be provisioned by the supplier/operator.

## SQL Server connector

SQL Server extraction is limited to a reflected schema/table and selected column projection. It issues a SQLAlchemy SELECT with a bounded row limit; arbitrary SQL is not accepted.

Required connection properties:

- Python pyodbc package.
- Microsoft ODBC Driver 18 for SQL Server installed in the backend runtime.
- SQL-authenticated, dedicated least-privilege login (not integrated authentication).
- Encrypt=yes, TrustServerCertificate=no, and ApplicationIntent=ReadOnly.
- A server certificate trusted by the runtime CA store.

The backend Dockerfile installs Microsoft ODBC Driver 18 and verifies that pyodbc.drivers() can see it. This does not establish that the deployed Render service uses this Dockerfile; confirm the actual runtime image before enabling SQL Server. The connector checks the driver at execution time.

ApplicationIntent=ReadOnly is a client routing hint, not a permission boundary. The database administrator must create a dedicated login with only SELECT permission on the approved schema/table/view and no write, DDL, or broader database permissions. CompatFlow cannot prove those grants from the connection URL.

An optional incremental watermark is supported only for a selected single-column primary key or single-column unique constraint with an integer, numeric, date, or datetime type. A column that is merely one part of a composite primary key is not accepted as unique. The query applies watermark_column > watermark_after, orders ascending, and returns the watermark column in the selected projection. The query fetches one sentinel row beyond the requested limit and fails if that row exists, rather than silently accepting a potentially truncated batch. The import history stores the previous and next values. The operator must review and supply the next value on the following run. A monotonic unique key is required; non-unique timestamps are rejected to avoid skipped ties. There is no automated checkpoint scheduler or durable incremental sync.

No real SQL Server connection or least-privilege permission test has passed. Do not label SQL Server operational until a live connection and permission test succeeds.

## UI and rollout boundary

The file upload UI currently performs validation/preview; it does not expose the backend file commit endpoint. The connector UI exposes one-shot preview and commit, but does not expose all API pagination or SQL watermark settings yet. UI wording and controls must be updated before claiming complete multi-format or connector support.

Do not change subscription entitlements or pricing as part of ingestion work. Multi-format and connector routes retain the existing supplier_catalogs feature gate; the legacy CSV validator retains its existing csv_validation gate. A plan gate is not a claim that an external integration is live-compatible.

## Remaining work

- Complete source-configuration management and an encrypted credential vault; current credentials are request-scoped only.
- Add API cursor/next-link adapters where supplier contracts require them, with source-specific pagination tests.
- Add SFTP polling/trigger, remote-file deduplication, and retry/recovery orchestration.
- Add durable SQL Server watermark checkpoint management. Composite-key watermark pagination is deliberately unsupported until a safe tie-breaking cursor is designed.
- Verify DNS pinning/connection-level SSRF controls for API destinations.
- Run live, least-privilege tests against approved REST, SFTP, and SQL Server test sources before enabling broader product claims.
- Update UI controls and labels so preview-only, mock-tested, live-verified, and generally available capabilities cannot be confused.
