# CompatFlow — Initial V1 scope

## Product purpose
A supplier catalog change-operations platform that receives supplier product data, standardizes records, identifies changes against an existing catalog, supports review and prepares approved changes for publishing.

## First vertical
Automotive aftermarket parts is the working discovery vertical. This is not a claim that the market or competitor gap has been validated.

## V1 workflow
1. Create a supplier profile.
2. Upload a supplier CSV.
3. Validate file format, required columns and values.
4. Normalize supplier fields into the CompatFlow product schema.
5. Compare the incoming records with existing catalog records.
6. Classify records as new, changed, unchanged, removed or invalid.
7. Show the proposed change set for human review.
8. Approve or reject changes.
9. Export approved changes as a normalized CSV.

## Explicit exclusions
- No proprietary vehicle fitment database.
- No automatic safety-critical compatibility decisions.
- No unverified fuzzy matching as final proof of fitment.
- No Shopify write access until reconciliation and approval workflows are tested.
- No claims of production scale until load and recovery tests pass.
