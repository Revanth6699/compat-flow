# Product Scope

**Status:** Initial V1 scope; discovery assumptions are not validated market claims.

## Product purpose

CompatFlow is intended to support supplier-catalog change operations. The workflow receives supplier product data, standardizes records, compares incoming data with an existing catalog, supports human review, and prepares approved changes for publishing.

## Initial discovery vertical

Automotive aftermarket parts is the current discovery vertical. This is a working focus, not evidence that market demand, willingness to pay, or a competitor gap has been validated.

## Target V1 workflow

1. Create a supplier profile.
2. Upload supplier catalog data.
3. Validate file structure, required fields, and values.
4. Map supplier fields to the CompatFlow catalog model.
5. Compare incoming records with existing catalog records.
6. Classify records as new, changed, unchanged, removed, or invalid.
7. Present proposed changes for human review.
8. Approve or reject each proposed change.
9. Export approved changes in a normalized format.

## Explicit exclusions

- No proprietary vehicle-fitment database.
- No automatic safety-critical compatibility decisions.
- No unverified fuzzy match treated as proof of fitment.
- No Shopify write access until reconciliation and approval workflows are tested.
- No production-scale claims until load, recovery, and operational tests pass.

## Validation required before expanding scope

- Confirm the target buyer and the supplier-data workflows they currently use.
- Validate data availability, field consistency, and source-system constraints.
- Test reconciliation accuracy against independently reviewed examples.
- Define approval, rollback, and audit requirements before enabling publishing.
- Validate operating cost and support requirements with real users.
