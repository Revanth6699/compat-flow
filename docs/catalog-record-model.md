# Catalog Record Model

## 1. Why the model separates record types

The original `products` table represents a product master but also carries a supplier link and canonical SKU. Supplier feeds can contain multiple supplier-specific identifiers and offers for one product, multiple sellable variants, and changing stock positions.

Combining these concepts in one product row loses source provenance and history. CompatFlow separates product identity from identifiers, variants, offers, and inventory snapshots.

## 2. Record types

### 2.1 Product master — `products`

Owns stable product identity and core descriptive attributes:

- Organization-scoped canonical SKU.
- Product name.
- Manufacturer.
- Manufacturer part number (MPN).
- Category.

Supplier identifiers, prices, warehouse quantities, and variant attributes do not belong on this row. The canonical SKU and MPN remain on the product master; additional identifiers use the typed identifier registry.

### 2.2 Product identifiers — `product_identifiers`

Stores one additional identifier per row:

- Identifier type: UPC, EAN, GTIN, ASIN, marketplace ID, manufacturer code, source product ID, or another explicit type.
- Namespace, such as `global` or a marketplace.
- Identifier value stored as text to preserve leading zeros.
- Source reference and primary flag.

SKU, MPN, supplier SKU, and marketplace identifiers are separate namespaces. Identifier values must not be numerically coerced.

### 2.3 Product variants — `product_variants`

Stores each sellable variation:

- Parent product and tenant.
- Optional variant SKU.
- Structured attributes such as color, size, capacity, material, or pack size.
- Active/inactive state.

A product can have multiple variants. A variant is not a duplicate product solely because its parent name is the same.

### 2.4 Supplier offers — `supplier_offers`

Stores one supplier's commercial listing:

- Supplier and optional matched product.
- Supplier SKU and supplier product ID, distinct from canonical SKU.
- Unit price with explicit currency and unit of measure.
- Minimum order quantity and lead time.
- Source URL and offer status.

An offer can exist before it is confidently matched to a product. A supplier SKU must not be silently promoted to canonical SKU.

### 2.5 Inventory snapshots — `inventory_snapshots`

Stores append-only, point-in-time stock positions:

- Product, optional supplier offer, and warehouse code.
- Quantity on hand, reserved, and available.
- Snapshot timestamp and source reference.

Snapshots preserve history rather than overwriting the latest stock figure. The three quantities remain separate. The system may flag when available quantity differs from on-hand minus reserved; it must not silently rewrite supplier values.

## 3. Tenant isolation and constraints

All new tables carry `organization_id`. Composite foreign keys bind variants, offers, products, suppliers, and inventory snapshots within the same organization.

List queries filter by the authenticated organization. Negative prices, quantities, invalid minimum order quantities, and negative lead times are rejected at the API or database boundary.

## 4. API surface

All endpoints require authentication, the applicable catalog read/write permission, and the `supplier_catalogs` plan feature.

| Resource | Endpoints |
|---|---|
| Product identifiers | `GET/POST /api/v1/product-identifiers` |
| Product variants | `GET/POST /api/v1/product-variants` |
| Supplier offers | `GET/POST /api/v1/supplier-offers` |
| Inventory snapshots | `GET/POST /api/v1/inventory-snapshots` |

Create operations verify that referenced products, suppliers, and offers belong to the caller's organization. Inventory snapshot creation also verifies that an attached supplier offer belongs to the same product.

## 5. Current limitations

- Existing CSV validation still produces a product-master preview; it does not persist these new record types.
- Automatic product matching and supplier-offer linking are not implemented.
- No AI model is trained or called by this record model.
- AI may suggest mappings or matches with evidence and confidence, but deterministic validation remains authoritative.
- Inventory reconciliation metrics are not generated until import lineage and business rules are defined.
