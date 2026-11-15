# CompatFlow AI-Assisted Column Mapping

## Decision

AI-assisted mapping is a suggestion layer only. It does not own parsing, validation, quality scoring, duplicate detection, relationship matching, or metric calculation.

The deterministic alias mapper remains the first pass. AI may help when headers are unfamiliar, ambiguous, source-qualified, or embedded in structured payloads. Every suggestion requires user confirmation.

## Implemented backend contract

The optional POST /api/v1/catalog/import/suggest-mappings endpoint parses CSV, XLSX, XLS, JSON, and XML input using the shared source adapters and accepts a selected catalog record type. The caller must explicitly set ai_opt_in=true; without consent, no sample data is sent.

The provider adapter is configured through server-side environment variables:

- MAPPING_AI_BASE_URL: HTTPS endpoint only; embedded credentials and URL fragments are rejected.
- MAPPING_AI_API_KEY: server-side provider key; never expose it to the browser.
- MAPPING_AI_MODEL: configured provider model identifier.

The endpoint sends only header names and up to five non-empty sample values per header, each truncated to 160 characters, with a maximum of 200 headers and five sample records. It does not send the complete uploaded file. The user-facing UI explains this before consent. No provider credentials are configured in the current environment, so live provider behavior has not been verified; the deterministic/manual fallback remains the only available path until configuration and a live test are completed.

The provider may return only fields allowlisted for the selected record type. The adapter verifies that source headers and evidence values occur in the submitted sample, validates confidence is between zero and one, and marks suggestions as requiring confirmation. Confidence is model-reported and uncalibrated; it is not a probability or validated quality metric.

## User-visible workflow

1. Parse the source deterministically and identify headers, source locations, record structure, and parser errors.
2. Apply conservative exact aliases.
3. If the user explicitly opts in, send the bounded header/sample evidence to the configured HTTPS provider.
4. Display suggestions with source header, candidate field, model-reported confidence, rationale, and evidence.
5. The user reviews and applies selected suggestions to the mapping form.
6. Run deterministic validation with the confirmed mapping.
7. Never let a suggestion trigger persistence automatically.

## AI boundary

AI may rank possible mappings for unfamiliar headers, suggest source-qualified field interpretations when supplied evidence supports them, explain why similar fields should remain separate, or return no suggestion when evidence is weak.

AI must not generate validation metrics, decide row validity, suppress deterministic errors, silently rewrite source values, auto-apply ambiguous mappings, invent product/supplier/variant/identifier relationships, or infer a legal manufacturer from a brand, vendor, or seller.

Completeness, duplicate, range, format, referential, profile, and row-level metrics must be computed from actual parsed records by deterministic code.

## Evaluation data and limitations

A reviewed benchmark seed of 72 examples exists at docs/column-mapping-benchmark-seed.json. It covers positive aliases, negative mappings, ambiguous identifiers, source-specific fields, and structural cases. It is a discovery/evaluation seed, not a training corpus and not a claim of model accuracy. A 100-dataset audit informs the mapping vocabulary, but neither the audit nor the 72-example seed is sufficient justification for training a model.

Do not train on unconfirmed AI predictions. Split evaluation by source repository and source family so near-duplicate exports cannot leak across train/test. Tag synthetic/adversarial examples and report their results separately.

Before any model evaluation, define a held-out source-family split and measure top-1 accuracy, top-3 recall, precision, false-positive rate, coverage by confidence band, calibration, results by domain and record type, and false mappings for high-risk pairs such as brand/manufacturer, model/MPN, product_id/SKU, supplier_sku/SKU, barcode/SKU, and product/variant/inventory.

The first release keeps all AI suggestions user-confirmed regardless of score.

## Remaining work

- Configure an approved provider and verify the live request/response path.
- Define provider retention, logging, deletion, cost, and rate limits.
- Add timeout/retry/request-budget tests and provider outage monitoring.
- Expand manually reviewed labels across independent source families and maintain a held-out set.
- Add organization-scoped confirmed mapping templates only after an explicit save workflow exists.
- Add connector-payload mapping consent and tests; current AI endpoint accepts uploaded files only.

No model has been trained. Do not report live AI results while provider credentials are absent.
