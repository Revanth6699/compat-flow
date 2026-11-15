# Product Scope

**Status:** Initial product scope. The assumptions below have not been validated through customer research.

## Purpose

CompatFlow is being developed to help teams review and manage changes in supplier product catalogs. The intended workflow is to receive supplier data, standardize it, compare it with an existing catalog, review proposed changes, and prepare approved records for export or publishing.

## Initial market focus

The first discovery focus is the automotive aftermarket. This is a working choice for product research, not a claim that demand, willingness to pay, or an unmet market need has been established.

## Proposed V1 workflow

1. Create a supplier profile.
2. Upload supplier catalog data.
3. Check the file structure, required fields, and values.
4. Map supplier columns to the CompatFlow catalog model.
5. Compare incoming records with the current catalog.
6. Classify records as new, changed, unchanged, removed, or invalid.
7. Review proposed changes.
8. Approve or reject each change.
9. Export approved records in a normalized format.

## Out of scope

- A proprietary vehicle-fitment database.
- Automatic safety-critical compatibility decisions.
- Treating an unverified fuzzy match as proof of fitment.
- Writing to Shopify before reconciliation and approval have been tested.
- Production-scale performance or availability claims without load and recovery testing.

## Questions to resolve

- Who is the buyer, and which supplier-data tasks do they handle today?
- Which data formats and source systems are used in practice?
- How consistent are supplier fields and identifiers?
- How accurately can incoming records be reconciled against reviewed examples?
- What approval, rollback, and audit history do customers require?
- What operating and support costs follow from real usage?

The scope should change only when these questions are answered with evidence from prospective users and tested workflows.