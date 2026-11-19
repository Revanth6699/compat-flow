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

Connector preview and commit requests are authenticated, tenant-scoped, plan-gated, and rate-limited through Redis (20 operations per organization per minute by default). If Redis is unavailable, connector execution fails closed before contacting the source. API credentials must be supplied through bounded Authorization or X-API-Key headers; credential-like query parameters are rejected to avoid placing secrets in URLs. Committed imports record the connector type and a sanitized host descriptor; credentials and query tokens are not stored.

The hostname is checked against the exact allowlist and resolved once per connector invocation. Every DNS answer must be globally routable; mixed public/private answers are rejected. The REST connector uses a pinned aiohttp resolver so TCP connects only to those validated IP addresses while TLS certificate verification, SNI, and the HTTP Host header continue to use the original hostname. Redirects and environment proxies are disabled. This closes the validation/connect DNS-rebinding gap for REST requests. Keep the allowlist limited to operator-controlled supplier hosts.

## SFTP connector

SFTP requires an allowlisted host, an absolute remote path without `.` or `..` path segments, a username, exactly one authentication method, and a managed SFTP_KNOWN_HOSTS_PATH. Paramiko strict reject policy is used; unknown host keys are rejected. Password authentication is supported. Private-key authentication accepts pasted, unencrypted PEM/OpenSSH private-key content and parses it in memory; the value is never treated as a server-side file path. Encrypted private keys/passphrases are not supported yet. Key material is bounded to 64 KiB. The file read is bounded to the configured upload limit plus one byte. Credentials are request-scoped and are not stored in CompatFlow.

The SFTP hostname is resolved once and every answer must be globally routable. CompatFlow opens the TCP socket directly to one of those validated IP addresses, then gives that socket to Paramiko while retaining the original hostname and port for known-host key verification. This avoids a second DNS lookup between validation and connection. Only a single file is fetched per invocation. Directory polling, scheduled triggers, remote-file deduplication, retry/recovery orchestration, and durable background jobs are not implemented. A read-only SFTP account and directory-level permissions must be provisioned by the supplier/operator.

## Saved connector configurations and credential vault

Authenticated organizations can create, list, and delete named REST API, SFTP, and SQL Server configurations through:

- POST /api/v1/catalog/import/connectors/configurations
- GET /api/v1/catalog/import/connectors/configurations
- DELETE /api/v1/catalog/import/connectors/configurations/{configuration_id}

Creation separates non-secret source settings from credentials. Credentials are encrypted with AES-256-GCM before persistence; the associated authenticated data binds the ciphertext to the organization, configuration ID, source type, and key version. Ciphertext is never returned by list/create endpoints. Connector preview/commit requests may supply configuration_id instead of inline source settings. The lookup is organization-scoped and source-type-scoped; inline source settings cannot be mixed with a saved configuration. Using a saved credential for preview or commit also requires the organization's `catalog:write` permission; a read-only catalog role cannot trigger a source request with stored credentials. The connector still revalidates the source at execution time, including the current host allowlist and DNS protections.

Set CONNECTOR_CREDENTIAL_ENCRYPTION_KEY to URL-safe base64 encoding of exactly 32 random bytes. Generate one outside the application and store it only in the backend secret manager. Do not commit it, put it in the database, or reuse APP_SECRET_KEY. Every backend instance that reads saved connector configurations must use the same key. Back up the key separately from the database. Losing or rotating the key without a planned re-encryption procedure makes existing saved credentials undecryptable. The vault fails closed when the key is absent or invalid; inline request-scoped connector credentials remain available for development/testing.

REST API header credentials, SFTP passwords/private keys, and SQL Server connection URLs are encrypted as one source-specific secret object. SQL Server connection URLs must still satisfy the ODBC Driver 18, TLS certificate verification, SQL authentication, and ApplicationIntent=ReadOnly checks. Saving a configuration does not prove that the remote account is read-only or that the source is reachable.

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

## AI-assisted record classification and mapping

The authenticated file endpoint `POST /api/v1/catalog/import/suggest-mappings` and authenticated connector preview endpoint `POST /api/v1/catalog/import/connectors/preview` use the same opt-in assistant. One provider request can return a record-type classification across all five catalog record types plus field-mapping suggestions restricted to the user's selected record type. This works after parsing CSV, XLSX, XLS, JSON, XML, REST API JSON, SFTP files, and SQL Server row projections into the shared source-record representation.

AI evidence is deliberately bounded before serialization: at most 80 source headers (headers longer than 128 characters are rejected for AI processing), the first five records, and at most 120 characters per sample value. The aggregate evidence budget is 64,000 characters and provider responses are limited to 64 KiB. A request exceeding these limits receives a bounded-input error; deterministic/manual mapping remains available. Connector credentials, connection URLs, API authorization headers, SFTP passwords/private keys, and SQL connection secrets are not passed to the AI helper.

AI requests require explicit user opt-in. If the provider is not configured, no source evidence is sent and the endpoint reports `provider_unconfigured`. Provider configuration uses `MAPPING_AI_BASE_URL`, `MAPPING_AI_API_KEY`, and `MAPPING_AI_MODEL`; all three are required and the base URL must use HTTPS. No provider credentials are configured in the current environment, so live AI suggestions are not verified.

The backend accepts only allowed record types and fields, verifies that each evidence item exactly matches a submitted header or bounded sample value, rejects duplicate source/target mapping suggestions, and marks every result as requiring confirmation. Classification and mapping confidence values are model-reported and uncalibrated; they are not data-quality metrics. The user must confirm a suggested record type or mapping before it is applied. Suggestions never authorize persistence, infer foreign-key relationships, or create catalog records.

The reviewed benchmark seed has 72 examples and is an evaluation seed, not a training corpus. Keep source families separated in any held-out evaluation; do not train on the seed or unconfirmed AI predictions. No model is trained.

## UI and rollout boundary

The authenticated file page exposes record-type selection and optional AI classification/mapping suggestions, but currently stops at validation and preview; it does not expose the backend file commit endpoint. The connector page exposes all five record types, one-shot preview and commit, optional AI suggestions, and reviewable field mappings. It still does not expose all API pagination or SQL watermark settings. The UI can create, list, select, and delete organization-scoped saved REST API, SFTP, and SQL Server configurations. Secrets are submitted only during creation and are not returned to the browser; selecting a saved configuration sends only its ID. Saved configurations fail closed until CONNECTOR_CREDENTIAL_ENCRYPTION_KEY is configured, and using a saved credential requires catalog:write permission. API pagination and SQL watermark controls are not yet fully exposed in the UI.

The UI must continue to distinguish public demo validation, authenticated parser/preview, backend commit paths, mock-tested connector primitives, and live-verified integrations. None of the REST API, SFTP, or SQL Server connectors is live-verified. Do not describe the full multi-source workflow as generally available.

Do not change subscription entitlements or pricing as part of ingestion work. Multi-format and connector routes retain the existing `supplier_catalogs` feature gate; the legacy CSV validator retains its existing `csv_validation` gate. A plan gate is not a claim that an external integration is live-compatible.

## Remaining work

- Add planned key rotation/re-encryption and formal audit events for connector configuration changes; the initial encrypted vault uses one operator-managed application key.
- Add API cursor/next-link adapters where supplier contracts require them, with source-specific pagination tests.
- Add SFTP polling/trigger, remote-file deduplication, and retry/recovery orchestration.
- Add durable SQL Server watermark checkpoint management. Composite-key watermark pagination is deliberately unsupported until a safe tie-breaking cursor is designed.

- Run live, least-privilege tests against approved REST, SFTP, and SQL Server test sources before enabling broader product claims.
- Update UI controls and labels so preview-only, mock-tested, live-verified, and generally available capabilities cannot be confused.
