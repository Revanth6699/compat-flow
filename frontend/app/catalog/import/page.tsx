"use client";

import { useState } from "react";
import { useAuth } from "@/components/auth-provider";
import { apiRequest } from "@/lib/auth-client";

type PreviewRow = {
  sku: string; name: string; manufacturer: string; part_number: string;
  category: string; compatibility?: string | null; replacement_sku?: string | null;
};
type RowIssue = {
  row_number: number; field: string | null; error_code: string; message: string;
  severity: "critical" | "warning"; category: string; recommendation: string;
};
type MultiResult = {
  filename: string; format: string; record_type: string; total_records: number;
  valid_records: number; invalid_records: number;
  mappings: { field: string; source_header: string; confidence: number }[];
  unmapped_headers: string[];
  field_completeness: { field: string; populated: number; missing: number; completeness_pct: number }[];
  errors: { source_location: string; field: string | null; error_code: string; message: string }[];
  preview: Record<string, unknown>[];
  persisted: false; validation_scope: string; referential_checks: string;
};
type AiMappingResult = {
  status: string; message: string;
  suggestions: { source_header: string; candidate_field: string; confidence: number; rationale: string; evidence: string[]; requires_confirmation: boolean }[];
  source_data_sent: boolean;
};
const recordFields: Record<string, string[]> = {
  products: ["sku", "name", "manufacturer", "part_number", "category", "supplier_id", "replacement_sku"],
  product_variants: ["product_id", "variant_sku", "attributes", "is_active"],
  supplier_offers: ["supplier_id", "product_id", "supplier_sku", "supplier_product_id", "unit_price", "currency", "unit_of_measure", "minimum_order_quantity", "lead_time_days", "source_url", "status"],
  inventory_snapshots: ["product_id", "supplier_offer_id", "warehouse_code", "quantity_on_hand", "quantity_reserved", "quantity_available", "snapshot_at", "source_reference"],
  product_identifiers: ["product_id", "identifier_type", "namespace", "value", "source_reference", "is_primary"],
};
type PreviewResponse = {
  filename: string; profile_id: string; records_with_issues: number; duplicate_sku_count: number; duplicate_rate: number; issue_density: number; critical_record_rate: number; total_rows: number; valid_rows: number; invalid_rows: number;
  validation_pass_rate: number; data_quality_score: number; total_issues: number;
  critical_issues: number; warning_issues: number; errors: string[];
  issue_categories: { category: string; count: number }[];
  field_metrics: { field: string; populated: number; missing: number; completeness_pct: number }[];
  column_mappings: { field: string; source_header: string; confidence: number }[];
  unmapped_headers: string[];
  preview: PreviewRow[]; row_errors: RowIssue[];
};

export default function CatalogImportPage() {
  const { user } = useAuth();
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<PreviewResponse | null>(null);
  const [multiResult, setMultiResult] = useState<MultiResult | null>(null);
  const [recordType, setRecordType] = useState("products");
  const [aiConsent, setAiConsent] = useState(false);
  const [aiResult, setAiResult] = useState<AiMappingResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [profileId, setProfileId] = useState("general");
  const [manualMapping, setManualMapping] = useState<Record<string, string>>({});
  const canonicalFields = ["sku", "name", "manufacturer", "part_number", "category", "compatibility", "replacement_sku"];

  function handleFileChange(selectedFile: File | null) {
    setFile(selectedFile); setResult(null); setMultiResult(null); setAiResult(null); setAiConsent(false); setError("");
    if (!selectedFile) return;
    const extension = selectedFile.name.split(".").pop()?.toLowerCase();
    if (!["csv", "xlsx", "xls", "json", "xml"].includes(extension ?? "")) {
      setFile(null); setError("Supported file formats: CSV, XLSX, XLS, JSON and XML."); return;
    }
    if (selectedFile.size > 5 * 1024 * 1024) {
      setFile(null); setError("The file exceeds the 5 MB limit.");
    }
  }

  async function handleValidate() {
    if (!file || loading) return;
    setLoading(true); setError(""); setResult(null); setMultiResult(null);
    try {
      const formData = new FormData(); formData.append("file", file);
      const extension = file.name.split(".").pop()?.toLowerCase();
      if (extension !== "csv" || recordType !== "products") {
        if (!user) throw new Error("Sign in to validate Excel, JSON, XML, or non-product catalog records.");
        formData.append("record_type", recordType);
        if (Object.keys(manualMapping).length) formData.append("column_mapping_json", JSON.stringify(Object.fromEntries(Object.entries(manualMapping).filter(([, value]) => value))));
        const data = await apiRequest<MultiResult>("/api/v1/catalog/import/validate-records", { method: "POST", body: formData });
        setMultiResult(data);
        setManualMapping(Object.fromEntries(data.mappings.map((item) => [item.field, item.source_header])));
        return;
      }
      formData.append("profile_id", profileId);
      if (Object.keys(manualMapping).length) formData.append("column_mapping_json", JSON.stringify(Object.fromEntries(Object.entries(manualMapping).filter(([, value]) => value))));
      if (user) {
        const data = await apiRequest<PreviewResponse>("/api/v1/catalog/import/validate", { method: "POST", body: formData });
        setResult(data);
        setManualMapping(Object.fromEntries(data.column_mappings.map((item) => [item.field, item.source_header])));
      } else {
        const response = await fetch("/api/catalog/import/preview", { method: "POST", body: formData });
        const data = await response.json();
        if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "The backend could not validate this CSV.");
        const parsed = data as PreviewResponse;
        setResult(parsed);
        setManualMapping(Object.fromEntries(parsed.column_mappings.map((item) => [item.field, item.source_header])));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong while validating the file.");
    } finally { setLoading(false); }
  }

  async function handleSuggestMappings() {
    if (!file || !user || !aiConsent || loading) return;
    setLoading(true); setError(""); setAiResult(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("record_type", recordType);
      formData.append("ai_opt_in", "true");
      const data = await apiRequest<AiMappingResult>("/api/v1/catalog/import/suggest-mappings", { method: "POST", body: formData });
      setAiResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI mapping suggestions could not be generated.");
    } finally { setLoading(false); }
  }

  function applyAiSuggestions() {
    if (!aiResult) return;
    setManualMapping((current) => ({
      ...current,
      ...Object.fromEntries(aiResult.suggestions.map((item) => [item.candidate_field, item.source_header])),
    }));
  }

  function downloadReport() {
    if (!result) return;
    const report = [
      ["CompatFlow CSV Validation Report", result.filename],
      ["Total records", result.total_rows],
      ["Valid records", result.valid_rows],
      ["Invalid records", result.invalid_rows],
      ["Validation pass rate (%)", result.validation_pass_rate],
      ["Data quality score (%)", result.data_quality_score],
      ["Total issues", result.total_issues],
      ["Critical issues", result.critical_issues],
      ["Warnings", result.warning_issues],
      ["Records with issues", result.records_with_issues],
      ["Duplicate SKU count", result.duplicate_sku_count],
      ["Duplicate SKU rate (%)", result.duplicate_rate],
      ["Issue density (issues per record)", result.issue_density],
      ["Critical record rate (%)", result.critical_record_rate],
      ["Catalog profile", result.profile_id],
      [],
      ["Canonical field", "Detected source header", "Mapping confidence"],
      ...result.column_mappings.map((m) => [m.field, m.source_header, m.confidence]),
      [],
      ["Field", "Populated", "Missing", "Completeness (%)"],
      ...result.field_metrics.map((m) => [m.field, m.populated, m.missing, m.completeness_pct]),
      [],
      ["Row", "Field", "Severity", "Category", "Issue", "Recommended action"],
      ...result.row_errors.map((i) => [i.row_number, i.field ?? "General", i.severity, i.category, i.message, i.recommendation]),
    ];
    const csv = report.map((row) => row.map((v) => {
      const value = String(v ?? "");
      return `"${value.replace(/"/g, '""')}"`;
    }).join(",")).join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = "compatflow-validation-report.csv"; anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <main id="main" className="page">
      <div className="container">
        <div className="import-heading">
          <div className="eyebrow">Public product demo</div>
          <h1>Validate a supplier catalog</h1>
          <p>Inspect structured catalog files, map fields to the right record type, and review deterministic validation results before persistence.</p>
        </div>

        <section className="panel import-panel">
          <h2>Catalog file validation</h2>
          <p className="import-description">CSV, XLSX, XLS, JSON and XML · Maximum 5 MB per upload. The public demo remains CSV-only; multi-format and non-product validation require an authenticated account with the supplier catalog feature.</p>
          <label className="column-hint" htmlFor="record-type">Target catalog record type</label>
          <select id="record-type" value={recordType} onChange={(event) => { setRecordType(event.target.value); setResult(null); setMultiResult(null); setManualMapping({}); setAiResult(null); }}>
            <option value="products">Products</option><option value="product_variants">Product variants</option><option value="supplier_offers">Supplier offers</option><option value="inventory_snapshots">Inventory snapshots</option><option value="product_identifiers">Product identifiers</option>
          </select>
          <label className="column-hint" htmlFor="catalog-profile">Catalog profile</label>
          <select id="catalog-profile" value={profileId} onChange={(event) => { setProfileId(event.target.value); setResult(null); setManualMapping({}); }}><option value="general">General product catalog</option><option value="automotive">Automotive parts</option><option value="electronics">Electronics</option><option value="industrial">Industrial components</option></select>
          <p className="import-description">Files are validated in memory. This public demo does not save files or modify a catalog.</p>
          <p className="column-hint">CompatFlow detects common supplier header variants and maps them to the product catalog fields.</p>
          <p className="column-hint"><a href="/sample_supplier_catalog.csv" download>Download the sample supplier catalog</a></p>
          <label className="file-picker" htmlFor="catalog-file">
            <span className="file-picker-icon" aria-hidden="true">↥</span>
            <strong>{file ? file.name : "Choose a catalog file"}</strong>
            <span>{file ? `${(file.size / 1024).toFixed(1)} KB` : "Select a file from your computer"}</span>
          </label>
          <input id="catalog-file" className="visually-hidden" type="file" accept=".csv,.xlsx,.xls,.json,.xml,text/csv,application/json,application/xml"
            onChange={(event) => handleFileChange(event.target.files?.[0] ?? null)} />
          <div className="import-actions">
            <button className="button" type="button" onClick={handleValidate} disabled={!file || loading}>
              {loading ? "Validating..." : "Validate file"}
            </button>
            <button className="button button-secondary" type="button" disabled={loading} onClick={() => {
              setFile(null); setResult(null); setMultiResult(null); setAiResult(null); setAiConsent(false); setError("");
              const input = document.getElementById("catalog-file") as HTMLInputElement | null;
              if (input) input.value = "";
            }}>Clear</button>
          </div>
          {error && <div className="import-error" role="alert">{error}</div>}
        </section>

        {file && user && (
          <section className="panel result-section" aria-live="polite">
            <h3>AI-assisted mapping suggestions</h3>
            <p className="import-description">AI is optional. If enabled and a provider is configured, CompatFlow sends the source headers and up to five bounded sample values per header to that external HTTPS provider. Suggestions are never applied automatically.</p>
            <label><input type="checkbox" checked={aiConsent} onChange={(event) => { setAiConsent(event.target.checked); setAiResult(null); }} /> I consent to sending this bounded sample evidence to the configured AI provider for mapping suggestions.</label>
            <button className="button button-secondary" type="button" onClick={handleSuggestMappings} disabled={!aiConsent || loading}>Suggest mappings with AI</button>
            {aiResult && <><p className="import-description">{aiResult.message} {aiResult.source_data_sent ? "Sample evidence was sent to the configured provider." : "No sample evidence was sent."}</p>
              {aiResult.suggestions.length > 0 && <><ul className="error-list">{aiResult.suggestions.map((item, index) => <li key={index}><strong>{item.source_header} → {item.candidate_field}</strong> ({Math.round(item.confidence * 100)}%): {item.rationale}<br />Evidence: {item.evidence.join("; ")}</li>)}</ul>
                <button className="button button-secondary" type="button" onClick={applyAiSuggestions}>Apply suggestions to mapping form</button></>}
            </>}
          </section>
        )}
        {multiResult && (
          <section className="import-results" aria-live="polite">
            <div className="results-heading">
              <div><div className="eyebrow">Validation complete</div><h2>{multiResult.record_type.replaceAll("_", " ")} results</h2><p>{multiResult.filename} · {multiResult.format.toUpperCase()}</p></div>
              <span className={multiResult.invalid_records === 0 ? "result-status success" : "result-status warning"}>{multiResult.invalid_records === 0 ? "All records passed schema checks" : "Review required"}</span>
            </div>
            <div className="result-stats">
              <div className="panel stat-card"><span>Total records</span><strong>{multiResult.total_records.toLocaleString()}</strong></div>
              <div className="panel stat-card"><span>Valid records</span><strong>{multiResult.valid_records.toLocaleString()}</strong></div>
              <div className="panel stat-card"><span>Invalid records</span><strong>{multiResult.invalid_records.toLocaleString()}</strong></div>
            </div>
            <div className="panel result-section">
              <h3>Field mapping</h3>
              <p className="import-description">Automatic matches are conservative. Review and confirm every mapping before revalidating.</p>
              <div className="table-scroll"><table className="preview-table"><thead><tr><th>Canonical field</th><th>Source column</th><th>Confidence</th></tr></thead><tbody>
                {recordFields[recordType].map((field) => <tr key={field}><td>{field.replaceAll("_", " ")}</td><td>
                  <select aria-label={"Source column for " + field} value={manualMapping[field] ?? ""} onChange={(event) => setManualMapping((current) => ({ ...current, [field]: event.target.value }))}>
                    <option value="">Not mapped</option>{[...new Set([...multiResult.mappings.map((item) => item.source_header), ...multiResult.unmapped_headers])].map((header) => <option key={header} value={header}>{header}</option>)}
                  </select>
                </td><td>{(multiResult.mappings.find((item) => item.field === field)?.confidence ?? 0) * 100}%</td></tr>)}
              </tbody></table></div>
              <button className="button button-secondary" type="button" onClick={handleValidate} disabled={loading || !file}>Revalidate with selected mapping</button>
              {multiResult.unmapped_headers.length > 0 && <p className="import-description">Unmapped columns: {multiResult.unmapped_headers.join(", ")}</p>}
            </div>
            <div className="panel result-section">
              <h3>Required field completeness</h3>
              <div className="table-scroll"><table className="preview-table"><thead><tr><th>Field</th><th>Populated</th><th>Missing</th><th>Completeness</th></tr></thead><tbody>
                {multiResult.field_completeness.map((item) => <tr key={item.field}><td>{item.field}</td><td>{item.populated}</td><td>{item.missing}</td><td>{item.completeness_pct.toFixed(2)}%</td></tr>)}
              </tbody></table></div>
            </div>
            <div className="panel result-section">
              <h3>Validation issues</h3>
              {multiResult.errors.length === 0 ? <p>No schema or in-file duplicate issues found. Referential checks have not run.</p> : <ul className="error-list">{multiResult.errors.map((item, index) => <li key={index}><strong>{item.source_location} · {item.field ?? "Record"}</strong>: {item.message} ({item.error_code})</li>)}</ul>}
              <h3>Valid record preview</h3>
              <p className="import-description">These records passed schema and in-file duplicate checks only. Nothing has been saved.</p>
              {multiResult.preview.map((item, index) => <pre key={index} className="code-preview">{JSON.stringify(item, null, 2)}</pre>)}
              <p className="import-disclaimer">Persistence is not implemented in this workflow. Referential checks are not run.</p>
            </div>
          </section>
        )}
        {result && (
          <section className="import-results" aria-live="polite">
            <div className="results-heading">
              <div><div className="eyebrow">Validation complete</div><h2>Validation results</h2><p>{result.filename}</p></div>
              <span className={result.invalid_rows === 0 ? "result-status success" : "result-status warning"}>
                {result.invalid_rows === 0 ? "All records passed" : "Review required"}
              </span>
            </div>

            <div className="result-stats">
              <div className="panel stat-card"><span>Total records</span><strong>{result.total_rows.toLocaleString()}</strong></div>
              <div className="panel stat-card"><span>Valid records</span><strong>{result.valid_rows.toLocaleString()}</strong></div>
              <div className="panel stat-card"><span>Invalid records</span><strong>{result.invalid_rows.toLocaleString()}</strong></div>
              <div className="panel stat-card"><span>Quality score</span><strong>{result.data_quality_score.toFixed(2)}%</strong></div>
              <div className="panel stat-card"><span>Pass rate</span><strong>{result.validation_pass_rate.toFixed(2)}%</strong></div>
              <div className="panel stat-card"><span>Total issues</span><strong>{result.total_issues.toLocaleString()}</strong></div>
            </div>

            <div className="panel result-section">
              <h3>Column mapping</h3>
              <p className="import-description">Confidence indicates how closely a source header matches a known alias. It is not a measure of data accuracy. Unrecognized columns are preserved in the source file but are not used by this product-catalog profile.</p>
              <div className="table-scroll"><table className="preview-table"><thead><tr><th>Product field</th><th>Source column</th><th>Mapping confidence</th></tr></thead>
                <tbody>{result.column_mappings.map((mapping) => <tr key={mapping.field}>
                  <td>{mapping.field.replaceAll("_", " ")}</td><td>{mapping.source_header}</td><td>{(mapping.confidence * 100).toFixed(0)}%</td>
                </tr>)}</tbody></table></div>
              <p className="import-description">Adjust source columns below and revalidate. Each source column can map to only one canonical field.</p>
              <div className="table-scroll"><table className="preview-table"><thead><tr><th>Canonical field</th><th>Source column</th></tr></thead><tbody>{canonicalFields.map((field) => <tr key={field}><td>{field.replaceAll("_", " ")}</td><td><select aria-label={"Source column for " + field} value={manualMapping[field] ?? ""} onChange={(event) => setManualMapping((current) => ({ ...current, [field]: event.target.value }))}><option value="">Not mapped</option>{[...new Set([...result.column_mappings.map((item) => item.source_header), ...result.unmapped_headers])].map((header) => <option key={header} value={header}>{header}</option>)}</select></td></tr>)}</tbody></table></div>
              <button className="button button-secondary" type="button" onClick={handleValidate} disabled={loading || !file}>Revalidate with selected mapping</button>
              {result.unmapped_headers.length > 0 && <p className="import-description">Unmapped columns: {result.unmapped_headers.join(", ")}</p>}
            </div>

            <div className="panel result-section">
              <div className="results-heading"><div><h3>Issue overview</h3><p className="import-description">Critical: blocks the record from passing. Warning: requires review but does not block it.</p></div>
                <button className="button button-secondary" type="button" onClick={downloadReport}>Download report</button>
              </div>
              <div className="result-stats">
                <div className="stat-card"><span>Records with issues</span><strong>{result.records_with_issues}</strong></div>
                <div className="stat-card"><span>Duplicate SKU rate</span><strong>{result.duplicate_rate.toFixed(2)}%</strong></div>
                <div className="stat-card"><span>Issue density</span><strong>{result.issue_density.toFixed(3)}</strong></div>
                <div className="stat-card"><span>Critical record rate</span><strong>{result.critical_record_rate.toFixed(2)}%</strong></div>
                <div className="stat-card"><span>Critical issues</span><strong>{result.critical_issues}</strong></div>
                <div className="stat-card"><span>Warnings</span><strong>{result.warning_issues}</strong></div>
              </div>
              {result.issue_categories.length > 0 ? (
                <ul className="error-list">{result.issue_categories.map((item) =>
                  <li key={item.category}><strong>{item.category.replaceAll("_", " ")}</strong>: {item.count}</li>
                )}</ul>
              ) : <p>No issues detected by the current rule set.</p>}
            </div>

            <div className="panel result-section">
              <h3>Required-field completeness</h3>
              <p className="import-description">Completeness is the percentage of records with a non-empty value for each required field.</p>
              <div className="table-scroll"><table className="preview-table"><thead><tr><th>Field</th><th>Populated</th><th>Missing</th><th>Completeness</th></tr></thead>
                <tbody>{result.field_metrics.map((metric) => <tr key={metric.field}>
                  <td>{metric.field}</td><td>{metric.populated}</td><td>{metric.missing}</td><td>{metric.completeness_pct.toFixed(2)}%</td>
                </tr>)}</tbody></table></div>
            </div>

            <div className="panel result-section">
              <h3>Issues requiring review</h3>
              <p className="import-description">Showing up to 50 issue details. The downloadable report contains the returned issue set.</p>
              {result.row_errors.length === 0 ? <p>No row-level issues were found.</p> : (
                <div className="table-scroll"><table className="preview-table"><thead><tr><th>Row</th><th>Field</th><th>Severity</th><th>Category</th><th>Reason</th><th>Recommended action</th></tr></thead>
                  <tbody>{result.row_errors.slice(0, 50).map((item, index) => <tr key={`${item.row_number}-${item.error_code}-${index}`}>
                    <td>{item.row_number}</td><td>{item.field ?? "General"}</td><td>{item.severity}</td><td>{item.category.replaceAll("_", " ")}</td><td>{item.message}</td><td>{item.recommendation}</td>
                  </tr>)}</tbody></table></div>
              )}
            </div>

            <div className="panel result-section">
              <h3>Valid record preview</h3>
              <p className="import-description">Showing up to the first 10 accepted records.</p>
              {result.preview.length === 0 ? <p>No valid records to preview.</p> : (
                <div className="table-scroll"><table className="preview-table"><thead><tr><th>SKU</th><th>Product</th><th>Manufacturer</th><th>Part number</th><th>Category</th><th>Compatibility</th><th>Replacement SKU</th></tr></thead>
                  <tbody>{result.preview.map((row, index) => <tr key={`${row.sku}-${index}`}>
                    <td>{row.sku}</td><td>{row.name}</td><td>{row.manufacturer}</td><td>{row.part_number}</td><td>{row.category}</td><td>{row.compatibility || "—"}</td><td>{row.replacement_sku || "—"}</td>
                  </tr>)}</tbody></table></div>
              )}
            </div>
            <p className="import-disclaimer">The score is a transparent rule-based heuristic, not a statistical accuracy measurement. It reflects only the current product-catalog validation rules.</p>
          </section>
        )}
        <p className="import-disclaimer">Demonstration only. Do not upload confidential supplier files, personal information or production catalog data.</p>
      </div>
    </main>
  );
}
