# Catalog record model separation

## Why the previous model was insufficient

The original `products` table represents a product master but also carries one supplier link and one canonical SKU. Real supplier feeds contain multiple supplier-specific identifiers and offers for the same product, multiple sellable variants, and changing stock positions. Treating all of these as columns on a single product row loses provenance and history.

## Record types

### 1. Product master — existing `products` table

Owns stable product identity and core descriptive attributes:
- organization-scoped canonical SKU
- product name
- manufacturer
- manufacturer part number
- category

Supplier-specific identifiers, prices, warehouse quantities, and variant attributes do not belong on this row. The canonical SKU and MPN stay on the master; additional identifiers use the typed identifier registry.

### 2. Product identifiers — `product_identifiers`

One row per additional identifier attached to a product:
- identifier type: UPC, EAN, GTIN, ASIN, marketplace ID, manufacturer code, source product ID, or other
- explicit namespace, such as `global` or a marketplace
- identifier value stored as text so leading zeros are preserved
- source reference and primary flag

SKU, MPN, supplier SKU, and marketplace identifiers remain separate namespaces. Identifier values are never numerically coerced.

### 3. Product variants — `product_variants`

One row per sellable variation of a product:
- parent product and tenant
- optional variant SKU
- structured attributes such as color, size, capacity, material, or pack size
- active/inactive state

The same product can have multiple variants. A variant is not a duplicate product merely because the parent name is the same.

### 4. Supplier offers — `supplier_offers`

One row per supplier's commercial listing:
- supplier and optional matched product
- supplier SKU and supplier product ID kept distinct from canonical SKU
- unit price plus explicit currency and unit of measure
- minimum order quantity and lead time
- source URL and offer status

An offer can exist before it has been confidently matched to a product. A supplier's SKU is never silently promoted to the canonical SKU.

### 5. Inventory snapshots — `inventory_snapshots`

Append-only point-in-time stock positions:
- product, optional supplier offer, warehouse code
- quantity on hand, reserved, and available as decimal quantities
- snapshot timestamp and source reference

Snapshots preserve history instead of overwriting the latest stock figure. The three quantities are stored separately; the system can flag when available differs from on-hand minus reserved. It does not silently rewrite supplier values.

## Tenant isolation and constraints

All new tables carry `organization_id`. Composite foreign keys bind variants, offers, products, suppliers, and inventory snapshots within the same organization. List queries filter by the authenticated organization. Negative prices, quantities, invalid MOQ and negative lead times are rejected at the API/database boundary.

## API surface

All endpoints require authentication, the existing catalog read/write permission, and the `supplier_catalogs` plan feature.

- `GET/POST /api/v1/product-identifiers`
- `GET/POST /api/v1/product-variants`
- `GET/POST /api/v1/supplier-offers`
- `GET/POST /api/v1/inventory-snapshots`

The create endpoints verify that referenced products, suppliers, and offers belong to the caller's organization. Inventory snapshot creation verifies that an attached supplier offer is for the same product.

## Deliberate non-goals in this phase

- Existing CSV validation still produces a product-master preview; it does not yet persist these new record types.
- No automatic product matching or supplier-offer linking is performed.
- No AI model is trained or called. The AI layer must suggest mappings/matches with evidence and confidence; deterministic validation remains authoritative.
- No inventory reconciliation metric is generated until the import pipeline has reliable row-level lineage and defined business rules.
