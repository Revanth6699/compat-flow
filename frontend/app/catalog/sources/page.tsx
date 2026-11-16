"use client";

import { useState } from "react";
import { AuthRequired } from "@/components/auth-required";
import { apiRequest } from "@/lib/auth-client";

type SourceType = "rest_api" | "sftp" | "sql_server";
const RECORD_FIELDS = {
  products: ["sku", "name", "manufacturer", "part_number", "category", "replacement_sku"],
  product_variants: ["product_id", "variant_sku", "attributes", "is_active"],
  supplier_offers: ["supplier_id", "product_id", "supplier_sku", "supplier_product_id", "unit_price", "currency", "unit_of_measure", "minimum_order_quantity", "lead_time_days", "source_url", "status"],
  inventory_snapshots: ["product_id", "supplier_offer_id", "warehouse_code", "quantity_on_hand", "quantity_reserved", "quantity_available", "snapshot_at", "source_reference"],
  product_identifiers: ["product_id", "identifier_type", "namespace", "value", "source_reference", "is_primary"],
} as const;
type RecordType = keyof typeof RECORD_FIELDS;
type MappingSuggestion = {
  source_header: string;
  candidate_field: string;
  confidence: number;
  rationale: string;
  evidence: string[];
  requires_confirmation: boolean;
};
type ClassificationSuggestion = {
  record_type: RecordType;
  confidence: number;
  rationale: string;
  evidence: string[];
  requires_confirmation: boolean;
};
type AiResult = {
  status: string;
  message: string;
  classification: ClassificationSuggestion | null;
  suggestions: MappingSuggestion[];
  confidence_calibration: string;
  source_data_sent: boolean;
};
type Preview = {
  source_type: string;
  source_descriptor: string;
  filename: string;
  format: string;
  record_type: RecordType;
  total_records: number;
  valid_records: number;
  invalid_records: number;
  mappings: { field: string; source_header: string; confidence: number }[];
  unmapped_headers: string[];
  errors: { source_location: string; field?: string | null; message: string }[];
  preview: Record<string, unknown>[];
  ai: AiResult;
  persisted: boolean;
};
type FormState = {
  api_url: string; api_token: string; api_records_path: string;
  sftp_host: string; sftp_port: string; sftp_username: string; sftp_password: string; sftp_private_key: string; sftp_remote_path: string;
  sql_server_url: string; sql_schema: string; sql_table: string; sql_columns: string; sql_row_limit: string;
};
const initialForm: FormState = {
  api_url: "", api_token: "", api_records_path: "",
  sftp_host: "", sftp_port: "22", sftp_username: "", sftp_password: "", sftp_private_key: "", sftp_remote_path: "",
  sql_server_url: "", sql_schema: "dbo", sql_table: "", sql_columns: "", sql_row_limit: "1000",
};

function SourcesContent() {
  const [sourceType, setSourceType] = useState<SourceType>("rest_api");
  const [recordType, setRecordType] = useState<RecordType>("products");
  const [form, setForm] = useState<FormState>(initialForm);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [columnMapping, setColumnMapping] = useState<Record<string, string>>({});
  const [mappingDirty, setMappingDirty] = useState(false);
  const [aiConsent, setAiConsent] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [committed, setCommitted] = useState(false);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm(current => ({ ...current, [key]: value }));
    setPreview(null); setColumnMapping({}); setMappingDirty(false); setCommitted(false); setNotice("");
  }

  function payload(aiOptIn = false) {
    const common = {
      source_type: sourceType,
      record_type: recordType,
      column_mapping: Object.keys(columnMapping).length ? columnMapping : null,
      ai_opt_in: aiOptIn,
    };
    if (sourceType === "rest_api") {
      return { ...common, api_url: form.api_url.trim(), api_records_path: form.api_records_path.trim() || null,
        api_headers: form.api_token.trim() ? { Authorization: form.api_token.trim().startsWith("Bearer ") ? form.api_token.trim() : `Bearer ${form.api_token.trim()}` } : {} };
    }
    if (sourceType === "sftp") {
      return { ...common, sftp_host: form.sftp_host.trim(), sftp_port: Number(form.sftp_port), sftp_username: form.sftp_username.trim(),
        sftp_password: form.sftp_password || null, sftp_private_key: form.sftp_private_key || null, sftp_remote_path: form.sftp_remote_path.trim() };
    }
    return { ...common, sql_server_url: form.sql_server_url.trim(), sql_schema: form.sql_schema.trim(), sql_table: form.sql_table.trim(),
      sql_columns: form.sql_columns.split(",").map(value => value.trim()).filter(Boolean), sql_row_limit: Number(form.sql_row_limit) };
  }

  async function runPreview(requestAi = aiConsent) {
    if (busy) return;
    setBusy(true); setError(""); setNotice(""); setPreview(null); setCommitted(false);
    try {
      const result = await apiRequest<Preview>("/api/v1/catalog/import/connectors/preview", {
        method: "POST",
        body: JSON.stringify(payload(requestAi)),
      });
      setPreview(result);
      setColumnMapping(Object.fromEntries(result.mappings.map(item => [item.field, item.source_header])));
      setMappingDirty(false);
      setNotice("Source preview completed. Review record type, mappings and rejected rows before committing.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "The source preview failed.");
    } finally {
      setBusy(false);
    }
  }

  async function commitImport() {
    if (!preview || busy || committed || mappingDirty || preview.valid_records < 1) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await apiRequest<{ id: string; status: string; filename: string }>(
        "/api/v1/catalog/import/connectors/commit",
        { method: "POST", body: JSON.stringify(payload(false)) },
      );
      setCommitted(true);
      setNotice(`Import created: ${result.filename} (${result.status}).`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The import could not be committed.");
    } finally {
      setBusy(false);
    }
  }

  function changeRecordType(value: RecordType) {
    setRecordType(value);
    setColumnMapping({});
    setMappingDirty(false);
    setPreview(null);
    setCommitted(false);
    setNotice("Record type changed. Preview the source again before committing.");
  }

  function useClassification(suggestion: ClassificationSuggestion) {
    if (!suggestion.requires_confirmation) return;
    changeRecordType(suggestion.record_type);
  }

  function useMappingSuggestion(suggestion: MappingSuggestion) {
    if (!suggestion.requires_confirmation) return;
    setColumnMapping(current => ({ ...current, [suggestion.candidate_field]: suggestion.source_header }));
    setMappingDirty(true);
    setCommitted(false);
  }

  function changeMapping(field: string, sourceHeader: string) {
    setColumnMapping(current => {
      const next = { ...current };
      if (sourceHeader) next[field] = sourceHeader;
      else delete next[field];
      return next;
    });
    setMappingDirty(true);
    setCommitted(false);
  }

  function clearCredentials() {
    setForm(initialForm);
    setPreview(null);
    setColumnMapping({});
    setMappingDirty(false);
    setAiConsent(false);
    setError("");
    setNotice("");
    setCommitted(false);
  }

  const availableHeaders = preview
    ? [...new Set([...preview.mappings.map(item => item.source_header), ...preview.unmapped_headers])]
    : [];

  return <main id="main" className="page"><div className="container">
    <header className="workspace-heading"><div><span className="eyebrow">INPUT SOURCES</span><h1>Connect a supplier source</h1><p>Preview data from an approved API, SFTP server or SQL Server before importing it into your organization workspace.</p></div><a className="button button-secondary" href="/catalog/import">Back to file upload</a></header>
    <section className="panel import-panel">
      <p className="import-description">Connector ingestion requires a Growth, Business or Enterprise subscription and an operator-allowlisted source host. Credentials are sent for this request only and are not saved as reusable connection settings.</p>
      <label className="column-hint" htmlFor="source-type">Source type</label>
      <select id="source-type" value={sourceType} onChange={event => {
        setSourceType(event.target.value as SourceType); setPreview(null); setColumnMapping({});
        setMappingDirty(false); setCommitted(false); setError(""); setNotice("");
      }}>
        <option value="rest_api">REST API</option><option value="sftp">SFTP server</option><option value="sql_server">Microsoft SQL Server</option>
      </select>
      <label className="column-hint" htmlFor="record-type">Catalog record type</label>
      <select id="record-type" value={recordType} onChange={event => changeRecordType(event.target.value as RecordType)}>
        {Object.keys(RECORD_FIELDS).map(value => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}
      </select>
      {sourceType === "rest_api" && <div className="auth-form">
        <label htmlFor="api-url">API endpoint URL</label><input id="api-url" type="url" required value={form.api_url} onChange={e => update("api_url", e.target.value)} placeholder="https://supplier.example.com/products" />
        <label htmlFor="api-token">API bearer token or API key</label><input id="api-token" type="password" autoComplete="off" value={form.api_token} onChange={e => update("api_token", e.target.value)} placeholder="Credential for this request" />
        <label htmlFor="api-record-path">Records path (optional)</label><input id="api-record-path" value={form.api_records_path} onChange={e => update("api_records_path", e.target.value)} placeholder="e.g. data.items" />
        <p className="import-description">The current connector supports one response or explicitly configured page-number pagination. Cursor and next-link pagination are not supported.</p>
      </div>}
      {sourceType === "sftp" && <div className="auth-form">
        <label htmlFor="sftp-host">SFTP host</label><input id="sftp-host" required value={form.sftp_host} onChange={e => update("sftp_host", e.target.value)} placeholder="sftp.supplier.example.com" />
        <label htmlFor="sftp-port">Port</label><input id="sftp-port" type="number" min="1" max="65535" required value={form.sftp_port} onChange={e => update("sftp_port", e.target.value)} />
        <label htmlFor="sftp-user">Username</label><input id="sftp-user" required value={form.sftp_username} onChange={e => update("sftp_username", e.target.value)} />
        <label htmlFor="sftp-path">Remote file path</label><input id="sftp-path" required value={form.sftp_remote_path} onChange={e => update("sftp_remote_path", e.target.value)} placeholder="/exports/products.csv" />
        <label htmlFor="sftp-password">Password (use only one authentication method)</label><input id="sftp-password" type="password" autoComplete="new-password" value={form.sftp_password} onChange={e => update("sftp_password", e.target.value)} />
        <label htmlFor="sftp-key">Private key (alternative to password)</label><textarea id="sftp-key" rows={4} value={form.sftp_private_key} onChange={e => update("sftp_private_key", e.target.value)} placeholder="Paste the private key for this one-time connection" />
        <p className="import-description">SFTP uses strict known-host verification. A read-only supplier account and operator-managed known-host entry are required. This is a one-file operation; polling and file deduplication are not available.</p>
      </div>}
      {sourceType === "sql_server" && <div className="auth-form">
        <label htmlFor="sql-url">SQL Server connection URL</label><input id="sql-url" type="password" autoComplete="off" required value={form.sql_server_url} onChange={e => update("sql_server_url", e.target.value)} placeholder="mssql+pyodbc://..." />
        <p className="import-description">Use a dedicated SQL-authenticated login with SELECT-only grants on the approved table/view. TLS encryption and certificate verification are required; Microsoft ODBC Driver 18 must be installed. Live source connectivity is not yet verified by CompatFlow.</p>
        <label htmlFor="sql-schema">Schema</label><input id="sql-schema" required value={form.sql_schema} onChange={e => update("sql_schema", e.target.value)} />
        <label htmlFor="sql-table">Table or view</label><input id="sql-table" required value={form.sql_table} onChange={e => update("sql_table", e.target.value)} />
        <label htmlFor="sql-columns">Columns (comma-separated)</label><input id="sql-columns" required value={form.sql_columns} onChange={e => update("sql_columns", e.target.value)} placeholder="sku, name, manufacturer, part_number, category" />
        <label htmlFor="sql-limit">Maximum rows to read (1–10,000)</label><input id="sql-limit" type="number" min="1" max="10000" required value={form.sql_row_limit} onChange={e => update("sql_row_limit", e.target.value)} />
      </div>}
      <div className="panel result-section">
        <h3>Optional AI suggestions</h3>
        <p className="import-description">AI can suggest a catalog record type and field mappings. If enabled and a provider is configured, only up to 80 source headers and the first five records are sent to the external HTTPS provider; header names longer than 128 characters are excluded from AI requests and each sample value is clipped to 120 characters. Connector credentials are not included. Confidence is model-reported and uncalibrated. Suggestions require your confirmation and never trigger an import.</p>
        <label><input type="checkbox" checked={aiConsent} onChange={event => setAiConsent(event.target.checked)} /> I consent to sending this bounded sample evidence to the configured AI provider.</label>
      </div>
      <div className="import-actions">
        <button className="button" type="button" onClick={() => void runPreview()} disabled={busy}>{busy ? "Connecting…" : "Preview source"}</button>
        <button className="button button-secondary" type="button" onClick={clearCredentials}>Clear credentials</button>
      </div>
      {error && <p className="auth-error" role="alert">{error}</p>}{notice && <p className="auth-success" role="status">{notice}</p>}
    </section>
    {preview && <section className="panel result-section" aria-live="polite">
      <div className="results-heading"><div><h2>Source preview</h2><p>{preview.filename} · {preview.format}</p></div><span className="result-status">{preview.total_records.toLocaleString()} records</span></div>
      <div className="result-stats">
        <div className="stat-card"><span>Valid</span><strong>{preview.valid_records.toLocaleString()}</strong></div>
        <div className="stat-card"><span>Invalid</span><strong>{preview.invalid_records.toLocaleString()}</strong></div>
        <div className="stat-card"><span>Source</span><strong>{preview.source_type.replace("_", " ")}</strong></div>
      </div>
      <h3>AI record-type classification</h3>
      <p className="import-description">{preview.ai.message} {preview.ai.source_data_sent ? "Bounded sample evidence was sent to the provider." : "No sample evidence was sent."}</p>
      {preview.ai.classification && <div className="panel">
        <p><strong>{preview.ai.classification.record_type.replaceAll("_", " ")}</strong> — model-reported {Math.round(preview.ai.classification.confidence * 100)}% (uncalibrated)</p>
        <p>{preview.ai.classification.rationale}</p>
        <p className="import-description">Evidence: {preview.ai.classification.evidence.join("; ")}</p>
        <button className="button button-secondary" type="button" onClick={() => useClassification(preview.ai.classification!)} disabled={!preview.ai.classification.requires_confirmation}>Use suggested record type</button>
      </div>}
      {preview.ai.suggestions.length > 0 && <>
        <h3>AI field-mapping suggestions</h3>
        <ul className="error-list">{preview.ai.suggestions.map((item, index) => <li key={index}>
          <strong>{item.source_header} → {item.candidate_field}</strong> — model-reported {Math.round(item.confidence * 100)}% (uncalibrated): {item.rationale}
          <br />Evidence: {item.evidence.join("; ")}
          <br /><button className="button button-secondary" type="button" onClick={() => useMappingSuggestion(item)} disabled={!item.requires_confirmation}>Confirm this mapping</button>
        </li>)}</ul>
      </>}
      <h3>Review field mappings</h3>
      <p className="import-description">Select or change source columns. Any change requires a new preview before the import can be committed.</p>
      <div className="table-scroll"><table className="preview-table"><thead><tr><th>Catalog field</th><th>Source column</th></tr></thead><tbody>
        {RECORD_FIELDS[recordType].map(field => <tr key={field}>
          <td>{field.replaceAll("_", " ")}</td>
          <td><select aria-label={`Source column for ${field}`}
            value={columnMapping[field] ?? preview.mappings.find(item => item.field === field)?.source_header ?? ""}
            onChange={event => changeMapping(field, event.target.value)}>
            <option value="">Not mapped</option>
            {availableHeaders.map(header => <option key={header} value={header}>{header}</option>)}
          </select></td>
        </tr>)}
      </tbody></table></div>
      {mappingDirty && <button className="button button-secondary" type="button" onClick={() => void runPreview(false)} disabled={busy}>Revalidate with confirmed mappings</button>}
      {preview.errors.length > 0 && <ul className="error-list">{preview.errors.slice(0, 20).map((item, index) => <li key={index}><strong>{item.source_location} · {item.field || "Record"}</strong>: {item.message}</li>)}</ul>}
      <div className="code-preview">{JSON.stringify(preview.preview, null, 2)}</div>
      <p className="import-description">Preview checks schema and in-file duplicates. Referential checks run during commit. Nothing is saved until you explicitly commit.</p>
      <button className="button" type="button" onClick={() => void commitImport()} disabled={busy || committed || mappingDirty || preview.valid_records < 1}>{busy ? "Importing…" : committed ? "Import created" : "Commit valid records"}</button>
    </section>}
  </div></main>;
}

export default function CatalogSourcesPage() {
  return <AuthRequired><SourcesContent /></AuthRequired>;
}
