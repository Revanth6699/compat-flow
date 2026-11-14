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

These modules provide parser and connector primitives. They do not yet constitute a complete end-user import workflow: record-type selection, mapping confirmation, deterministic validation across all five catalog record types, durable import jobs/lineage, scheduled API/SFTP/SQL Server polling, connector management UI, and transactional persistence still need to be wired and tested end to end. Do not label those capabilities generally available until that integration is complete.
