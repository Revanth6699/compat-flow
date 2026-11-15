# Industry-aware catalog mapping and validation

Status: researched implementation specification. This document does not claim that runtime import validation already supports these profiles.

## Design rules

1. Keep source columns and source values unchanged for lineage and audit.
2. Map only when the source header and observed values support the same meaning. Similar words are not sufficient.
3. Separate product master data, sellable variants, supplier offers, inventory, packaging/logistics, identifiers, technical attributes, and compatibility relationships.
4. A field can be required, conditional, recommended, or optional by profile and product class. Never make every field in a profile globally mandatory.
5. Never fabricate an internal SKU, manufacturer, MPN, product title, price, unit, or compatibility relationship when the source does not contain it.
6. Mapping confidence and data quality are separate measurements.
7. Unknown columns remain available as source attributes; do not silently discard them.

## Shared canonical entities

### Product master
- `source_product_id`: identifier assigned by the source system; not automatically an SKU.
- `sku`: seller's internal stock-keeping identifier.
- `gtin`: GS1 trade-item identifier (GTIN-8/12/13/14 as applicable).
- `title`, `description`, `brand`, `manufacturer`, `category`, `product_type`, `status`.
- `mpn`: manufacturer's part number; distinct from seller SKU and model number.
- `model_number`: manufacturer model designation; do not assume it is an MPN.

### Variant
- `parent_product_id`, `variant_id`, `variant_sku`, `variant_options`.
- Typed variant attributes such as `size`, `colour`, `material`, `pattern`, `capacity`, `storage`, `voltage`, or `finish`, depending on product class.
- Each independently tradeable variant should retain its own identifier where required by the relevant GTIN allocation rules.

### Supplier offer / commercial terms
- `supplier_id`, `supplier_sku`, `supplier_product_id`, `buyer_sku`.
- `unit_price`, `currency`, `price_basis`, `minimum_order_quantity`, `order_multiple`, `unit_of_measure`, `lead_time_days`, `availability`, `valid_from`, `valid_to`.
- These are offer/relationship fields, not universal product-master fields.

### Packaging and logistics
- `packaging_level`, `units_per_inner`, `inners_per_case`, `units_per_case`, `case_gtin`, `net_weight`, `gross_weight`, `length`, `width`, `height`, `dimension_unit`, `weight_unit`, `pallet_quantity`.
- Never compare or aggregate measurements without units.

### Technical attributes and relationships
- Technical attributes are key/value/unit records associated with a product class, not an ever-growing set of hard-coded columns.
- Compatibility/fitment and replacement/interchange are explicit relationships, not plain product-description text.

## Profile 1: D2C brand catalog

### Expected source columns and canonical mappings
| Source column examples | Canonical field | Mapping / validation |
|---|---|---|
| product_id, item_id, catalog_id | source_product_id | Preserve source namespace; unique within source, not presumed to be SKU |
| sku, seller_sku, variant_sku | sku / variant_sku | Unique within seller/variant scope |
| parent_id, parent_product_id, style_id | parent_product_id | Must resolve to a parent product |
| title, product_title, product_name | title | Non-empty for a sellable listing; length and suspicious-placeholder checks |
| brand, brand_name | brand | Do not map to manufacturer |
| category, product_category | category | Resolve against source taxonomy where available |
| size, size_name | variant attribute: size | Normalize only with retained original; category-specific allowed values |
| color, colour, color_name | variant attribute: colour | Normalize spelling/value vocabulary; do not merge distinct colors |
| material, fabric, composition | variant attribute or technical attribute: material | Preserve multi-material composition; do not assume one material |
| variant_id, option_id | variant_id | Unique in its source scope |
| image_url, image, image_count | digital asset / image_count | URL syntax and reachability are separate checks; count must be non-negative integer |
| description, product_description | description | Text field; never map description-length/count fields to it |
| weight, weight_g, net_weight | net_weight + unit | Parse explicit unit; reject unitless conversion assumptions |

### Business rules
- Variant must reference an existing parent.
- Variant-defining attributes must be present when the category/channel requires them.
- Variant identifiers must not collide within their defined scope.
- Do not require size for products where size is not applicable.
- Brand and manufacturer remain separate concepts.
- Image count, image URL presence, and image quality are separate checks.

## Profile 2: General ecommerce / marketplace listing

### Expected source columns and canonical mappings
| Source column examples | Canonical field | Mapping / validation |
|---|---|---|
| product_id, listing_id, item_id | source_product_id / listing_id | Preserve marketplace/source namespace |
| sku, seller_sku, merchant_sku | sku | Unique within seller catalog |
| gtin, barcode, ean, upc | gtin / product identifier | Validate format/check digit where the identifier scheme supports it; preserve leading zeros |
| title, product_title, item_name | title | Non-empty; channel length rules are channel-specific |
| brand, brand_name | brand | Distinct from manufacturer |
| category, category_path, product_type | category / product_type | Map taxonomy with source and target taxonomy retained; product_type is not automatically category |
| price, sale_price, selling_price | offer.unit_price | Non-negative decimal; currency required to interpret price |
| currency, currency_code | offer.currency | ISO 4217 code format; do not infer from locale |
| stock, quantity, inventory_qty | inventory quantity | Non-negative; distinguish available, on-hand, and reserved |
| item_group_id, parent_sku | parent_product_id / variant group | Group variants without collapsing their identifiers |
| size, color, colour, material | variant attributes | Require only when relevant to product class or channel |
| weight, length, width, height | logistics measurements | Explicit units and non-negative values |
| image_link, image_url, additional_image_link | digital assets | Validate URL structure; availability and image policy checks are separate |

### Business rules
- Price validation is impossible to interpret fully without currency and price basis.
- Inventory values must distinguish on-hand, reserved, and available quantities.
- Variant grouping must not cause distinct sellable items to be deduplicated.
- GTIN, seller SKU, listing ID, and source product ID are different identifier types.
- Listing-channel required attributes must be applied by destination channel and category, not universally.

## Profile 3: Automotive aftermarket

Standards basis: Auto Care ACES communicates vehicle/equipment fitment; PIES communicates product information. They are complementary, not interchangeable.

### Expected source columns and canonical mappings
| Source column examples | Canonical field | Mapping / validation |
|---|---|---|
| sku, seller_sku, distributor_sku | sku | Seller/distributor identifier |
| brand, brand_name | brand | Brand-table identity where a standard feed is used |
| manufacturer, mfr_name | manufacturer | Legal/trading manufacturer identity |
| mpn, mfr_part_number, manufacturer_part_number | mpn | Unique in manufacturer/brand scope; do not substitute generic part_id without evidence |
| part_number, catalog_number | manufacturer part number or source part number | Resolve semantics from source context; ambiguous part_number must not be guessed |
| part_type, product_class, category | product_class/category | Normalize to appropriate classification, e.g. PCdb when exchanging ACES/PIES data |
| year, vehicle_year | fitment.year | Valid year and explicit vehicle application |
| make, vehicle_make | fitment.make | Resolve to controlled vehicle reference |
| model, vehicle_model | fitment.model | Resolve with year/make; model alone is not a complete fitment |
| engine, submodel, trim, body, qualifier | fitment qualifier attributes | Keep qualifiers structured; don't flatten into free text |
| position, placement | fitment.position | Validate against applicable product class and qualifier vocabulary |
| interchange, cross_reference | interchange relationship | Store source, direction and relationship type |
| replacement_part, superseded_by | replacement relationship | Preserve direction and effective status |
| weight, dimensions, upc | PIES product attributes | Typed values with units and identifier scheme |

### Business rules
- Fitment is a structured relation between a part and a vehicle/equipment configuration.
- Year/make/model alone may be insufficient; product-specific qualifiers can be essential.
- Validate referenced vehicle/configuration, qualifier, brand and product-class codes against the licensed/current reference datasets when available.
- A part with no fitment data must not be reported as fitting all vehicles.
- Replacement/interchange is not the same as vehicle fitment.
- Do not claim ACES conformance merely because a CSV contains year, make and model columns.

## Profile 4: Electronics

### Expected source columns and canonical mappings
| Source column examples | Canonical field | Mapping / validation |
|---|---|---|
| sku, seller_sku | sku | Seller identifier |
| manufacturer, mfr | manufacturer | Manufacturer identity |
| brand, brand_name | brand | Keep separate from manufacturer |
| mpn, manufacturer_part_number | mpn | Manufacturer-assigned part identifier |
| model, model_number, model_name | model_number | Do not map to MPN without evidence |
| gtin, ean, upc | gtin | Validate identifier scheme and preserve leading zeros |
| category, product_class | category/product_class | Use product-class-specific attribute requirements |
| voltage, input_voltage | technical attribute: voltage | Numeric/range value with unit and AC/DC context |
| current, power, wattage | technical attribute | Numeric value and unit; valid ranges depend on class |
| frequency, frequency_range | technical attribute | Range and Hz unit where applicable |
| capacity, memory, storage | technical attribute | Preserve unit and distinguish RAM/storage/capacity type |
| screen_size, resolution, processor, ports | technical attributes | Validate type and class-specific formats |
| compatible_models, model_compatibility | compatibility relationship | Resolve referenced model identifiers; do not infer from title |
| certification, energy_rating, compliance_doc | compliance attributes/assets | Validate only against relevant market/product regulations |
| dimensions, weight | logistics attributes | Explicit units and non-negative values |

### Business rules
- MPN, model number, SKU and GTIN are separate identifiers.
- Compatibility must resolve to explicit model/product references and a relationship type.
- Technical values require units and context; e.g. voltage without AC/DC context may be incomplete.
- Certification and energy-label requirements depend on product class and market.
- Use ETIM/eCl@ss product classes and features when the supplier/channel uses those classifications; do not assume all electronics use one taxonomy.

## Profile 5: Industrial / MRO

### Expected source columns and canonical mappings
| Source column examples | Canonical field | Mapping / validation |
|---|---|---|
| manufacturer, maker | manufacturer | Manufacturer identity |
| mpn, manufacturer_part_number, manufacturer_item_number | mpn | Manufacturer-scoped identifier |
| supplier_part_number, vendor_part_number | supplier_sku / supplier part identifier | Supplier-scoped, not automatically manufacturer MPN |
| part_number | mpn or supplier part number | Ambiguous unless source context establishes owner |
| product_name, description, short_description | title / description | Keep title and description distinct |
| unspsc, etim_class, eclass, product_class | classification code | Retain scheme and version with code |
| material, grade, finish | technical attributes | Controlled vocabulary where available |
| diameter, length, width, height, thickness | technical attributes | Numeric values with units; check class-specific ranges |
| pressure_rating, temperature_range, voltage, power | technical attributes | Validate unit, range, and applicable operating context |
| standard, specification, certification | standards/compliance attributes | Preserve issuing body, identifier and version |
| replacement_part, alternate_part, supersedes | replacement/interchange relationship | Direction and relationship type required |
| compatible_equipment, equipment_model | compatibility relationship | Resolve equipment identifiers where possible |
| uom, unit_of_measure | offer/packaging UOM | Controlled unit vocabulary; do not assume each/box/case equivalence |

### Business rules
- Technical attribute requirements are product-class-specific, not one global list.
- Numeric attributes require units; range attributes require lower and upper bounds.
- Classification code must be interpreted together with its scheme and version.
- Manufacturer part number and supplier part number must remain distinct.
- Replacement and interchange claims require explicit source evidence.

## Profile 6: Wholesale / distribution

### Expected source columns and canonical mappings
| Source column examples | Canonical field | Mapping / validation |
|---|---|---|
| product_id, item_id | source_product_id | Source namespace; not presumed to be SKU |
| sku, buyer_sku, customer_sku | buyer_sku / sku | Identify whose SKU it is |
| supplier_sku, vendor_sku, supplier_item_code | offer.supplier_sku | Unique within supplier scope |
| supplier_id, vendor_id, supplier_code | offer.supplier_id | Must resolve to supplier master |
| brand, brand_name | brand | Brand identity |
| manufacturer, mfr | manufacturer | Manufacturer identity |
| mpn, manufacturer_part_number | mpn | Manufacturer identifier |
| gtin, case_gtin, barcode | product/packaging identifier | Identify packaging level; each/case/pallet GTINs are not interchangeable |
| price, unit_cost, wholesale_price | offer.unit_price | Non-negative decimal with currency and price basis |
| currency, currency_code | offer.currency | ISO 4217 format; never infer silently |
| moq, minimum_order_quantity | offer.minimum_order_quantity | Greater than zero; compatible with order UOM |
| order_multiple, order_increment | offer.order_multiple | Positive; ordered quantities must respect multiple |
| quantity, available_qty, stock | inventory quantity | Distinguish available/on-hand/reserved |
| uom, unit_of_measure | offer.unit_of_measure | Controlled unit vocabulary |
| pack_size, units_per_case, case_qty | packaging hierarchy | Positive integer/decimal as appropriate; hierarchy consistency |
| lead_time, lead_time_days | offer.lead_time_days | Non-negative duration with explicit unit |
| valid_from, valid_to, price_effective_date | offer validity | End must not precede start |
| incoterm, payment_terms | commercial terms | Preserve named term and version/context; not product attributes |

### Business rules
- Supplier SKU is unique only within its supplier scope; the same code may exist at another supplier.
- MOQ and order multiple must use a defined UOM.
- Unit, case and pallet quantities must reconcile with the packaging hierarchy.
- Price must carry currency and basis (per each, case, weight, etc.).
- Inventory snapshots must be timestamped and tied to a warehouse/location where applicable.
- Supplier offer data must not overwrite product-master identity data.

## Cross-profile validation and metrics

### Mapping confidence (not model accuracy)
Use independent evidence:
- Header semantics and known aliases.
- Sample-value type/pattern fit.
- Profile/product-class compatibility.
- Cross-column constraints and identifier uniqueness.
- Conflicts with other candidate columns.

High confidence can be auto-mapped only after calibration against labelled examples. Ambiguous fields should remain unmapped and be surfaced for clarification. A fixed score such as 95% must not be assigned to every alias.

### Data-quality dimensions
Report separate metrics rather than one opaque score:
- Mapping coverage: mapped source columns / relevant source columns.
- Required-field completeness: populated applicable required fields / applicable required fields.
- Type and format validity: valid values / non-empty values evaluated.
- Identifier uniqueness: unique identifiers / identifiers evaluated, at the correct namespace/scope.
- Referential integrity: resolved parent, supplier, warehouse, fitment, replacement and compatibility references / references evaluated.
- Attribute consistency: values satisfying cross-field and unit constraints / constraints evaluated.
- Commercial consistency: valid price/currency/UOM/MOQ/order-multiple combinations.
- Freshness: age of source snapshot or effective data, when timestamps exist.

Show numerator, denominator, exclusions and severity for every metric. Do not score non-applicable fields as missing. A critical failure (e.g. invalid vehicle fitment or broken parent-variant relationship) must remain visible even if the aggregate score is high.

### Severity model
- Critical: identifier collision in required scope, invalid required field, broken required relationship, invalid unit/quantity relationship, invalid fitment reference.
- Warning: optional/recommended data missing, suspicious but not provably invalid value, incomplete product content.
- Informational: unmapped extra column, normalization suggestion, profile inference with uncertainty.

### Industry detection
Infer a candidate profile from headers, sample values, file structure and relationship columns. Return the profile plus evidence and confidence. Do not silently force a profile when evidence conflicts. Ask the user only when two or more profiles remain materially ambiguous.

## Olist dataset handling (important semantic exception)

The Olist products table contains:
- `product_id`: source product identifier, **not evidence of a seller SKU**.
- `product_category_name`: category name (Portuguese taxonomy).
- `product_name_lenght`: character count, not product title.
- `product_description_lenght`: character count, not product description.
- `product_photos_qty`: photo count.
- `product_weight_g`: weight in grams.
- `product_length_cm`, `product_height_cm`, `product_width_cm`: dimensions in centimetres.

Correct mapping: `product_id -> source_product_id`; category -> category; length-count fields -> `name_length` and `description_length`; photo count -> `image_count`; physical measures -> typed logistics attributes. This source does not provide an actual product title, description, SKU, manufacturer or MPN in this table. Do not fabricate them to satisfy a legacy required-field schema.

## Standards and research references

- GS1 Global Data Model: https://ref.gs1.org/standards/gdm/ (harmonized trade-item attributes)
- GS1 identifier guidance: https://support.gs1.org/support/solutions/articles/43000734469-what-kind-of-information-is-linked-to-the-gs1-identification-key-
- GS1 attribute implementation guideline: https://ref.gs1.org/guidelines/gdm-implementation/
- Google Merchant Center product data specification: https://support.google.com/merchants/answer/7052112
- Auto Care ACES: https://www.autocare.org/aces/
- Auto Care PIES: https://www.autocare.org/pies
- ETIM model information: https://www.etim-international.com/classification/model-information/
- ETIM feature/value/unit model: https://www.etim-uk-and-ie.org/the-standard/structure-of-the-etim-data-model/
- IPC electronics supply-chain PDX: https://www.electronics.org/ipc-standards-related-resources
- GS1 US product field definitions: https://www.help.gs1us.org/product-field-definitions

## Implementation boundary

This specification is not yet the runtime implementation. The current importer uses a fixed product preview model with mandatory `sku`, `name`, `manufacturer`, `part_number`, and `category`; that model cannot correctly represent every profile above. Implementing these profiles safely requires a flexible staging/attribute model and separate product, variant, offer, inventory, packaging, identifier and relationship validation. Do not just add aliases to the existing fixed schema.
