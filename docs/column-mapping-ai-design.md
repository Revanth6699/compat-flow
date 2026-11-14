# CompatFlow AI-Assisted Column Mapping Design

## Decision

Add AI-assisted mapping as a suggestion layer. Do not let an AI model own parsing, validation, quality scoring, duplicate detection, or metric calculation.

The existing deterministic alias mapper remains the first pass. AI is used only when headers are unknown, ambiguous, source-qualified, or embedded inside structured cells such as JSON.

## User-visible workflow

1. Parse the file deterministically and identify headers, delimiter, row count, and structural errors.
2. Apply exact, reviewed aliases.
3. For unmapped or ambiguous columns, prepare a compact evidence package:
   - Original and normalized header.
   - Selected profile and source type when known.
   - A bounded sample of non-empty values.
   - Basic value shape statistics (null rate, distinct count, length range, numeric/date/URL/JSON patterns).
   - Related headers from the same file.
4. Ask the mapping assistant for up to three canonical-field candidates, with rationale and evidence.
5. Show the suggestions in the mapping UI. The user confirms, rejects, or manually selects a mapping.
6. Persist the user's confirmed mapping as a reusable organization/source template only after explicit save.
7. Run the ordinary deterministic parser and validator against the confirmed mapping.

## Allowed output contract

The assistant may return only:
- source_header
- candidate_canonical_field from the current profile's allowed canonical fields
- confidence_band (high, medium, low) calibrated against held-out reviewed examples
- rationale
- evidence (specific header/value observations)
- risk_flags
- requires_confirmation (always true in the first release)

It must not create canonical fields, invent missing values, infer a manufacturer from a brand, treat a product ID as a SKU merely because its values look SKU-like, or treat model numbers as MPNs without evidence.

## AI boundary

AI may:
- Rank possible mappings for unfamiliar headers.
- Recognize source-qualified labels such as Shopify's Google Shopping MPN field.
- Suggest extraction paths for JSON-valued cells (for example attributes.Manufacturer Number).
- Explain why two similar fields should remain separate.

AI must not:
- Generate, estimate, or predict validation metrics.
- Decide whether a row is valid.
- Suppress deterministic errors.
- Silently rewrite source values.
- Auto-apply ambiguous mappings.
- Infer a product's legal manufacturer from its brand, vendor, or seller.

All completeness, duplicate, range, format, referential, profile, and row-level metrics must be computed from actual parsed records by deterministic code.

## Evaluation data

The 50 inspected files are a discovery corpus, not a trustworthy training set. Some are synthetic/demo fixtures, some contain placeholders, some are incomplete, and some represent inventory or variant records rather than product masters.

For every reviewed mapping example, store:
- Source file/repository and source-family identifier.
- Original header and normalized header.
- Canonical field label, or unmapped / ambiguous.
- Whether the label was verified from a source contract or manually reviewed.
- A small, non-sensitive sample-value profile.
- Domain/profile and record type (product master, variant, inventory, supplier offer, etc.).

Do not train on unconfirmed AI predictions. Split evaluation by source repository and source family so near-duplicate exports cannot leak across train/test. Keep synthetic/demo sources tagged and report their results separately.

## Evaluation gates

Measure:
- Top-1 accuracy and top-3 recall on reviewed mappings.
- Precision and false-positive rate for automatic mappings.
- Coverage at each confidence band.
- Calibration (Brier score or expected calibration error).
- Results by domain and record type.
- False mappings for high-risk pairs: brand/manufacturer, model/MPN, product_id/SKU, supplier_sku/SKU, barcode/SKU, product/variant/inventory.

A high overall accuracy is not sufficient if the model makes a small number of dangerous identifier substitutions. The first release keeps all AI suggestions user-confirmed regardless of score.

## Provider and privacy requirements

No external AI provider is wired into CompatFlow yet. Before connecting one:
- Choose the provider/model and define its cost and rate limits.
- Add server-side credentials through deployment environment variables; never expose keys in the browser.
- Send only the minimum sampled evidence required, not the entire uploaded file.
- Define retention, logging, and deletion behavior.
- Add timeouts, retries, request budgets, and a deterministic no-AI fallback.
- Make AI suggestions an opt-in capability with a clear explanation of what sample data is sent.

## Rollout sequence

1. Finish the 100-file discovery audit and lock record types/profile boundaries.
2. Build a reviewed mapping benchmark from source contracts and manually verified labels.
3. Benchmark exact aliases and deterministic contextual rules as the baseline.
4. Evaluate a zero-shot LLM suggestion prototype against the held-out benchmark; do not train a supervised model unless the labelled corpus and learning curve justify it.
5. Add the suggestion UI with mandatory user confirmation.
6. Monitor accepted, rejected, and corrected suggestions; only confirmed labels may be added to the training corpus.

## Current status

Design only. No model is trained, no AI API is called, and no user data is sent to an external provider. Deterministic parsing and validation remain the only production authority.


## Benchmark seed status

A first manually reviewed benchmark seed now exists at docs/column-mapping-benchmark-seed.json with 72 examples covering positive aliases, negative mappings, ambiguous identifiers, source-specific fields, and structural cases. It is a discovery/evaluation seed only, not a training corpus and not a claim of model accuracy. Before model evaluation, labels must be reviewed by source family, the synthetic/adversarial sources must be tagged, and held-out source repositories must be kept separate from examples used to tune prompts or rules.


## Benchmark regression coverage

The backend test suite now checks the 72 reviewed examples against the deterministic alias map. Positive examples must resolve to the reviewed canonical field; negative and manual-review examples must not be auto-mapped. This guards against reintroducing risky brand/manufacturer, product_type/category, model/MPN, and product_id/SKU substitutions while the AI suggestion layer is developed.
