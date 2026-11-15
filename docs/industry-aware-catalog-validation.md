# Industry-Aware Catalog Mapping and Validation

**Status:** Research-backed implementation specification  
**Boundary:** This document does not claim that runtime import validation supports every profile described here.

## 1. Design rules

1. Preserve source columns and values for lineage and audit.
2. Map a field only when its header and observed values support the same meaning. Similar wording is not sufficient evidence.
3. Separate product master data, variants, supplier offers, inventory, packaging/logistics, identifiers, technical attributes, and compatibility relationships.
4. A field may be required, conditional, recommended, or optional by profile and product class. Do not make every profile field globally mandatory.
5. Do not fabricate SKU, manufacturer, MPN, title, price, unit, or compatibility relationships when the source does not provide them.
6. Mapping confidence and data quality are separate measurements.
7. Preserve unknown columns as source attributes; do not silently discard them.

## 2. Shared canonical entities

### Product master

- `source_product_id`: source-system identifier; not automatically an SKU.
- `sku`: seller's internal stock-keeping identifier.
- `gtin`: GS1 trade-item identifier (GTIN-8/12/13/14, as applicable).
- `title`, `description`, `brand`, `manufacturer`, `category`, `product_type`, `status`.
- `mpn`: manufacturer's part number; distinct from seller SKU and model number.
- `model_number`: manufacturer model designation; do not assume it is an MPN.

### Variant

- `parent_product_id`, `variant_id`, `variant_sku`, `variant_options`.
- Typed attributes such as `size`, `colour`, `material`, `pattern`, `capacity`, `storage`, `voltage`, or `finish`, depending on product class.
- Independently tradeable variants retain their own identifiers where required by the applicable GTIN allocation rules.

### Supplier offer and commercial terms

- `supplier_id`, `supplier_sku`, `supplier_product_id`, `buyer_sku`.
- `unit_price`, `currency`, `price_basis`, `minimum_order_quantity`, `order_multiple`, `unit_of_measure`, `lead_time_days`, `availability`, `valid_from`, `valid_to`.
- These are offer or relationship fields, not universal product-master fields.

### Packaging and logistics

- `packaging_level`, `units_per_inner`, `inners_per_case`, `units_per_case`, `case_gtin`.
- `net_weight`, `gross_weight`, `length`, `width`, `height`, `dimension_unit`, `weight_unit`, `pallet_quantity`.
- Do not compare or aggregate measurements without units.

### Technical attributes and relationships

- Model technical attributes as key/value/unit records associated with a product class, not as an unbounded set of hard-coded columns.
- Represent compatibility/fitment and replacement/interchange as explicit relationships, not plain product-description text.

## 3. Industry profiles

### 3.1 D2C brand catalog

| Source column examples | Canonical field | Mapping and validation |
|---|---|---|
| `product_id`, `item_id`, `catalog_id` | `source_product_id` | Preserve source namespace; unique within source; not presumed to be SKU |
| `sku`, `seller_sku`, `variant_sku` | `sku` / `variant_sku` | Unique within seller/variant scope |
| `parent_id`, `parent_product_id`, `style_id` | `parent_product_id` | Must resolve to a parent product |
| `title`, `product_title`, `product_name` | `title` | Non-empty for a sellable listing; check length and placeholders |
| `brand`, `brand_name` | `brand` | Do not map to manufacturer |
| `category`, `product_category` | `category` | Resolve against source taxonomy where available |
| `size`, `size_name` | Variant attribute: size | Normalize only while retaining original value |
| `color`, `colour`, `color_name` | Variant attribute: colour | Normalize spelling without merging distinct colours |
| `material`, `fabric`, `composition` | Variant or technical attribute: material | Preserve multi-material composition |
| `variant_id`, `option_id` | `variant_id` | Unique within source scope |
| `image_url`, `image`, `image_count` | Digital asset / `image_count` | URL syntax, reachability, and count are separate checks |
| `description`, `product_description` | `description` | Text field; do not map length/count fields to it |
| `weight`, `weight_g`, `net_weight` | `net_weight` plus unit | Require explicit unit; do not assume conversions |

**Business rules**
- A variant must reference an existing parent.
- Variant-defining attributes are required only when relevant to the category/channel.
- Variant identifiers must not collide within their defined scope.
- Do not require size where size is not applicable.
- Brand and manufacturer are separate concepts.
- Image count, URL presence, and image quality are separate checks.

### 3.2 General ecommerce / marketplace listing

| Source column examples | Canonical field | Mapping and validation |
|---|---|---|
| `product_id`, `listing_id`, `item_id` | `source_product_id` / `listing_id` | Preserve marketplace/source namespace |
| `sku`, `seller_sku`, `merchant_sku` | `sku` | Unique within seller catalog |
| `gtin`, `barcode`, `ean`, `upc` | `gtin` / product identifier | Validate scheme/check digit where supported; preserve leading zeros |
| `title`, `product_title`, `item_name` | `title` | Non-empty; channel length rules are channel-specific |
| `brand`, `brand_name` | `brand` | Distinct from manufacturer |
| `category`, `category_path`, `product_type` | `category` / `product_type` | Preserve source and target taxonomy; product_type is not automatically category |
| `price`, `sale_price`, `selling_price` | `offer.unit_price` | Non-negative decimal; currency required |
| `currency`, `currency_code` | `offer.currency` | ISO 4217 code format; do not infer from locale |
| `stock`, `quantity`, `inventory_qty` | Inventory quantity | Distinguish available, on-hand, and reserved |
| `item_group_id`, `parent_sku` | Parent product / variant group | Group variants without collapsing identifiers |
| `size`, `color`, `colour`, `material` | Variant attributes | Require only when relevant to product class or channel |
| `weight`, `length`, `width`, `height` | Logistics measurements | Require explicit units and non-negative values |
| `image_link`, `image_url`, `additional_image_link` | Digital assets | URL structure, availability, and image policy are separate checks |

**Business rules**
- Price requires currency and price basis for meaningful interpretation.
- Inventory must distinguish on-hand, reserved, and available quantities.
- Variant grouping must not deduplicate distinct sellable items.
- GTIN, seller SKU, listing ID, and source product ID are different identifier types.
- Apply listing-channel requirements by destination channel and category, not universally.

### 3.3 Automotive aftermarket

**Standards context:** Auto Care ACES communicates vehicle/equipment fitment. PIES communicates product information. They are complementary standards, not interchangeable.

| Source column examples | Canonical field | Mapping and validation |
|---|---|---|
| `sku`, `seller_sku`, `distributor_sku` | `sku` | Seller/distributor identifier |
| `brand`, `brand_name` | `brand` | Brand identity where a standard feed is used |
| `manufacturer`, `mfr_name` | `manufacturer` | Manufacturer identity |
| `mpn`, `mfr_part_number`, `manufacturer_part_number` | `mpn` | Manufacturer-scoped identifier |
| `part_number`, `catalog_number` | MPN or source part number | Resolve from source context; do not guess ambiguous meaning |
| `part_type`, `product_class`, `category` | Product class/category | Normalize to the appropriate classification |
| `year`, `vehicle_year` | `fitment.year` | Valid year and explicit application |
| `make`, `vehicle_make` | `fitment.make` | Resolve to controlled vehicle reference |
| `model`, `vehicle_model` | `fitment.model` | Resolve with year/make; model alone is incomplete |
| `engine`, `submodel`, `trim`, `body`, `qualifier` | Fitment qualifier attributes | Keep qualifiers structured |
| `position`, `placement` | `fitment.position` | Validate against product class and qualifier vocabulary |
| `interchange`, `cross_reference` | Interchange relationship | Store source, direction, and relationship type |
| `replacement_part`, `superseded_by` | Replacement relationship | Preserve direction and effective status |
| `weight`, dimensions, `upc` | PIES product attributes | Typed values with units and identifier scheme |

**Business rules**
- Fitment is a structured relation between a part and a vehicle/equipment configuration.
- Year/make/model may be insufficient; product-specific qualifiers can be essential.
- Validate vehicle/configuration, qualifier, brand, and product-class codes against licensed/current reference data when available.
- A part with no fitment data must not be reported as fitting all vehicles.
- Replacement/interchange is not the same as vehicle fitment.
- Do not claim ACES conformance because a CSV contains year, make, and model columns.

### 3.4 Electronics

| Source column examples | Canonical field | Mapping and validation |
|---|---|---|
| `sku`, `seller_sku` | `sku` | Seller identifier |
| `manufacturer`, `mfr` | `manufacturer` | Manufacturer identity |
| `brand`, `brand_name` | `brand` | Keep separate from manufacturer |
| `mpn`, `manufacturer_part_number` | `mpn` | Manufacturer-assigned identifier |
| `model`, `model_number`, `model_name` | `model_number` | Do not map to MPN without evidence |
| `gtin`, `ean`, `upc` | `gtin` | Validate identifier scheme and preserve leading zeros |
| `category`, `product_class` | Category/product class | Use product-class-specific requirements |
| `voltage`, `input_voltage` | Technical attribute: voltage | Numeric/range value with unit and AC/DC context |
| `current`, `power`, `wattage` | Technical attribute | Numeric value and unit; ranges depend on class |
| `frequency`, `frequency_range` | Technical attribute | Range and Hz unit where applicable |
| `capacity`, `memory`, `storage` | Technical attribute | Preserve unit and distinguish RAM/storage/capacity |
| `screen_size`, `resolution`, `processor`, `ports` | Technical attributes | Validate type and class-specific format |
| `compatible_models`, `model_compatibility` | Compatibility relationship | Resolve model identifiers; do not infer from title |
| `certification`, `energy_rating`, `compliance_doc` | Compliance attributes/assets | Validate against relevant market/product rules |
| Dimensions, weight | Logistics attributes | Explicit units and non-negative values |

**Business rules**
- MPN, model number, SKU, and GTIN are separate identifiers.
- Compatibility must resolve to explicit model/product references and a relationship type.
- Technical values require units and context.
- Certification and energy-label requirements depend on product class and market.
- Use ETIM/eCl@ss classifications when the supplier/channel uses them; do not assume one taxonomy applies to all electronics.

### 3.5 Industrial / MRO

| Source column examples | Canonical field | Mapping and validation |
|---|---|---|
| `manufacturer`, `maker` | `manufacturer` | Manufacturer identity |
| `mpn`, `manufacturer_part_number`, `manufacturer_item_number` | `mpn` | Manufacturer-scoped identifier |
| `supplier_part_number`, `vendor_part_number` | Supplier SKU / supplier identifier | Supplier-scoped; not automatically MPN |
| `part_number` | MPN or supplier part number | Ambiguous unless source context establishes ownership |
| `product_name`, `description`, `short_description` | Title / description | Keep title and description distinct |
| `unspsc`, `etim_class`, `eclass`, `product_class` | Classification code | Retain scheme and version |
| `material`, `grade`, `finish` | Technical attributes | Controlled vocabulary where available |
| Dimensions and measurements | Technical attributes | Numeric values with units and class-specific ranges |
| `pressure_rating`, `temperature_range`, `voltage`, `power` | Technical attributes | Validate unit, range, and operating context |
| `standard`, `specification`, `certification` | Standards/compliance attributes | Preserve issuer, identifier, and version |
| `replacement_part`, `alternate_part`, `supersedes` | Replacement/interchange relationship | Direction and relationship type required |
| `compatible_equipment`, `equipment_model` | Compatibility relationship | Resolve equipment identifiers where possible |
| `uom`, `unit_of_measure` | Offer/packaging UOM | Controlled vocabulary; do not assume each/box/case equivalence |

**Business rules**
- Technical attribute requirements are product-class-specific.
- Numeric attributes require units; range attributes require lower and upper bounds.
- Classification codes must retain scheme and version.
- Manufacturer and supplier part numbers must remain distinct.
- Replacement/interchange claims require explicit source evidence.

### 3.6 Wholesale / distribution

| Source column examples | Canonical field | Mapping and validation |
|---|---|---|
| `product_id`, `item_id` | `source_product_id` | Source namespace; not presumed to be SKU |
| `sku`, `buyer_sku`, `customer_sku` | Buyer SKU / SKU | Identify whose SKU it is |
| `supplier_sku`, `vendor_sku`, `supplier_item_code` | `offer.supplier_sku` | Unique within supplier scope |
| `supplier_id`, `vendor_id`, `supplier_code` | `offer.supplier_id` | Must resolve to supplier master |
| `brand`, `brand_name` | `brand` | Brand identity |
| `manufacturer`, `mfr` | `manufacturer` | Manufacturer identity |
| `mpn`, `manufacturer_part_number` | `mpn` | Manufacturer identifier |
| `gtin`, `case_gtin`, `barcode` | Product/packaging identifier | Identify packaging level; each/case/pallet GTINs are not interchangeable |
| `price`, `unit_cost`, `wholesale_price` | `offer.unit_price` | Non-negative decimal with currency and price basis |
| `currency`, `currency_code` | `offer.currency` | ISO 4217 format; do not infer silently |
| `moq`, `minimum_order_quantity` | `offer.minimum_order_quantity` | Greater than zero; compatible with order UOM |
| `order_multiple`, `order_increment` | `offer.order_multiple` | Positive; ordered quantities must respect multiple |
| `quantity`, `available_qty`, `stock` | Inventory quantity | Distinguish available, on-hand, and reserved |
| `uom`, `unit_of_measure` | `offer.unit_of_measure` | Controlled unit vocabulary |
| `pack_size`, `units_per_case`, `case_qty` | Packaging hierarchy | Validate positive quantities and hierarchy |
| `lead_time`, `lead_time_days` | `offer.lead_time_days` | Non-negative duration with explicit unit |
| `valid_from`, `valid_to`, `price_effective_date` | Offer validity | End must not precede start |
| `incoterm`, `payment_terms` | Commercial terms | Preserve term and version/context; not product attributes |

**Business rules**
- Supplier SKU is unique only within its supplier scope.
- MOQ and order multiple require a defined UOM.
- Unit, case, and pallet quantities must reconcile with packaging hierarchy.
- Price must include currency and basis (each, case, weight, etc.).
- Inventory snapshots must be timestamped and tied to a warehouse/location where applicable.
- Supplier offer data must not overwrite product-master identity data.

## 4. Cross-profile validation and metrics

### Mapping confidence

Use independent evidence:
- Header semantics and known aliases.
- Sample-value type and pattern fit.
- Profile/product-class compatibility.
- Cross-column constraints and identifier uniqueness.
- Conflicts with other candidate columns.

Auto-mapping at high confidence requires calibration against labelled examples. Ambiguous fields remain unmapped and are surfaced for clarification. Do not assign a fixed score such as 95% to every alias.

### Data-quality dimensions

Report separate metrics rather than one opaque score:

- **Mapping coverage:** mapped source columns / relevant source columns.
- **Required-field completeness:** populated applicable required fields / applicable required fields.
- **Type and format validity:** valid values / non-empty values evaluated.
- **Identifier uniqueness:** unique identifiers / identifiers evaluated in the correct namespace and scope.
- **Referential integrity:** resolved parent, supplier, warehouse, fitment, replacement, and compatibility references / references evaluated.
- **Attribute consistency:** values satisfying cross-field and unit constraints / constraints evaluated.
- **Commercial consistency:** valid price/currency/UOM/MOQ/order-multiple combinations.
- **Freshness:** age of source snapshot or effective data, when timestamps exist.

Show numerator, denominator, exclusions, and severity for every metric. Do not score non-applicable fields as missing. Critical failures must remain visible even when an aggregate score is high.

### Severity

- **Critical:** identifier collision in required scope, invalid required field, broken required relationship, invalid unit/quantity relationship, or invalid fitment reference.
- **Warning:** optional/recommended data missing, suspicious but not provably invalid value, or incomplete product content.
- **Informational:** unmapped extra column, normalization suggestion, or profile inference with uncertainty.

### Industry detection

Infer a candidate profile from headers, sample values, file structure, and relationship columns. Return the profile with evidence and confidence. Do not silently force a profile when evidence conflicts. Ask for clarification only when two or more profiles remain materially ambiguous.

## 5. Olist dataset exception

The Olist products table contains:

- `product_id`: source product identifier, **not evidence of a seller SKU**.
- `product_category_name`: category name (Portuguese taxonomy).
- `product_name_lenght`: character count, not product title.
- `product_description_lenght`: character count, not product description.
- `product_photos_qty`: photo count.
- `product_weight_g`: weight in grams.
- `product_length_cm`, `product_height_cm`, `product_width_cm`: dimensions in centimetres.

Correct mapping:
- `product_id` → `source_product_id`.
- `product_category_name` → category.
- Length-count fields → `name_length` and `description_length`.
- Photo count → `image_count`.
- Physical measures → typed logistics attributes.

This table does not provide an actual product title, description, SKU, manufacturer, or MPN. Do not fabricate them to satisfy a legacy required-field schema.

## 6. Standards and research references

- [GS1 Global Data Model](https://ref.gs1.org/standards/gdm/)
- [GS1 identifier guidance](https://support.gs1.org/support/solutions/articles/43000734469-what-kind-of-information-is-linked-to-the-gs1-identification-key-)
- [GS1 attribute implementation guideline](https://ref.gs1.org/guidelines/gdm-implementation/)
- [Google Merchant Center product data specification](https://support.google.com/merchants/answer/7052112)
- [Auto Care ACES](https://www.autocare.org/aces/)
- [Auto Care PIES](https://www.autocare.org/pies)
- [ETIM model information](https://www.etim-international.com/classification/model-information/)
- [ETIM feature/value/unit model](https://www.etim-uk-and-ie.org/the-standard/structure-of-the-etim-data-model/)
- [IPC electronics supply-chain PDX](https://www.electronics.org/ipc-standards-related-resources)
- [GS1 US product field definitions](https://www.help.gs1us.org/product-field-definitions)

## 7. Implementation boundary

This specification is not the runtime implementation. The current importer uses a fixed product preview model with mandatory `sku`, `name`, `manufacturer`, `part_number`, and `category`. That model cannot correctly represent every profile above.

Safe implementation requires a flexible staging/attribute model and separate product, variant, offer, inventory, packaging, identifier, and relationship validation. Do not implement these profiles by adding aliases to the existing fixed schema.
