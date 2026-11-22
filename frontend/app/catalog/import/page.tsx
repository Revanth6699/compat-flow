"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/components/auth-provider";
import { apiRequest } from "@/lib/auth-client";
import UnifiedImportReport from "@/components/unified-import-report";
import { BrandedLoading } from "@/components/branded-loading";


type DatasetProfile = {
  filename: string; format: string; dataset_type: string; total_records: number; total_columns: number;
  total_cells: number; populated_cells: number; missing_cells: number; completeness_pct: number;
  complete_records: number | null; incomplete_records: number | null; complete_records_pct: number | null;
  duplicate_rows: number; duplicate_rate_pct: number; is_product_catalog: boolean; persisted: false;
  columns: { name: string; populated: number; missing: number; completeness_pct: number; distinct_values: number; inferred_type: string; minimum: number | string | null; maximum: number | string | null; average: number | null; top_values: { value: string; count: number; pct: number }[] }[];
  categorical_distributions: { name: string; values: { value: string; count: number; pct: number }[] }[];
  date_columns: string[]; numeric_columns: string[];
  relationship_checks: { name: string; from_column: string; to_column: string; matched_records: number; average_days: number | null; minimum_days: number | null; maximum_days: number | null; negative_duration_records: number }[];
  domain_checks?: { code: string; title: string; issue_records: number; severity: string; detail: string; recommendation: string }[];
  findings: { severity: string; title: string; detail: string }[];
  preview: Record<string, unknown>[];
};
type IndustryResult = {
  filename: string; profile_id: string | null; profile_detection: { profile_id: string | null; confidence: number; scores: Record<string, number>; needs_confirmation: boolean };
  requires_profile_confirmation: boolean; total_rows: number; valid_rows: number; invalid_rows: number;
  validation_pass_rate: number; column_mappings: { field: string; source_header: string; confidence: number }[];
  unmapped_headers: string[]; field_metrics: { field: string; applicable: boolean; populated: number; missing: number; completeness_pct: number }[];
  issues: { row_number: number; field: string | null; error_code: string; message: string; severity: string }[];
  preview: Record<string, unknown>[]; metrics: { mapping_coverage_pct: number; validation_pass_rate_pct: number; issue_count: number; critical_issue_count: number; warning_issue_count: number };
  persisted: false; validation_scope: string;
};
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
  const { user, loading: authLoading } = useAuth();
  const [accessResult, setAccessResult] = useState<{ email: string; type: "demo" | "subscription" | "none"; maxUploadBytes: number | null } | null>(null);
  const email = user?.email?.toLowerCase() || "";
  const accessType = !email ? "none" : accessResult?.email === email ? accessResult.type : "checking";
  const demoApproved = accessType === "demo";
  useEffect(() => {
    if (!email) return;
    let active = true;
    apiRequest<{ allowed: boolean; access_type: "demo" | "subscription" | "none"; max_upload_bytes?: number | null }>("/api/v1/demo-access")
      .then((data) => { if (active) setAccessResult({ email, type: data.allowed ? data.access_type : "none", maxUploadBytes: data.max_upload_bytes ?? null }); })
      .catch(() => { if (active) setAccessResult({ email, type: "none", maxUploadBytes: null }); });
    return () => { active = false; };
  }, [email]);
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<PreviewResponse | null>(null);
  const [datasetResult, setDatasetResult] = useState<DatasetProfile | null>(null);
  const [multiResult, setMultiResult] = useState<MultiResult | null>(null);
  const [industryResult, setIndustryResult] = useState<IndustryResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [manualMapping, setManualMapping] = useState<Record<string, string>>({});
  const canonicalFields = ["sku", "name", "manufacturer", "part_number", "category", "compatibility", "replacement_sku"];

  function handleFileChange(selectedFile: File | null) {
    setFile(selectedFile); setResult(null); setDatasetResult(null); setMultiResult(null); setIndustryResult(null); setManualMapping({}); setError("");
    if (!selectedFile) return;
    const extension = selectedFile.name.split(".").pop()?.toLowerCase();
    const allowed = demoApproved ? ["csv", "xlsx", "xls"] : ["csv", "xlsx", "xls", "json", "xml"];
    if (!allowed.includes(extension ?? "")) {
      setFile(null);
      setError(demoApproved ? "Approved demo supports CSV, XLSX and XLS only." : "Supported formats: CSV, XLSX, XLS, JSON and XML. Your plan determines which formats you can process.");
      return;
    }
    const maxUploadBytes = accessResult?.email === email ? accessResult.maxUploadBytes : null;
    if (maxUploadBytes !== null && selectedFile.size > maxUploadBytes) {
      const limitMb = maxUploadBytes / (1024 * 1024);
      setFile(null); setError(`The file exceeds the ${limitMb.toLocaleString()} MB limit for this access level.`);
    }
  }

  async function handleValidate() {
    if (!file || loading || !user) return;
    setLoading(true); setError(""); setResult(null); setDatasetResult(null); setMultiResult(null); setIndustryResult(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const extension = file.name.split(".").pop()?.toLowerCase();

      if (demoApproved) {
        const data = await apiRequest<IndustryResult>("/api/v1/catalog/import/preview-industry", { method: "POST", body: formData });
        if (!data.profile_id) {
          const profileForm = new FormData();
          profileForm.append("file", file);
          const profile = await apiRequest<Partial<DatasetProfile>>("/api/v1/catalog/import/profile", { method: "POST", body: profileForm });
          const columns = profile.columns ?? [];
          const totalRecords = profile.total_records ?? 0;
          const duplicateRows = profile.duplicate_rows ?? 0;
          const missingCells = profile.missing_cells ?? 0;
          const normalizedHeaders = columns.map((column) => column.name.toLowerCase().replace(/[^a-z0-9]+/g, "_"));
          const datasetType = profile.dataset_type ?? (normalizedHeaders.some((header) => ["order_id", "order_status", "order_purchase_timestamp", "order_item_id"].includes(header)) ? "orders / transactions" : profile.is_product_catalog ? "product catalog" : "general dataset");
          const findings = profile.findings ?? [
            ...(missingCells > 0 ? [{ severity: "warning", title: "Missing values detected", detail: missingCells.toLocaleString() + " cells are empty." }] : []),
            ...(duplicateRows > 0 ? [{ severity: "warning", title: "Duplicate records detected", detail: duplicateRows.toLocaleString() + " exact duplicate rows were found." }] : []),
          ];
          setDatasetResult({
            ...profile, filename: profile.filename ?? file.name, format: profile.format ?? extension ?? "unknown", dataset_type: datasetType,
            total_records: totalRecords, total_columns: profile.total_columns ?? columns.length, total_cells: profile.total_cells ?? totalRecords * columns.length,
            populated_cells: profile.populated_cells ?? Math.max(0, totalRecords * columns.length - missingCells), missing_cells: missingCells, completeness_pct: profile.completeness_pct ?? 0,
            complete_records: profile.complete_records ?? null, incomplete_records: profile.incomplete_records ?? null, complete_records_pct: profile.complete_records_pct ?? null,
            duplicate_rows: duplicateRows, duplicate_rate_pct: profile.duplicate_rate_pct ?? (totalRecords ? duplicateRows / totalRecords * 100 : 0),
            columns, categorical_distributions: profile.categorical_distributions ?? [], date_columns: profile.date_columns ?? [], numeric_columns: profile.numeric_columns ?? [],
            relationship_checks: profile.relationship_checks ?? [], findings, preview: profile.preview ?? [], is_product_catalog: profile.is_product_catalog ?? false, persisted: false, quality_score: null,
          } as DatasetProfile);
          return;
        }
        setIndustryResult(data);
        return;
      }

      const data = await apiRequest<IndustryResult>("/api/v1/catalog/import/validate-industry", { method: "POST", body: formData });
      if (!data.profile_id) {
        const profileForm = new FormData();
        profileForm.append("file", file);
        const profile = await apiRequest<Partial<DatasetProfile>>("/api/v1/catalog/import/profile", { method: "POST", body: profileForm });
        const columns = profile.columns ?? [];
        const totalRecords = profile.total_records ?? 0;
        const duplicateRows = profile.duplicate_rows ?? 0;
        const missingCells = profile.missing_cells ?? 0;
        const normalizedHeaders = columns.map((column) => column.name.toLowerCase().replace(/[^a-z0-9]+/g, "_"));
        const datasetType = profile.dataset_type ?? (normalizedHeaders.some((header) => ["order_id", "order_status", "order_purchase_timestamp", "order_item_id"].includes(header)) ? "orders / transactions" : profile.is_product_catalog ? "product catalog" : "general dataset");
        const findings = profile.findings ?? [
          ...(missingCells > 0 ? [{ severity: "warning", title: "Missing values detected", detail: missingCells.toLocaleString() + " cells are empty." }] : []),
          ...(duplicateRows > 0 ? [{ severity: "warning", title: "Duplicate records detected", detail: duplicateRows.toLocaleString() + " exact duplicate rows were found." }] : []),
        ];
        setDatasetResult({
          ...profile, filename: profile.filename ?? file.name, format: profile.format ?? extension ?? "unknown", dataset_type: datasetType,
          total_records: totalRecords, total_columns: profile.total_columns ?? columns.length, total_cells: profile.total_cells ?? totalRecords * columns.length,
          populated_cells: profile.populated_cells ?? Math.max(0, totalRecords * columns.length - missingCells), missing_cells: missingCells, completeness_pct: profile.completeness_pct ?? 0,
          complete_records: profile.complete_records ?? null, incomplete_records: profile.incomplete_records ?? null, complete_records_pct: profile.complete_records_pct ?? null,
          duplicate_rows: duplicateRows, duplicate_rate_pct: profile.duplicate_rate_pct ?? (totalRecords ? duplicateRows / totalRecords * 100 : 0),
          columns, categorical_distributions: profile.categorical_distributions ?? [], date_columns: profile.date_columns ?? [], numeric_columns: profile.numeric_columns ?? [],
          relationship_checks: profile.relationship_checks ?? [], findings, preview: profile.preview ?? [], is_product_catalog: profile.is_product_catalog ?? false, persisted: false, quality_score: null,
        } as DatasetProfile);
        return;
      }
      setIndustryResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong while validating the file.");
    } finally { setLoading(false); }
  }

  function saveBlob(filename: string, content: string, mimeType: string) {
    const url = URL.createObjectURL(new Blob([content], { type: mimeType }));
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = filename; anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function downloadReport() {
    if (datasetResult) {
      const rows: unknown[][] = [
        ["CompatFlow Dataset Profile", datasetResult.filename],
        ["Dataset type", datasetResult.dataset_type],
        ["Records", datasetResult.total_records],
        ["Columns", datasetResult.total_columns],
        ["Completeness (%)", datasetResult.completeness_pct],
        ["Complete records", datasetResult.complete_records],
        ["Incomplete records", datasetResult.incomplete_records],
        ["Duplicate rows", datasetResult.duplicate_rows],
        ["Duplicate rate (%)", datasetResult.duplicate_rate_pct],
        [],
        ["Column", "Inferred type", "Populated", "Missing", "Completeness (%)", "Distinct values", "Minimum", "Maximum", "Average"],
        ...datasetResult.columns.map(c => [c.name,c.inferred_type,c.populated,c.missing,c.completeness_pct,c.distinct_values,c.minimum ?? "",c.maximum ?? "",c.average ?? ""]),
        [],
        ["Categorical column", "Value", "Count", "Share (%)"],
        ...datasetResult.categorical_distributions.flatMap(c => c.values.map(v => [c.name,v.value,v.count,v.pct])),
        [],
        ["Finding severity", "Finding", "Details"],
        ...datasetResult.findings.map(f => [f.severity,f.title,f.detail]),
        [],
        ["Dataset-specific check", "Code", "Severity", "Records flagged", "Finding", "Recommendation"],
        ...(datasetResult.domain_checks ?? []).map(check => [check.title,check.code,check.severity,check.issue_records,check.detail,check.recommendation]),
        [],
        ["Relationship check", "From", "To", "Matched records", "Average days", "Minimum days", "Maximum days", "Negative durations"],
        ...datasetResult.relationship_checks.map(r => [r.name,r.from_column,r.to_column,r.matched_records,r.average_days ?? "",r.minimum_days ?? "",r.maximum_days ?? "",r.negative_duration_records]),
      ];
      const csv = rows.map(row => row.map(value => {
        let cell = String(value ?? "");
        if (/^[=+@-]/.test(cell)) cell = "'" + cell;
        return '"' + cell.replace(/"/g, '""') + '"';
      }).join(",")).join("\n");
      saveBlob("compatflow-dataset-profile.csv", csv, "text/csv;charset=utf-8");
      return;
    }
    if (industryResult) {
      const rows: unknown[][] = [
        ["CompatFlow Industry Validation Report", industryResult.filename],
        ["Profile", industryResult.profile_id ?? "Not confirmed"],
        ["Total records", industryResult.total_rows], ["Valid records", industryResult.valid_rows],
        ["Invalid records", industryResult.invalid_rows], ["Pass rate (%)", industryResult.validation_pass_rate],
        [], ["Field", "Source column", "Confidence"],
        ...industryResult.column_mappings.map((item) => [item.field, item.source_header, item.confidence]),
        [], ["Field", "Populated", "Missing", "Completeness (%)"],
        ...industryResult.field_metrics.map((item) => [item.field, item.populated, item.missing, item.completeness_pct]),
        [], ["Row", "Field", "Severity", "Code", "Issue"],
        ...industryResult.issues.map((item) => [item.row_number, item.field ?? "Record", item.severity, item.error_code, item.message]),
      ];
      const csv = rows.map((row) => row.map((value) => '"' + String(value ?? "").replace(/"/g, '""') + '"').join(",")).join("\n");
      saveBlob("compatflow-industry-report.csv", csv, "text/csv;charset=utf-8");
      return;
    }
    if (multiResult) {
      const rows: unknown[][] = [
        ["CompatFlow Multi-format Validation Report", multiResult.filename],
        ["Record type", multiResult.record_type], ["Total records", multiResult.total_records],
        ["Valid records", multiResult.valid_records], ["Invalid records", multiResult.invalid_records],
        [], ["Field", "Source column", "Confidence"],
        ...multiResult.mappings.map((item) => [item.field, item.source_header, item.confidence]),
        [], ["Field", "Populated", "Missing", "Completeness (%)"],
        ...multiResult.field_completeness.map((item) => [item.field, item.populated, item.missing, item.completeness_pct]),
        [], ["Source location", "Field", "Code", "Issue"],
        ...multiResult.errors.map((item) => [item.source_location, item.field ?? "Record", item.error_code, item.message]),
      ];
      const csv = rows.map((row) => row.map((value) => '"' + String(value ?? "").replace(/"/g, '""') + '"').join(",")).join("\n");
      saveBlob("compatflow-multiformat-report.csv", csv, "text/csv;charset=utf-8");
      return;
    }
    if (!result) return;
    const report = [
      ["CompatFlow Catalog Validation Report", result.filename],
      ["Total records", result.total_rows], ["Valid records", result.valid_rows],
      ["Invalid records", result.invalid_rows], ["Validation pass rate (%)", result.validation_pass_rate],
      ["Data quality score (%)", result.data_quality_score], ["Total issues", result.total_issues],
      ["Critical issues", result.critical_issues], ["Warnings", result.warning_issues],
      ["Records with issues", result.records_with_issues], ["Duplicate SKU count", result.duplicate_sku_count],
      ["Duplicate SKU rate (%)", result.duplicate_rate], ["Issue density", result.issue_density],
      ["Critical record rate (%)", result.critical_record_rate], [],
      ["Canonical field", "Detected source header", "Mapping confidence"],
      ...result.column_mappings.map(m => [m.field,m.source_header,m.confidence]), [],
      ["Field", "Populated", "Missing", "Completeness (%)"],
      ...result.field_metrics.map(m => [m.field,m.populated,m.missing,m.completeness_pct]), [],
      ["Row", "Field", "Severity", "Category", "Issue", "Recommended action"],
      ...result.row_errors.map(i => [i.row_number,i.field ?? "General",i.severity,i.category,i.message,i.recommendation]),
    ];
    const csv = report.map(row => row.map(v => '"' + String(v ?? "").replace(/"/g, '""') + '"').join(",")).join("\n");
    saveBlob("compatflow-validation-report.csv", csv, "text/csv;charset=utf-8");
  }

  function downloadProfileJson() {
    const report = datasetResult ?? industryResult ?? multiResult ?? result;
    if (!report) return;
    saveBlob("compatflow-report.json", JSON.stringify(report, null, 2), "application/json;charset=utf-8");
  }

  function printReport() {
    window.print();
  }

  if (authLoading) return <main id="main" className="page"><div className="container"><BrandedLoading label="Checking your account" detail="Securely verifying your sign-in session." /></div></main>;
  if (!user) return (
    <main id="main" className="page"><div className="container">
      <section className="panel import-panel">
        <div className="eyebrow">RESTRICTED WORKSPACE</div>
        <h1>Demo access is not public</h1>
        <p>Submit a demo request. If approved, create an account or sign in with the same email address to use the upload workflow. Subscribed customers can sign in to access their plan features.</p>
        <div className="import-actions"><a className="button" href="/contact?intent=demo">Request demo access</a><a className="button button-secondary" href="/sign-in">Sign in</a></div>
      </section>
    </div></main>
  );
  if (accessType === "checking") return <main id="main" className="page"><div className="container"><BrandedLoading label="Checking upload access" detail="Confirming your demo approval or active subscription." /></div></main>;
  if (accessType === "none") return (
    <main id="main" className="page"><div className="container">
      <section className="panel import-panel"><div className="eyebrow">UPLOAD ACCESS REQUIRED</div><h1>Your account does not have upload access</h1>
        <p>Demo uploads are available only after an operator approves your request. Subscribed organizations can use the features included in their active plan.</p>
        <div className="import-actions"><a className="button" href="/contact?intent=demo">Request demo access</a><a className="button button-secondary" href="/pricing">View plans</a></div>
      </section>
    </div></main>
  );
  return (
    <main id="main" className="page">
      <div className="container">
        <div className="import-heading">
          <div className="eyebrow">{demoApproved ? "APPROVED DEMO WORKSPACE" : "CUSTOMER CATALOG WORKSPACE"}</div>
          <h1>{demoApproved ? "Explore your approved demo" : "Validate your catalog data"}</h1>
          <p>{demoApproved ? "Use the limited, stateless demo workflow. Access is checked by the backend on every upload." : "Validate product data using the file formats and limits available to your organization. Review field completeness, duplicates and actionable issues."}</p>
          {user && <p className="import-description"><a href="/catalog/sources">Connect a REST API, SFTP server or SQL Server source →</a></p>}
        </div>

        <section className="panel import-panel">
          <h2>Multi-industry catalog validation</h2>
          <p className="import-description">{demoApproved ? "Approved demo: CSV, XLS and XLSX · Maximum 5 MB per file." : `Your plan: ${((accessResult?.maxUploadBytes ?? 0) / (1024 * 1024)).toLocaleString()} MB per file.`}</p>
          <div className="import-description">
            {demoApproved ? "Approved demo access is stateless and does not save uploaded files." : "CompatFlow detects common supplier product fields and applies the validation features available on your plan."}
          </div>
          <p className="import-description">Files are validated in memory. This preview does not save files or commit records to your organization catalog.</p>
          {demoApproved && <p className="column-hint">Non-product datasets are profiled using their actual columns; CompatFlow will not label them as invalid product catalogs or invent a product quality score.</p>}
          {demoApproved && <p className="column-hint"><a href="/sample_supplier_catalog.csv" download>Download the sample supplier catalog</a></p>}
          <p className="import-description">CompatFlow identifies the most likely industry from the file&apos;s column evidence. If the file is not clearly a product catalog, it provides a structural dataset profile instead of asking you to choose an industry.</p>
          <label className="file-picker" htmlFor="catalog-file">
            <span className="file-picker-icon" aria-hidden="true">↥</span>
            <strong>{file ? file.name : "Choose a catalog file"}</strong>
            <span>{file ? `${(file.size / 1024).toFixed(1)} KB` : "Select a file from your computer"}</span>
          </label>
          <input id="catalog-file" className="visually-hidden" type="file" accept={demoApproved ? ".csv,.xlsx,.xls,text/csv" : ".csv,.xlsx,.xls,.json,.xml,text/csv,application/json,application/xml"}
            onChange={(event) => handleFileChange(event.target.files?.[0] ?? null)} />
          <div className="import-actions">
            <button className="button" type="button" onClick={handleValidate} disabled={!file || loading}>
              {loading ? "Validating..." : "Validate file"}
            </button>
            <button className="button button-secondary" type="button" disabled={loading} onClick={() => {
              setFile(null); setResult(null); setDatasetResult(null); setMultiResult(null); setIndustryResult(null); setError("");
              const input = document.getElementById("catalog-file") as HTMLInputElement | null;
              if (input) input.value = "";
            }}>Clear</button>
          </div>
          {error && <div className="import-error" role="alert">{error}</div>}
        </section>

        <UnifiedImportReport datasetResult={datasetResult} industryResult={industryResult} multiResult={multiResult} result={result} onDownloadCsv={downloadReport} onDownloadJson={downloadProfileJson} onPrint={printReport} />
        {accessType !== "subscription" && <p className="import-disclaimer">Demonstration only. Do not upload confidential supplier files, personal information or production catalog data.</p>}
      </div>
    </main>
  );
}
