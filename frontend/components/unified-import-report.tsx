"use client";

import DatasetCharts from "@/components/dataset-charts";

type DatasetProfile = {
  filename: string; format: string; dataset_type: string; total_records: number; total_columns: number;
  total_cells: number; populated_cells: number; missing_cells: number; completeness_pct: number;
  complete_records: number | null; incomplete_records: number | null; complete_records_pct: number | null;
  duplicate_rows: number; duplicate_rate_pct: number;
  columns: { name: string; populated: number; missing: number; completeness_pct: number; distinct_values: number; inferred_type: string }[];
  categorical_distributions: { name: string; values: { value: string; count: number; pct: number }[] }[];
  date_columns: string[]; numeric_columns: string[];
  relationship_checks: { name: string; from_column: string; to_column: string; matched_records: number; average_days: number | null; minimum_days: number | null; maximum_days: number | null; negative_duration_records: number }[];
  findings: { severity: string; title: string; detail: string }[];
  domain_checks?: { code: string; title: string; issue_records: number; severity: string; detail: string; recommendation: string }[];
  preview: Record<string, unknown>[];
};
type IndustryResult = {
  filename: string; profile_id: string | null; total_rows: number; valid_rows: number; invalid_rows: number;
  validation_pass_rate: number; column_mappings: { field: string; source_header: string; confidence: number }[];
  unmapped_headers: string[]; field_metrics: { field: string; applicable: boolean; populated: number; missing: number; completeness_pct: number }[];
  issues: { row_number: number; field: string | null; error_code: string; message: string; severity: string }[];
  preview: Record<string, unknown>[]; metrics: { mapping_coverage_pct: number; validation_pass_rate_pct: number; issue_count: number; critical_issue_count: number; warning_issue_count: number };
  validation_scope: string;
};
type MultiResult = {
  filename: string; format: string; record_type: string; total_records: number; valid_records: number; invalid_records: number;
  mappings: { field: string; source_header: string; confidence: number }[]; unmapped_headers: string[];
  field_completeness: { field: string; populated: number; missing: number; completeness_pct: number }[];
  errors: { source_location: string; field: string | null; error_code: string; message: string }[];
  preview: Record<string, unknown>[]; validation_scope: string; referential_checks: string;
};
type PreviewResponse = {
  filename: string; total_rows: number; valid_rows: number; invalid_rows: number; validation_pass_rate: number;
  data_quality_score: number; total_issues: number; critical_issues: number; warning_issues: number;
  column_mappings: { field: string; source_header: string; confidence: number }[];
  field_metrics: { field: string; populated: number; missing: number; completeness_pct: number }[];
  unmapped_headers: string[];
  preview: Record<string, unknown>[]; row_errors: { row_number: number; field: string | null; error_code: string; message: string; severity: string; category: string; recommendation: string }[];
};

type Props = {
  datasetResult: DatasetProfile | null;
  industryResult: IndustryResult | null;
  multiResult: MultiResult | null;
  result: PreviewResponse | null;
  onDownloadCsv: () => void;
  onDownloadJson: () => void;
  onPrint: () => void;
};

function Table({ headers, rows }: { headers: string[]; rows: Record<string, unknown>[] }) {
  if (!rows.length) return <p>No records available for preview.</p>;
  return <div className="table-scroll"><table className="preview-table"><thead><tr>{headers.map((header) => <th key={header}>{header.replaceAll("_", " ")}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index}>{headers.map((header) => <td key={header}>{row[header] === null || row[header] === undefined || row[header] === "" ? "—" : typeof row[header] === "object" ? JSON.stringify(row[header]) : String(row[header])}</td>)}</tr>)}</tbody></table></div>;
}

export default function UnifiedImportReport({ datasetResult, industryResult, multiResult, result, onDownloadCsv, onDownloadJson, onPrint }: Props) {
  if (!datasetResult && !industryResult && !multiResult && !result) return null;

  const filename = datasetResult?.filename ?? industryResult?.filename ?? multiResult?.filename ?? result?.filename ?? "Uploaded dataset";
  const format = datasetResult?.format ?? multiResult?.format ?? filename.split(".").pop() ?? "unknown";
  const total = datasetResult?.total_records ?? industryResult?.total_rows ?? multiResult?.total_records ?? result?.total_rows ?? 0;
  const valid = industryResult?.valid_rows ?? multiResult?.valid_records ?? result?.valid_rows ?? null;
  const invalid = industryResult?.invalid_rows ?? multiResult?.invalid_records ?? result?.invalid_rows ?? null;
  const completeness = datasetResult?.completeness_pct ?? null;
  const passRate = industryResult?.validation_pass_rate ?? result?.validation_pass_rate ?? (multiResult && total ? multiResult.valid_records / total * 100 : null);
  const profileTitle = datasetResult?.dataset_type ?? industryResult?.profile_id?.replaceAll("_", " ") ?? multiResult?.record_type.replaceAll("_", " ") ?? "Product catalog";
  const mappings = industryResult?.column_mappings ?? multiResult?.mappings ?? result?.column_mappings ?? [];
  const fieldMetrics = datasetResult?.columns.map((column) => ({ field: column.name, populated: column.populated, missing: column.missing, completeness_pct: column.completeness_pct, inferred_type: column.inferred_type })) ?? industryResult?.field_metrics ?? multiResult?.field_completeness ?? result?.field_metrics ?? [];
  const issues = datasetResult?.findings.map((finding) => ({ location: "Dataset", field: finding.title, severity: finding.severity, message: finding.detail, code: "PROFILE_FINDING" })) ??
    industryResult?.issues.map((issue) => ({ location: `Row ${issue.row_number}`, field: issue.field ?? "Record", severity: issue.severity, message: issue.message, code: issue.error_code })) ??
    multiResult?.errors.map((issue) => ({ location: issue.source_location, field: issue.field ?? "Record", severity: "warning", message: issue.message, code: issue.error_code })) ??
    result?.row_errors.map((issue) => ({ location: `Row ${issue.row_number}`, field: issue.field ?? "Record", severity: issue.severity, message: issue.message, code: issue.error_code })) ?? [];
  const preview = datasetResult?.preview ?? industryResult?.preview ?? multiResult?.preview ?? result?.preview ?? [];
  const previewHeaders = [...new Set(preview.slice(0, 10).flatMap((row) => Object.keys(row)))].slice(0, 12);

  return (
    <section className="import-results premium-report" aria-live="polite">
      <div className="results-heading">
        <div><div className="eyebrow">COMPATFLOW DATA INTELLIGENCE REPORT</div><h2>{profileTitle} overview</h2><p>{filename} · {format.toUpperCase()} · Stateless analysis</p></div>
        <span className={invalid === null || invalid === 0 ? "result-status success" : "result-status warning"}>{invalid === null ? "Analysis complete" : invalid === 0 ? "No validation errors" : "Review required"}</span>
      </div>

      <div className="report-actions no-print">
        <button className="button" type="button" onClick={onDownloadCsv}>Download CSV report</button>
        <button className="button button-secondary" type="button" onClick={onDownloadJson}>Download JSON</button>
        <button className="button button-secondary" type="button" onClick={onPrint}>Print / Save PDF</button>
      </div>

      <div className="result-stats premium-kpis">
        <div className="panel stat-card"><span>Total records</span><strong>{total.toLocaleString()}</strong><small>Rows analysed</small></div>
        <div className="panel stat-card"><span>Accepted records</span><strong className="metric-valid">{valid === null ? "Not calculated" : valid.toLocaleString()}</strong><small>{valid === null ? "Structural profile only" : "Passed current validation"}</small></div>
        <div className="panel stat-card"><span>Records needing review</span><strong className={invalid ? "metric-invalid" : "metric-valid"}>{invalid === null ? "Not calculated" : invalid.toLocaleString()}</strong><small>{invalid === null ? "No schema validation run" : "Failed current validation"}</small></div>
        <div className="panel stat-card"><span>Quality indicator</span><strong>{completeness !== null ? completeness.toFixed(2) + "%" : passRate !== null ? passRate.toFixed(2) + "%" : "Not available"}</strong><small>{completeness !== null ? "Cell completeness" : passRate !== null ? "Validation pass rate" : "Not calculated"}</small></div>
      </div>

      <div className="panel result-section">
        <div className="section-heading"><div><h3>Analysis summary</h3><p>Common report structure; metrics depend on the checks applicable to this dataset.</p></div></div>
        {valid !== null && invalid !== null ? <>
          <div className="validation-chart"><span className="chart-valid" style={{ width: `${total ? valid / total * 100 : 0}%` }} /><span className="chart-invalid" style={{ width: `${total ? invalid / total * 100 : 0}%` }} /></div>
          <p><span className="metric-valid">Accepted: {valid.toLocaleString()}</span> · <span className="metric-invalid">Needs review: {invalid.toLocaleString()}</span></p>
        </> : <><div className="metric-bar"><span style={{ width: `${completeness ?? 0}%` }} /></div><p>{datasetResult ? `${datasetResult.populated_cells.toLocaleString()} populated cells of ${datasetResult.total_cells.toLocaleString()} total cells.` : "Schema-level accepted and rejected counts are not available for this analysis."}</p></>}
      </div>

      {datasetResult && <DatasetCharts profile={datasetResult} />}

      {mappings.length > 0 && <div className="panel result-section">
        <h3>Column mapping</h3>
        <div className="table-scroll"><table className="preview-table"><thead><tr><th>Canonical field</th><th>Source column</th><th>Confidence</th></tr></thead><tbody>{mappings.map((item) => <tr key={item.field}><td>{item.field.replaceAll("_", " ")}</td><td>{item.source_header}</td><td>{(item.confidence * 100).toFixed(0)}%</td></tr>)}</tbody></table></div>
        {((industryResult?.unmapped_headers ?? multiResult?.unmapped_headers ?? result?.unmapped_headers) ?? []).length > 0 && <p className="import-description">Unmapped source columns retained: {(industryResult?.unmapped_headers ?? multiResult?.unmapped_headers ?? result?.unmapped_headers ?? []).join(", ")}</p>}
      </div>}

      {fieldMetrics.length > 0 && <div className="panel result-section">
        <h3>Column completeness and data types</h3>
        <div className="table-scroll"><table className="preview-table"><thead><tr><th>Field</th><th>Type</th><th>Populated</th><th>Missing</th><th>Completeness</th></tr></thead><tbody>{fieldMetrics.map((item) => <tr key={item.field}><td>{item.field}</td><td>{"inferred_type" in item ? String(item.inferred_type) : "—"}</td><td>{item.populated.toLocaleString()}</td><td>{item.missing.toLocaleString()}</td><td>{item.completeness_pct.toFixed(2)}%</td></tr>)}</tbody></table></div>
      </div>}

      {datasetResult && datasetResult.domain_checks && datasetResult.domain_checks.length > 0 && <div className="panel result-section">
        <h3>Dataset-specific validation checks</h3>
        <p className="import-description">These rules were selected from the detected dataset type and available columns. A zero issue count means the check ran and did not flag a record; it does not certify external or business-specific correctness.</p>
        <div className="table-scroll"><table className="preview-table"><thead><tr><th>Check</th><th>Severity</th><th>Records flagged</th><th>Finding</th><th>Recommended action</th></tr></thead><tbody>{datasetResult.domain_checks.map((check) => <tr key={check.code}><td>{check.title}</td><td>{check.severity}</td><td>{check.issue_records.toLocaleString()}</td><td>{check.detail}</td><td>{check.recommendation}</td></tr>)}</tbody></table></div>
      </div>}

      <div className="panel result-section">
        <h3>Findings and issues</h3>
        {issues.length === 0 ? <p>No issues were returned by the current analysis.</p> : <div className="table-scroll"><table className="preview-table"><thead><tr><th>Location</th><th>Field / finding</th><th>Severity</th><th>Code</th><th>Details</th></tr></thead><tbody>{issues.slice(0, 100).map((issue, index) => <tr key={index}><td>{issue.location}</td><td>{issue.field}</td><td>{issue.severity}</td><td>{issue.code}</td><td>{issue.message}</td></tr>)}</tbody></table></div>}
        <p className="import-description">The report includes only checks performed by the current analysis path. Unavailable external reference checks are not inferred.</p>
      </div>

      <div className="panel result-section">
        <h3>Source record preview</h3>
        <p className="import-description">Showing up to the first 10 records returned by the analysis endpoint. This is a preview, not a full-data export.</p>
        <Table headers={previewHeaders} rows={preview.slice(0, 10)} />
      </div>
      {industryResult && <p className="import-disclaimer">External vehicle fitment, certification, taxonomy and compatibility reference checks are not included unless explicitly provided by the active validation rules.</p>}
      {result && <p className="import-disclaimer">The score is a transparent rule-based heuristic, not a statistical accuracy measurement. It reflects only the current product-catalog validation rules.</p>}
    </section>
  );
}
