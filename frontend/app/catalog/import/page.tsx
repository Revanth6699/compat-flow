"use client";

import Link from "next/link";
import { useState } from "react";

type PreviewRow = {
  sku: string;
  name: string;
  manufacturer: string;
  part_number: string;
  category: string;
  compatibility?: string | null;
  replacement_sku?: string | null;
};

type PreviewResponse = {
  filename: string;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  errors: string[];
  row_errors?: {
    row_number: number;
    field: string | null;
    error_code: string;
    message: string;
  }[];
  preview: PreviewRow[];
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8001";

export default function CatalogImportPage() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<PreviewResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function handleFileChange(selectedFile: File | null) {
    setFile(selectedFile);
    setResult(null);
    setError("");

    if (!selectedFile) return;

    if (!selectedFile.name.toLowerCase().endsWith(".csv")) {
      setFile(null);
      setError("Only CSV files are supported.");
      return;
    }

    if (selectedFile.size > 5 * 1024 * 1024) {
      setFile(null);
      setError("The file exceeds the 5 MB limit.");
    }
  }

  async function handleValidate() {
    if (!file || loading) return;

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${API_BASE}/api/v1/catalog/import/preview`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "The backend could not validate this CSV."
        );
      }

      setResult(data as PreviewResponse);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Something went wrong while validating the file."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <>

      <main id="main" className="page">
        <div className="container">
          <div className="import-heading">
            <div className="eyebrow">Public product demo</div>
            <h1>Validate a supplier catalog CSV</h1>
            <p>
              Check required columns, row values and duplicate SKUs within
              your uploaded file before considering a catalog import workflow.
            </p>
          </div>

          <section className="panel import-panel">
            <h2>Try the CSV validator</h2>
            <p className="import-description">
              CSV only · Maximum 5 MB · Maximum 10,000 data rows.
            </p>
            <p className="import-description">
              Your file is validated in memory. This public demo does not save
              uploaded files, change a catalog or run persistent imports.
            </p>

            <p className="column-hint">
              Required columns: sku, name, manufacturer, part_number, category
            </p>

            <p className="column-hint">
              <a href="/sample_supplier_catalog.csv" download>
                Download the sample supplier catalog
              </a>
            </p>

            <label className="file-picker" htmlFor="catalog-file">
              <span className="file-picker-icon" aria-hidden="true">↥</span>
              <strong>{file ? file.name : "Choose a CSV file"}</strong>
              <span>
                {file
                  ? `${(file.size / 1024).toFixed(1)} KB`
                  : "Select a file from your computer"}
              </span>
            </label>

            <input
              id="catalog-file"
              className="visually-hidden"
              type="file"
              accept=".csv,text/csv"
              onChange={(event) =>
                handleFileChange(event.target.files?.[0] ?? null)
              }
            />

            <div className="import-actions">
              <button
                className="button"
                type="button"
                onClick={handleValidate}
                disabled={!file || loading}
              >
                {loading ? "Validating..." : "Validate CSV"}
              </button>
              <button
                className="button button-secondary"
                type="button"
                onClick={() => {
                  setFile(null);
                  setResult(null);
                  setError("");
                  const input = document.getElementById(
                    "catalog-file"
                  ) as HTMLInputElement | null;
                  if (input) input.value = "";
                }}
                disabled={loading}
              >
                Clear
              </button>
            </div>

            {error && (
              <div className="import-error" role="alert">{error}</div>
            )}
          </section>

          {result && (
            <section className="import-results" aria-live="polite">
              <div className="results-heading">
                <div>
                  <div className="eyebrow">Validation complete</div>
                  <h2>Validation results</h2>
                  <p>{result.filename}</p>
                </div>
                <span
                  className={
                    result.invalid_rows === 0
                      ? "result-status success"
                      : "result-status warning"
                  }
                >
                  {result.invalid_rows === 0 ? "All rows valid" : "Review required"}
                </span>
              </div>

              <div className="result-stats">
                <div className="panel stat-card">
                  <span>Total rows</span>
                  <strong>{result.total_rows}</strong>
                </div>
                <div className="panel stat-card">
                  <span>Valid rows</span>
                  <strong>{result.valid_rows}</strong>
                </div>
                <div className="panel stat-card">
                  <span>Invalid rows</span>
                  <strong>{result.invalid_rows}</strong>
                </div>
              </div>

              {((result.row_errors?.length ?? 0) > 0 || result.errors.length > 0) && (
                <div className="panel result-section">
                  <h3>Validation errors</h3>
                  <p className="import-description">Showing up to 50 reported errors.</p>
                  <ul className="error-list">
                    {result.row_errors && result.row_errors.length > 0
                      ? result.row_errors.map((item, index) => (
                          <li key={`${item.row_number}-${item.field}-${item.error_code}-${index}`}>
                            <strong>Row {item.row_number}</strong>
                            {" · "}
                            <code>{item.field || "General"}</code>
                            {": "}
                            {item.message}
                          </li>
                        ))
                      : result.errors.map((item, index) => (
                          <li key={`${index}-${item}`}>{item}</li>
                        ))}
                  </ul>
                </div>
              )}

              <div className="panel result-section">
                <h3>Valid row preview</h3>
                <p className="import-description">
                  Showing up to the first 10 valid records. Duplicate SKU
                  checks apply only within this uploaded file.
                </p>

                {result.preview.length === 0 ? (
                  <p>No valid records to preview.</p>
                ) : (
                  <div className="table-scroll">
                    <table className="preview-table">
                      <thead>
                        <tr>
                          <th>SKU</th>
                          <th>Product</th>
                          <th>Manufacturer</th>
                          <th>Part number</th>
                          <th>Category</th>
                          <th>Compatibility</th>
                          <th>Replacement SKU</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.preview.map((row, index) => (
                          <tr key={`${row.sku}-${index}`}>
                            <td>{row.sku}</td>
                            <td>{row.name}</td>
                            <td>{row.manufacturer}</td>
                            <td>{row.part_number}</td>
                            <td>{row.category}</td>
                            <td>{row.compatibility || "—"}</td>
                            <td>{row.replacement_sku || "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </section>
          )}

          <p className="import-disclaimer">
            Demonstration only. Do not upload confidential supplier files,
            personal information or production catalog data.
          </p>
        </div>
      </main>

      <footer className="site-footer">
        <div className="container footer">
          <span>CompatFlow · Early-stage product demo</span>
          <div className="footer-links">
            <Link href="/privacy">Privacy Policy</Link>
            <Link href="/terms">Terms &amp; Conditions</Link>
            <Link href="/">Home</Link>
          </div>
        </div>
      </footer>
    </>
  );
}
