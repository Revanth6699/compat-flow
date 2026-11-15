"use client";

import { useState } from "react";
import { AuthRequired } from "@/components/auth-required";
import { apiRequest } from "@/lib/auth-client";

type SourceType = "rest_api" | "sftp" | "sql_server";
type Preview = { source_type: string; filename: string; format: string; total_records: number; valid_records: number; invalid_records: number; errors: { source_location: string; field?: string | null; message: string }[]; preview: Record<string, unknown>[]; persisted: boolean };
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
  const [form, setForm] = useState<FormState>(initialForm);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [committed, setCommitted] = useState(false);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm(current => ({ ...current, [key]: value }));
    setPreview(null); setCommitted(false); setNotice("");
  }

  function payload() {
    const common = { source_type: sourceType, record_type: "products" as const };
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

  async function runPreview() {
    if (busy) return;
    setBusy(true); setError(""); setNotice(""); setPreview(null); setCommitted(false);
    try {
      const result = await apiRequest<Preview>("/api/v1/catalog/import/connectors/preview", { method: "POST", body: JSON.stringify(payload()) });
      setPreview(result);
      setNotice("Source connected. Review the sample records before committing this import.");
    } catch (err) { setError(err instanceof Error ? err.message : "The source preview failed."); }
    finally { setBusy(false); }
  }

  async function commitImport() {
    if (!preview || busy || committed || preview.valid_records < 1) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await apiRequest<{ id: string; status: string; filename: string }>("/api/v1/catalog/import/connectors/commit", { method: "POST", body: JSON.stringify(payload()) });
      setCommitted(true);
      setNotice(`Import created: ${result.filename} (${result.status}).`);
    } catch (err) { setError(err instanceof Error ? err.message : "The import could not be committed."); }
    finally { setBusy(false); }
  }

  return <main id="main" className="page"><div className="container">
    <header className="workspace-heading"><div><span className="eyebrow">INPUT SOURCES</span><h1>Connect a supplier source</h1><p>Preview data from an approved API, SFTP server or SQL Server before importing it into your organization workspace.</p></div><a className="button button-secondary" href="/catalog/import">Back to file upload</a></header>
    <section className="panel import-panel">
      <p className="import-description">Connector ingestion requires a Growth, Business or Enterprise subscription and the source host must be allowlisted by the CompatFlow operator. Credentials are sent for this request only and are not saved as reusable connection settings.</p>
      <label className="column-hint" htmlFor="source-type">Source type</label>
      <select id="source-type" value={sourceType} onChange={event => { setSourceType(event.target.value as SourceType); setPreview(null); setCommitted(false); setError(""); setNotice(""); }}>
        <option value="rest_api">REST API</option><option value="sftp">SFTP server</option><option value="sql_server">Microsoft SQL Server</option>
      </select>
      {sourceType === "rest_api" && <div className="auth-form">
        <label htmlFor="api-url">API endpoint URL</label><input id="api-url" type="url" required value={form.api_url} onChange={e => update("api_url", e.target.value)} placeholder="https://supplier.example.com/products" />
        <label htmlFor="api-token">API bearer token or API key</label><input id="api-token" type="password" autoComplete="off" value={form.api_token} onChange={e => update("api_token", e.target.value)} placeholder="Credential for this request" />
        <label htmlFor="api-record-path">Records path (optional)</label><input id="api-record-path" value={form.api_records_path} onChange={e => update("api_records_path", e.target.value)} placeholder="e.g. data.items" />
      </div>}
      {sourceType === "sftp" && <div className="auth-form">
        <label htmlFor="sftp-host">SFTP host</label><input id="sftp-host" required value={form.sftp_host} onChange={e => update("sftp_host", e.target.value)} placeholder="sftp.supplier.example.com" />
        <label htmlFor="sftp-port">Port</label><input id="sftp-port" type="number" min="1" max="65535" required value={form.sftp_port} onChange={e => update("sftp_port", e.target.value)} />
        <label htmlFor="sftp-user">Username</label><input id="sftp-user" required value={form.sftp_username} onChange={e => update("sftp_username", e.target.value)} />
        <label htmlFor="sftp-path">Remote file path</label><input id="sftp-path" required value={form.sftp_remote_path} onChange={e => update("sftp_remote_path", e.target.value)} placeholder="/exports/products.csv" />
        <label htmlFor="sftp-password">Password (use only one authentication method)</label><input id="sftp-password" type="password" autoComplete="new-password" value={form.sftp_password} onChange={e => update("sftp_password", e.target.value)} />
        <label htmlFor="sftp-key">Private key (alternative to password)</label><textarea id="sftp-key" rows={4} value={form.sftp_private_key} onChange={e => update("sftp_private_key", e.target.value)} placeholder="Paste the private key for this one-time connection" />
      </div>}
      {sourceType === "sql_server" && <div className="auth-form">
        <label htmlFor="sql-url">SQL Server connection URL</label><input id="sql-url" type="password" autoComplete="off" required value={form.sql_server_url} onChange={e => update("sql_server_url", e.target.value)} placeholder="mssql+pyodbc://..." />
        <label htmlFor="sql-schema">Schema</label><input id="sql-schema" required value={form.sql_schema} onChange={e => update("sql_schema", e.target.value)} />
        <label htmlFor="sql-table">Table or view</label><input id="sql-table" required value={form.sql_table} onChange={e => update("sql_table", e.target.value)} />
        <label htmlFor="sql-columns">Columns (comma-separated)</label><input id="sql-columns" required value={form.sql_columns} onChange={e => update("sql_columns", e.target.value)} placeholder="sku, name, manufacturer, part_number, category" />
        <label htmlFor="sql-limit">Maximum rows to read (1–10,000)</label><input id="sql-limit" type="number" min="1" max="10000" required value={form.sql_row_limit} onChange={e => update("sql_row_limit", e.target.value)} />
      </div>}
      <div className="import-actions"><button className="button" type="button" onClick={runPreview} disabled={busy}>{busy ? "Connecting…" : "Preview source"}</button><button className="button button-secondary" type="button" onClick={() => { setForm(initialForm); setPreview(null); setError(""); setNotice(""); setCommitted(false); }}>Clear credentials</button></div>
      {error && <p className="auth-error" role="alert">{error}</p>}{notice && <p className="auth-success" role="status">{notice}</p>}
    </section>
    {preview && <section className="panel result-section" aria-live="polite">
      <div className="results-heading"><div><h2>Source preview</h2><p>{preview.filename} · {preview.format}</p></div><span className="result-status">{preview.total_records.toLocaleString()} records</span></div>
      <div className="result-stats"><div className="stat-card"><span>Valid</span><strong>{preview.valid_records.toLocaleString()}</strong></div><div className="stat-card"><span>Invalid</span><strong>{preview.invalid_records.toLocaleString()}</strong></div><div className="stat-card"><span>Source</span><strong>{preview.source_type.replace("_"," ")}</strong></div></div>
      {preview.errors.length > 0 && <ul className="error-list">{preview.errors.slice(0,20).map((item,index)=><li key={index}><strong>{item.source_location} · {item.field || "Record"}</strong>: {item.message}</li>)}</ul>}
      <div className="code-preview">{JSON.stringify(preview.preview, null, 2)}</div>
      <p className="import-description">Preview checks schema and in-file duplicates. Referential checks are not run at preview time.</p>
      <button className="button" type="button" onClick={commitImport} disabled={busy || committed || preview.valid_records < 1}>{busy ? "Importing…" : committed ? "Import created" : "Commit valid records"}</button>
    </section>}
  </div></main>;
}

export default function CatalogSourcesPage() {
  return <AuthRequired><SourcesContent /></AuthRequired>;
}
