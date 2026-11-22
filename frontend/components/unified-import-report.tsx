"use client";

import DatasetCharts from "@/components/dataset-charts";

type DatasetProfile = {
  filename: string; format: string; dataset_type: string; total_records: number; total_columns: number;
  total_cells: number; populated_cells: number; missing_cells: number; completeness_pct: number;
  complete_records: number | null; incomplete_records: number | null; complete_records_pct: number | null;
  duplicate_rows: number; duplicate_rate_pct: number;
  missing_value_details?: { row_number: number; field: string }[];
  missing_value_details_truncated?: boolean;
  columns: { name: string; populated: number; missing: number; completeness_pct: number; distinct_values: number; inferred_type: string }[];
  categorical_distributions: { name: string; values: { value: string; count: number; pct: number }[] }[];
  date_columns: string[]; numeric_columns: string[];
  relationship_checks: { name: string; from_column: string; to_column: string; matched_records: number; average_days: number | null; minimum_days: number | null; maximum_days: number | null; negative_duration_records: number }[];
  findings: { severity: string; title: string; detail: string }[];
  domain_checks?: { code: string; title: string; issue_records: number; severity: string; detail: string; recommendation: string }[];
  validation_rules?: { code: string; title: string; category: string; severity: string; status: "evaluated" | "not_applicable" | "not_evaluated"; records_evaluated: number; issue_records: number | null; detail: string; recommendation: string }[];
  field_mappings?: Record<string, string>;
  issue_details?: { row_number: number; product_id: string; field: string; source_value: string; code: string; title: string; severity: string; recommendation: string }[];
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
  const hasValidationCounts = valid !== null && invalid !== null;
  const completeness = datasetResult?.completeness_pct ?? null;
  const completeRecords = datasetResult?.complete_records ?? null;
  const incompleteRecords = datasetResult?.incomplete_records ?? null;
  const recordCompleteness = datasetResult?.complete_records_pct ?? null;
  const passRate = industryResult?.validation_pass_rate ?? result?.validation_pass_rate ?? (multiResult && total ? multiResult.valid_records / total * 100 : null);
  const unmappedIndustryColumns = industryResult?.unmapped_headers.length ?? 0;
  const profileTitle = datasetResult?.dataset_type ?? industryResult?.profile_id?.replaceAll("_", " ") ?? multiResult?.record_type.replaceAll("_", " ") ?? "Product catalog";
  const mappings = industryResult?.column_mappings ?? multiResult?.mappings ?? result?.column_mappings ?? [];
  const productFieldMappings = datasetResult?.field_mappings ?? {};
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
        <span className={industryResult && unmappedIndustryColumns > 0 ? "result-status warning" : invalid === null || invalid === 0 ? "result-status success" : "result-status warning"}>{industryResult && unmappedIndustryColumns > 0 ? "Partial coverage" : invalid === null ? "Analysis complete" : invalid === 0 ? "No validation errors" : "Review required"}</span>
      </div>

      <div className="report-actions no-print">
        <button className="button" type="button" onClick={onDownloadCsv}>Download CSV report</button>
        <button className="button button-secondary" type="button" onClick={onDownloadJson}>Download JSON</button>
        <button className="button button-secondary" type="button" onClick={onPrint}>Print / Save PDF</button>
      </div>

      <div className="result-stats premium-kpis">
        <div className="panel stat-card"><span>Total records</span><strong>{total.toLocaleString()}</strong><small>Rows in dataset</small></div>
        {datasetResult ? <>
          <div className="panel stat-card"><span>Complete records</span><strong className="metric-valid">{completeRecords === null ? "Unavailable" : completeRecords.toLocaleString()}</strong><small>{recordCompleteness === null ? "Record-level completeness not returned by API" : recordCompleteness.toFixed(2) + "% of rows fully populated"}</small></div>
          <div className="panel stat-card"><span>Incomplete records</span><strong className={incompleteRecords ? "metric-warning" : "metric-valid"}>{incompleteRecords === null ? "Unavailable" : incompleteRecords.toLocaleString()}</strong><small>{incompleteRecords === null ? "Record-level completeness not returned by API" : "At least one empty field"}</small></div>
        </> : <>
          <div className="panel stat-card"><span>Accepted records</span><strong className="metric-valid">{valid === null ? "—" : valid.toLocaleString()}</strong><small>{hasValidationCounts ? "Passed current validation" : "Not applicable to this result"}</small></div>
          <div className="panel stat-card"><span>Records needing review</span><strong className={invalid ? "metric-invalid" : "metric-valid"}>{invalid === null ? "—" : invalid.toLocaleString()}</strong><small>{hasValidationCounts ? "Failed current validation" : "Not applicable to this result"}</small></div>
        </>}
        <div className="panel stat-card"><span>{completeness !== null ? "Cell completeness" : industryResult ? "Pass rate on evaluated checks" : "Validation pass rate"}</span><strong>{completeness !== null ? completeness.toFixed(2) + "%" : passRate !== null ? passRate.toFixed(2) + "%" : "Unavailable"}</strong><small>{completeness !== null ? "Populated cells / total cells" : industryResult ? `Mapping coverage ${industryResult.metrics.mapping_coverage_pct.toFixed(1)}%; ${unmappedIndustryColumns} unmapped columns were not validated` : passRate !== null ? "Records passing current validation" : "No quality metric returned"}</small></div>
      </div>

      <div className="panel result-section">
        <div className="section-heading"><div><h3>Analysis summary</h3><p>Common report structure; metrics depend on the checks applicable to this dataset.</p></div></div>
        {datasetResult && completeRecords !== null && incompleteRecords !== null && recordCompleteness !== null ? <>
          <div className="metric-bar"><span style={{ width: `${recordCompleteness}%` }} /></div>
          <p><span className="metric-valid">Complete: {completeRecords.toLocaleString()}</span> · <span className="metric-warning">Incomplete: {incompleteRecords.toLocaleString()}</span> · {recordCompleteness.toFixed(2)}% of records have every field populated.</p>
          <p>{datasetResult.populated_cells.toLocaleString()} populated cells of {datasetResult.total_cells.toLocaleString()} total cells.</p>
        </> : hasValidationCounts ? <>
          <div className="validation-chart"><span className="chart-valid" style={{ width: `${total ? valid! / total * 100 : 0}%` }} /><span className="chart-invalid" style={{ width: `${total ? invalid! / total * 100 : 0}%` }} /></div>
          <p><span className="metric-valid">Accepted: {valid!.toLocaleString()}</span> · <span className="metric-invalid">Needs review: {invalid!.toLocaleString()}</span></p>
        </> : <><div className="metric-bar"><span style={{ width: `${completeness ?? 0}%` }} /></div><p>{datasetResult ? `${datasetResult.populated_cells.toLocaleString()} populated cells of ${datasetResult.total_cells.toLocaleString()} total cells.` : "Schema-level accepted and rejected counts are not applicable to this analysis."}</p></>}
      </div>

      {datasetResult && <DatasetCharts profile={datasetResult} />}

      {Object.keys(productFieldMappings).length > 0 && mappings.length === 0 && <details className="panel result-section report-detail">
        <summary><span>Product field mapping</span><small>{Object.keys(productFieldMappings).length} canonical fields mapped</small></summary>
        <h3>Product field mapping</h3>
        <p className="import-description">CompatFlow matched source columns to canonical product attributes. These are header-based mappings, not proof that the source values satisfy your organization&apos;s business rules.</p>
        <div className="table-scroll"><table className="preview-table"><thead><tr><th>Canonical product field</th><th>Source column</th></tr></thead><tbody>{Object.entries(productFieldMappings).map(([field, source]) => <tr key={field}><td>{field.replaceAll("_", " ")}</td><td>{source}</td></tr>)}</tbody></table></div>
      </details>}

      {mappings.length > 0 && <details className="panel result-section report-detail">
        <summary><span>Column mapping</span><small>{mappings.length} mapped fields{((industryResult?.unmapped_headers ?? multiResult?.unmapped_headers ?? result?.unmapped_headers) ?? []).length ? ` · ${((industryResult?.unmapped_headers ?? multiResult?.unmapped_headers ?? result?.unmapped_headers) ?? []).length} unmapped` : ""}</small></summary>
        <h3>Column mapping</h3>
        <div className="table-scroll"><table className="preview-table"><thead><tr><th>Canonical field</th><th>Source column</th><th>Confidence</th></tr></thead><tbody>{mappings.map((item) => <tr key={item.field}><td>{item.field.replaceAll("_", " ")}</td><td>{item.source_header}</td><td>{(item.confidence * 100).toFixed(0)}%</td></tr>)}</tbody></table></div>
        {((industryResult?.unmapped_headers ?? multiResult?.unmapped_headers ?? result?.unmapped_headers) ?? []).length > 0 && <p className="import-description">Unmapped source columns retained: {(industryResult?.unmapped_headers ?? multiResult?.unmapped_headers ?? result?.unmapped_headers ?? []).join(", ")}</p>}
      </details>}

      {fieldMetrics.length > 0 && <details className="panel result-section report-detail">
        <summary><span>Column completeness and data types</span><small>{fieldMetrics.length} columns</small></summary>
        <h3>Column completeness and data types</h3>
        <div className="table-scroll"><table className="preview-table"><thead><tr><th>Field</th><th>Type</th><th>Populated</th><th>Missing</th><th>Completeness</th></tr></thead><tbody>{fieldMetrics.map((item) => <tr key={item.field}><td>{item.field}</td><td>{"inferred_type" in item ? String(item.inferred_type) : "—"}</td><td>{item.populated.toLocaleString()}</td><td>{item.missing.toLocaleString()}</td><td>{item.completeness_pct.toFixed(2)}%</td></tr>)}</tbody></table></div>
      </details>}
      {(datasetResult?.missing_value_details?.length ?? 0) > 0 && <details className="panel result-section report-detail">
        <summary><span>Missing-value locations</span><small>{datasetResult!.missing_cells.toLocaleString()} missing cells</small></summary>
        <h3>Missing-value locations</h3>
        <p className="import-description">Each entry identifies the source row and column where a value is empty. The list is capped at 1,000 locations; the aggregate missing-cell count remains exact.</p>
        <div className="table-scroll"><table className="preview-table"><thead><tr><th>Source row</th><th>Source column</th></tr></thead><tbody>{datasetResult!.missing_value_details!.map((item, index) => <tr key={index}><td>{item.row_number}</td><td>{item.field}</td></tr>)}</tbody></table></div>
        {datasetResult!.missing_value_details_truncated && <p className="import-description">Showing the first 1,000 missing-value locations.</p>}
      </details>

      {datasetResult && datasetResult.validation_rules && datasetResult.validation_rules.length > 0 && <details className="panel result-section report-detail" open>
        <summary><span>Default validation rules</span><small>{datasetResult.validation_rules.filter(rule => rule.status === "evaluated").length} evaluated · {datasetResult.validation_rules.filter(rule => rule.status === "not_applicable").length} not applicable · {datasetResult.validation_rules.filter(rule => rule.status === "not_evaluated").length} not evaluated</small></summary>
        <h3>Default validation rules</h3>
        <p className="import-description">Rules are selected from the detected dataset profile. “Not applicable” means the rule belongs to another dataset type. “Not evaluated” means the rule was relevant but the required source columns were unavailable. Neither state is counted as a pass.</p>
        <div className="table-scroll"><table className="preview-table"><thead><tr><th>Rule</th><th>Category</th><th>Status</th><th>Records evaluated</th><th>Issues</th><th>Details</th></tr></thead><tbody>{datasetResult.validation_rules.map(rule => <tr key={rule.code}><td>{rule.title}</td><td>{rule.category}</td><td>{rule.status === "evaluated" ? "Evaluated" : rule.status === "not_applicable" ? "Not applicable" : "Not evaluated"}</td><td>{rule.records_evaluated.toLocaleString()}</td><td>{rule.issue_records === null ? "—" : rule.issue_records.toLocaleString()}</td><td>{rule.detail}<br />Recommended action: {rule.recommendation}</td></tr>)}</tbody></table></div>
      </details>}

      {datasetResult?.dataset_type === "product catalog" && (datasetResult.issue_details?.length ?? 0) > 0 && <details className="panel result-section report-detail" open>
        <summary><span>Record-level product issues</span><small>{datasetResult.issue_details!.length.toLocaleString()} issue rows · {new Set(datasetResult.issue_details!.map(issue => issue.row_number)).size.toLocaleString()} affected records</small></summary>
        <h3>Record-level product issues</h3>
        <p className="import-description">Each entry identifies a source row, product identifier, source field and original value. Source row numbering includes the header row. Missing physical attributes are listed separately from non-positive or non-numeric values.</p>
        <div className="table-scroll"><table className="preview-table"><thead><tr><th>Source row</th><th>Product ID</th><th>Source field</th><th>Original value</th><th>Finding</th><th>Severity</th><th>Recommended action</th></tr></thead><tbody>{datasetResult.issue_details!.slice(0, 100).map((issue, index) => <tr key={index}><td>{issue.row_number}</td><td>{issue.product_id || "—"}</td><td>{issue.field}</td><td>{issue.source_value === "" ? "— (missing)" : issue.source_value}</td><td>{issue.title}</td><td>{issue.severity}</td><td>{issue.recommendation}</td></tr>)}</tbody></table></div>
        {datasetResult.issue_details!.length > 100 && <p className="import-description">Showing the first 100 issue rows here. Download the CSV report for the complete issue list.</p>}
      </details>}

      <div className="panel result-section report-findings">
        <h3>Findings and issues</h3>
        {issues.length === 0 ? <p>No issues were returned by the current analysis.</p> : <div className="table-scroll"><table className="preview-table"><thead><tr><th>Location</th><th>Field / finding</th><th>Severity</th><th>Code</th><th>Details</th></tr></thead><tbody>{issues.slice(0, 100).map((issue, index) => <tr key={index}><td>{issue.location}</td><td>{issue.field}</td><td>{issue.severity}</td><td>{issue.code}</td><td>{issue.message}</td></tr>)}</tbody></table></div>}
        <p className="import-description">The report includes only checks performed by the current analysis path. Unavailable external reference checks are not inferred.</p>
      </div>

      <details className="panel result-section report-detail">
        <summary><span>Source record preview</span><small>Up to 10 sample rows</small></summary>
        <h3>Source record preview</h3>
        <p className="import-description">Showing up to the first 10 records returned by the analysis endpoint. This is a preview, not a full-data export.</p>
        <Table headers={previewHeaders} rows={preview.slice(0, 10)} />
      </details>
      {industryResult && (industryResult.profile_id === "automotive" || industryResult.column_mappings.some((mapping) => mapping.field === "compatibility")) && <p className="import-disclaimer">External vehicle/equipment fitment and compatibility references are not checked unless explicitly provided by active validation rules.</p>}
      {result && <p className="import-disclaimer">The score is a transparent rule-based heuristic, not a statistical accuracy measurement. It reflects only the current product-catalog validation rules.</p>}
    </section>
  );
}
