# AI-Assisted Column Mapping

## 1. Design decision

AI-assisted mapping is a suggestion layer only. It does not own parsing, validation, quality scoring, duplicate detection, relationship matching, or metric calculation.

The deterministic alias mapper runs first. AI may assist when headers are unfamiliar, ambiguous, source-qualified, or embedded in structured payloads. Every suggestion requires user confirmation.

## 2. Backend contract

The optional endpoint is:

`POST /api/v1/catalog/import/suggest-mappings`

It supports CSV, XLSX, XLS, JSON, and XML through the shared source adapters and accepts a selected catalog record type. The caller must explicitly set `ai_opt_in=true`. Without opt-in, sample data is not sent to the provider.

### Provider configuration

| Variable | Purpose |
|---|---|
| `MAPPING_AI_BASE_URL` | HTTPS provider endpoint; embedded credentials and URL fragments are rejected |
| `MAPPING_AI_API_KEY` | Server-side provider key; never expose it to the browser |
| `MAPPING_AI_MODEL` | Configured provider model identifier |

The endpoint sends header names and up to five non-empty sample values per header. Each value is truncated to 160 characters; the request is limited to 200 headers and five sample records. The complete uploaded file is not sent.

No provider credentials are configured in the reviewed environment. Live provider behavior has therefore not been verified. Manual and deterministic mapping remain the fallback.

## 3. Suggestion validation

The provider may return only fields allowlisted for the selected record type.

The adapter verifies that:
- Referenced source headers and evidence values occur in the submitted sample.
- Confidence is between zero and one.
- Each suggestion is marked as requiring confirmation.

Confidence is model-reported and uncalibrated. It is not a probability or a validated quality metric.

## 4. User workflow

1. Parse the source deterministically.
2. Identify headers, source locations, record structure, and parser errors.
3. Apply conservative exact aliases.
4. Request AI suggestions only after explicit user opt-in.
5. Display each suggestion with its source header, candidate field, confidence, rationale, and evidence.
6. Require the user to review and apply selected suggestions.
7. Run deterministic validation using the confirmed mapping.
8. Do not allow a suggestion to trigger persistence automatically.

## 5. AI boundaries

AI may:
- Rank candidate mappings for unfamiliar headers.
- Suggest source-qualified interpretations when submitted evidence supports them.
- Explain why similar fields should remain separate.
- Return no suggestion when evidence is insufficient.

AI must not:
- Generate validation metrics or decide row validity.
- Suppress deterministic errors.
- Silently rewrite source values.
- Auto-apply ambiguous mappings.
- Invent product, supplier, variant, or identifier relationships.
- Infer a legal manufacturer from a brand, vendor, or seller.

Completeness, duplicate, range, format, referential, profile, and row-level metrics must be computed from parsed records by deterministic code.

## 6. Evaluation data and limitations

A reviewed benchmark seed of 72 examples exists at [column-mapping-benchmark-seed.json](column-mapping-benchmark-seed.json). It is an evaluation seed, not a training corpus and not evidence of model accuracy.

The 100-dataset audit informs the mapping vocabulary. Neither the audit nor the benchmark seed is sufficient justification for model training.

For evaluation:
- Split by source repository and source family to prevent near-duplicate leakage.
- Keep synthetic and adversarial examples separately identified.
- Do not train on unconfirmed AI predictions.
- Measure top-1 accuracy, top-3 recall, precision, false-positive rate, coverage by confidence band, calibration, and results by domain and record type.
- Review false mappings for high-risk pairs, including brand/manufacturer, model/MPN, product_id/SKU, supplier_sku/SKU, barcode/SKU, and product/variant/inventory.

The first release keeps all AI suggestions user-confirmed regardless of score.

## 7. Remaining work

- Configure an approved provider and verify the live request/response path.
- Review provider retention, logging, deletion, cost, and rate limits.
- Add timeout, retry, request-budget, and provider-outage tests.
- Expand manually reviewed labels across independent source families.
- Maintain a held-out evaluation set.
- Add organization-scoped confirmed mapping templates only after an explicit save workflow exists.
- Add connector-payload mapping consent and tests; the current AI endpoint accepts uploaded files only.

No model has been trained. Do not report live AI results while provider credentials are absent.
