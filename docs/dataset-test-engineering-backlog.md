# Dataset Test Findings and Engineering Backlog

**Evidence window:** 22 November 2026  
**Test scope:** Four unique CSV datasets and one JSON ingestion attempt. The repeated E-commerce Inventory CSV submission is excluded as duplicate evidence.

## Executive assessment

The four CSV files reached the profiling/validation pipeline. The JSON file was rejected before profiling because multiple candidate arrays were found. Current evidence shows reliable structural profiling for the CSV samples, but uneven semantic field mapping and domain-rule coverage. A 100% pass rate must never be presented as full-dataset correctness when source columns are unmapped or relevant rules were not evaluated.

This backlog separates confirmed workflow behavior from coverage gaps. An unmapped field is not automatically a defect: the canonical model may not support it, or its meaning may be ambiguous. Likewise, a rule marked not evaluated is not a failed validation.

## Evidence and issue register

| ID | Dataset | Finding | Classification | Priority |
|---|---|---|---|---|
| CF-TEST-001 | PriceRunner CSV | Merchant, cluster and category identifiers/labels were not mapped | Mapping coverage gap | P1 |
| CF-TEST-002 | PriceRunner CSV | Merchant/listing/cluster relationships were not demonstrated | Capability gap; investigate | P2 |
| CF-TEST-003 | PriceRunner CSV | ID-like numeric columns were displayed as numeric rather than identifier semantics | Reporting/type inference gap | P2 |
| CF-TEST-004 | PriceRunner CSV | Repeated report sections repeat rule/findings information | Confirmed UX issue | P3 |
| CF-TEST-005 | PriceRunner CSV | Product, merchant offer and cluster identity are not clearly distinguished | Domain-model gap | P1 |
| CF-TEST-006 | E-commerce Inventory CSV | Only name and category mapped; id, stock_level, price and created_at remained unmapped | Mapping coverage gap | P1 |
| CF-TEST-007 | E-commerce Inventory CSV | stock_level existed but inventory rules were not applicable | Confirmed rule-selection gap | P1 |
| CF-TEST-008 | E-commerce Inventory CSV | Missing-cell aggregate was visible; row-level missing-cell traceability was not demonstrated | Traceability gap; export unverified | P2 |
| CF-TEST-009 | E-commerce Inventory CSV | Price checks were not demonstrated | Coverage gap; business policy needed | P2 |
| CF-TEST-010 | E-commerce Inventory CSV | Mixed category values were accepted because no taxonomy was configured | Not a defect without a taxonomy; investigate configuration | P3 |
| CF-TEST-011 | E-commerce Inventory CSV | Not-evaluated checks do not identify the precise missing canonical evidence clearly enough | Confirmed report clarity gap | P2 |
| CF-TEST-012 | Supply Chain CSV | Supplier name was not mapped | Mapping coverage gap | P1 |
| CF-TEST-013 | Supply Chain CSV | Stock-level columns did not activate inventory checks | Confirmed rule-selection gap | P1 |
| CF-TEST-014 | Supply Chain CSV | Price checks were not demonstrated | Coverage gap; business policy needed | P2 |
| CF-TEST-015 | Supply Chain CSV | Manufacturing and quality checks were not demonstrated | Capability gap | P2 |
| CF-TEST-016 | Supply Chain CSV | Logistics checks were not demonstrated | Capability gap | P2 |
| CF-TEST-017 | Supply Chain CSV | Product ID, SKU and supplier product identity need separate semantics | Domain-model gap | P1 |
| CF-TEST-018 | Supply Chain CSV | One primary dataset type obscured the presence of multiple business domains | Classification/model gap | P1 |
| CF-TEST-019 | Zepto CSV | MRP, discount, available quantity, discounted selling price, weight and out-of-stock status were unmapped | Mapping coverage gap | P1 |
| CF-TEST-020 | Zepto CSV | 100% pass rate was shown despite unmapped fields and narrow demonstrated checks | Confirmed reporting defect | P0 |
| CF-TEST-021 | Zepto CSV | Discount and price consistency checks were not demonstrated | Coverage gap | P2 |
| CF-TEST-022 | Zepto CSV | Pack/product quantity and available stock must remain distinct | Domain-model gap | P1 |
| CF-TEST-023 | Zepto CSV | outOfStock boolean was not recognized as an inventory status | Mapping/coverage gap | P2 |
| CF-TEST-024 | Zepto CSV | Data type was shown as unavailable for mapped fields | Confirmed report gap | P2 |
| CF-TEST-025 | E-commerce Inventory JSON | Upload stopped with “JSON contains multiple candidate record arrays; configure record_path” | Confirmed ingestion blocker for this file | P1 |

## Existing work already merged

The following changes are already present on `main` and must not be reimplemented:

- PR #55: in-file product parent/replacement relationship checks.
- PR #56: broader product-catalog classification for common commerce and ERP schemas.
- PR #57: product-master aliases and quality checks for identifiers, categories, names, descriptions, photos and physical attributes.
- PR #58: ERP identifier aliases.
- PR #59: canonical product mapping display in reports.
- PR #60: source-row-level product issue traceability.

These merges do not resolve all findings above. In particular, inventory, commercial pricing/discount fields, multi-domain classification, JSON candidate selection and honest validation-coverage presentation remain.

## Implementation sequence

### Release A — Trustworthy results and core field semantics (P0/P1)

1. Distinguish validation pass rate from validation coverage. Show evaluated records/rules, unmapped source columns, and not-evaluated checks together. Never imply unmapped fields passed.
2. Extend conservative canonical mappings for inventory quantities, price bases, discounts, supplier names and marketplace listing/cluster identifiers.
3. Run inventory checks when inventory evidence exists even when the primary profile is product catalog. Do not map a generic `quantity` field to stock.
4. Keep source product ID, seller SKU, merchant listing ID, product cluster ID, pack quantity and available stock distinct.
5. Preserve identifier semantics for ID/SKU/barcode-like headers even when values contain only digits.

**Acceptance criteria**
- Zepto maps MRP/list price, discounted selling price, discount percentage, available quantity and out-of-stock status separately where headers are present.
- E-commerce Inventory maps stock_level and price; negative stock and non-positive price values are evaluated without assuming a currency.
- Supply Chain maps supplier name and stock levels without conflating SKU and product ID.
- PriceRunner merchant and cluster fields remain separate from product identity.
- A pass-rate label explicitly states its evaluation scope and does not treat unmapped or not-evaluated fields as passed.

### Release B — JSON record selection (P1)

1. Discover candidate object arrays at nested paths, not only top-level properties.
2. Score candidates using record-field evidence and path context. Auto-select only when one candidate is clearly stronger.
3. When candidates remain ambiguous, return their exact paths and a clear selection instruction; do not silently choose an arbitrary array.
4. Preserve selected `record_path` in parse metadata and test nested/multiple-array cases.

**Acceptance criteria**
- Product array is selected when its field evidence clearly outranks unrelated arrays such as orders/categories.
- Two equally plausible product arrays still require explicit selection.
- Existing explicit `record_path` behavior remains supported.
- Parser limits, flattening behavior and source traceability remain intact.

### Release C — Broader domain validation (P2)

- Add opt-in/configurable supplier, marketplace, manufacturing, quality and logistics checks.
- Keep supplier offer price/currency distinct from product list/selling price.
- Add configurable category taxonomy and business-required-field policies rather than universal assumptions.
- Add row-level missing-value details and verify CSV/JSON exports.

### Release D — Report quality (P2/P3)

- Remove duplicate sections or make each section answer a distinct question.
- Include inferred data types for industry-validation fields.
- Make rule status, coverage, unmapped fields and row-level evidence easy to understand.

## Release gates

- Run backend unit tests, lint, migrations/alembic checks where applicable, and frontend lint/build.
- Add regression tests for all four CSV schema shapes and JSON arrays, including ambiguous inputs.
- Confirm the production backend and frontend are on the same reviewed commit/release.
- Verify health endpoints and the import/profile/validation flows after deployment.
- Do not claim connector, external-reference, scale or production-readiness coverage from these five file tests; those areas were not exercised.
- Keep the existing stateless preview behavior: uploads in this workflow must not be persisted or committed to the organization catalog.

## Evidence limitations

- The same E-commerce Inventory CSV was submitted twice; it counts once.
- The JSON upload did not produce a profile, so its contents and candidate-array paths have not yet been inspected.
- Row-level missing-value export behavior was not verified.
- Manufacturing, logistics, supplier reference, external taxonomy, SQL Server, REST API and SFTP workflows were not tested in this dataset exercise.
- The test reports are snapshots; fixes merged after a report was generated require rerunning that dataset against the current production build.
