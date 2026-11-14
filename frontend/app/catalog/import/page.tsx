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
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [profileId, setProfileId] = useState("general");
  const [manualMapping, setManualMapping] = useState<Record<string, string>>({});
  const canonicalFields = ["sku", "name", "manufacturer", "part_number", "category", "compatibility", "replacement_sku"];

  function handleFileChange(selectedFile: File | null) {
    setFile(selectedFile); setResult(null); setError("");
    if (!selectedFile) return;
    if (!selectedFile.name.toLowerCase().endsWith(".csv")) {
      setFile(null); setError("Only CSV files are supported."); return;
    }
    if (selectedFile.size > 5 * 1024 * 1024) {
      setFile(null); setError("The file exceeds the 5 MB limit.");
    }
  }

  async function handleValidate() {
    if (!file || loading) return;
    setLoading(true); setError(""); setResult(null);
    try {
      const formData = new FormData(); formData.append("file", file);
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
          <h1>Validate a supplier catalog CSV</h1>
          <p>Inspect record quality, field completeness, duplicate identifiers and actionable data issues before an import.</p>
        </div>

        <section className="panel import-panel">
          <h2>Try the CSV validator</h2>
          <p className="import-description">CSV only · Maximum 5 MB · Maximum 10,000 data rows (current validator limits).</p>
          <label className="column-hint" htmlFor="catalog-profile">Catalog profile</label>
          <select id="catalog-profile" value={profileId} onChange={(event) => { setProfileId(event.target.value); setResult(null); setManualMapping({}); }}><option value="general">General product catalog</option><option value="automotive">Automotive parts</option><option value="electronics">Electronics</option><option value="industrial">Industrial components</option></select>
          <p className="import-description">Files are validated in memory. This public demo does not save files or modify a catalog.</p>
          <p className="column-hint">CompatFlow detects common supplier header variants and maps them to the product catalog fields.</p>
          <p className="column-hint"><a href="/sample_supplier_catalog.csv" download>Download the sample supplier catalog</a></p>
          <label className="file-picker" htmlFor="catalog-file">
            <span className="file-picker-icon" aria-hidden="true">↥</span>
            <strong>{file ? file.name : "Choose a CSV file"}</strong>
            <span>{file ? `${(file.size / 1024).toFixed(1)} KB` : "Select a file from your computer"}</span>
          </label>
          <input id="catalog-file" className="visually-hidden" type="file" accept=".csv,text/csv"
            onChange={(event) => handleFileChange(event.target.files?.[0] ?? null)} />
          <div className="import-actions">
            <button className="button" type="button" onClick={handleValidate} disabled={!file || loading}>
              {loading ? "Validating..." : "Validate CSV"}
            </button>
            <button className="button button-secondary" type="button" disabled={loading} onClick={() => {
              setFile(null); setResult(null); setError("");
              const input = document.getElementById("catalog-file") as HTMLInputElement | null;
              if (input) input.value = "";
            }}>Clear</button>
          </div>
          {error && <div className="import-error" role="alert">{error}</div>}
        </section>

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
