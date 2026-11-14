# Multi-source ingestion architecture

## Supported input families

The ingestion layer is being built around a canonical, source-preserving intermediate representation. File parsers and source connectors must not implement business validation independently.

| Input | Adapter | Important behavior |
|---|---|---|
| CSV | `parse_csv` | UTF-8 BOM, comma/semicolon/tab/pipe delimiter detection, strict row shape |
| XLSX | `parse_excel` | Read-only workbook mode, selected worksheet, configurable header row |
| XLS | `parse_excel` | Legacy workbook reader, selected worksheet and header row |
| JSON | `parse_json` | Object/array input, nested object paths, explicit record path for ambiguous arrays |
| XML | `parse_xml` | Safe XML parser, namespaces, repeated record elements, explicit record tag |
| REST API | `fetch_api_records` | HTTPS only, host allowlist, bounded JSON response, no redirects |
| SFTP | `fetch_sftp_file` | SSH host-key verification, known-hosts file required, bounded file read |
| SQL Server | `fetch_sql_server_rows` | Read-only bounded projection, identifier allowlisting, SQL Server ODBC driver required |

## Canonical parser output

Each parser returns a `ParsedSource` containing a format, headers, metadata, and `SourceRecord` objects. Each record preserves its original source location (CSV row, Excel sheet/row, JSON item, or XML element) and an optional source key. Nested JSON/XML fields use dotted paths. No parser writes to the database or claims that a record is valid.

## Safety boundaries

- Enforce upload/response/record/column/cell limits before expensive work.
- XML parsing uses defusedxml and rejects unsafe entity/DTD constructs.
- API destinations must be HTTPS and explicitly allowlisted; redirects are disabled to reduce SSRF exposure.
- SFTP rejects unknown SSH host keys; a managed known-hosts file is mandatory.
- SQL Server access is read-only and only supports a validated schema/table/column projection. Configure a dedicated least-privilege SQL login and a verified ODBC driver. Never grant write permissions to the ingestion login.
- Supply credentials only through deployment secret storage. Never persist them in mapping templates or logs.
- API pagination, SFTP polling, and SQL Server incremental watermarks are orchestration concerns and must be explicit per source; do not assume every source uses the same pagination or change-tracking model.

## Current implementation boundary

Implemented on the feature branch:
- Format-neutral parsers for CSV, XLSX, XLS, JSON, and XML with source-location metadata.
- Authenticated, subscription-gated `POST /api/v1/catalog/import/parse-preview` and `POST /api/v1/catalog/import/validate-records` endpoints for structural preview and deterministic schema/file-duplicate validation across all five record types; neither persists records.
- An opt-in `POST /api/v1/catalog/import/suggest-mappings` endpoint that sends only bounded header/sample evidence to a configured HTTPS OpenAI-compatible provider after explicit opt-in; suggestions require human confirmation.
- Secure connector primitives for HTTPS API fetch, host-key-verified SFTP download, and bounded SQL Server read projections.
- An opt-in AI mapping provider interface with bounded evidence, HTTPS provider endpoint requirement, candidate-field allowlisting, source-evidence checks, and no-provider fallback.

Not yet an end-to-end production import workflow:
- The existing CSV-specific business validator remains separate; the new shared record validator currently performs schema/type validation and in-file duplicate checks, not all domain-specific business or database referential checks.
- The preview endpoint does not persist data.
- No connector configuration UI, encrypted credential vault, API pagination scheduler, SFTP polling/deduplication scheduler, or SQL Server incremental watermark scheduler exists.
- Durable job orchestration, retry/recovery, full row/item lineage storage, and transactional batch persistence remain to be implemented.
- The frontend does not yet expose format selectors, mapping review, or connector setup.
- AI suggestions are exposed through a backend endpoint only; the frontend mapping-review/consent UI is not implemented. No AI provider credentials are configured and no model has been trained.

Do not label these incomplete capabilities generally available. SQL Server requires the Python pyodbc package, Microsoft ODBC Driver 18, and a least-privilege read-only login in the runtime environment. Configure encryption and certificate verification; never disable TLS verification for a production source.
