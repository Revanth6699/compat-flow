# Column-Mapping Dataset Audit

Status: in progress  
Branch: `feature/backend-auth-authorization`  
Purpose: inspect real-world CSV headers individually and use observed evidence to improve column mapping without guessing.

## Inspection rules

- Each listed file was opened and its header plus sample rows inspected.
- A file is one inspected sample; related feeds and duplicate schemas are noted rather than treated as new mapping evidence.
- A header being observed does not automatically make it a safe alias.
- The current canonical fields are `sku`, `name`, `manufacturer`, `part_number`, `category`, `compatibility`, and `replacement_sku`.
- Files that do not contain the fields required by a CompatFlow profile are still useful for identifying unmapped fields and scope gaps.

## Inspected datasets

### 1. Shopify DTC catalog sample

- Source: https://github.com/wookat/shopify-products-dataset-sample/blob/main/data/catalog_sample_500.csv
- Type: public Shopify product/variant catalog export
- Delimiter: comma
- Header: `store_domain,store_name,country_guess,product_id,title,handle,product_type,vendor,tags,variant_id,sku,variant_title,price,compare_at_price,available,image_count,published_at,created_at,updated_at,fetched_at,niche`
- Observed useful fields: `title`, `product_type`, `vendor`, `sku`, `product_id`, `variant_id`
- Mapping observations: `title` is a strong product-name candidate; `product_type` is a category candidate; `sku` is explicit. Do not map `product_id` or `variant_id` to SKU without a documented supplier convention. `vendor` is not necessarily the legal manufacturer.
- Current mapper gap: no canonical fields for store/vendor provenance, product/variant IDs, price, stock/availability, or timestamps. The sample does not provide manufacturer part number.

### 2. Refurbed supplier feed — Gitaarbarbaar

- Source: https://github.com/brendanrefurbed/supplier-feeds-public/blob/main/gitaarbarbaar_refurbed_import.csv
- Type: supplier feed
- Delimiter: semicolon
- Header: `product_code;price_gross;vat;currency;stock;name`
- Observed useful fields: `product_code`, `name`, `stock`, `price_gross`, `vat`, `currency`
- Mapping observations: `product_code` is a SKU-like supplier identifier; `name` is product name. No manufacturer, manufacturer part number, or category field is present.
- Current mapper gap: parser currently constructs a comma-delimited reader directly; this semicolon feed will not be parsed as six columns without delimiter detection/configuration. The general profile also requires fields absent from this feed.

### 3. ArrowheadPHX hardware catalog

- Source: https://github.com/Mr-bgrand/ArrowheadPHX-Product-Catalog/blob/main/arrowheadphx_hardware_flagships.csv
- Type: retailer/distributor hardware catalog
- Delimiter: comma
- Header: `sku,name,brand,category,price,url,in_stock,description,manufacturer_part_number,upc,weight,custom_fields,image_url`
- Observed useful fields: `sku`, `name`, `brand`, `category`, `manufacturer_part_number`, `upc`
- Mapping observations: current aliases cover SKU, name, brand-as-manufacturer, category, and manufacturer_part_number. Brand-to-manufacturer remains a lower-confidence semantic mapping and should be shown as such. `upc` is a barcode/GTIN candidate, not SKU or part number.
- Current mapper gap: no canonical barcode/GTIN field.

### 4. Tanzu catalogue-loader sample feed

- Source: https://github.com/tanzu-team/catalogue-loader/blob/main/data/sample_feed.csv
- Type: sample product catalog feed
- Delimiter: comma
- Header: `id,title,price,stock,description,brand,category`
- Observed useful fields: `title`, `brand`, `category`, `stock`
- Mapping observations: `title` and `category` are clear candidates. Generic `id` must not automatically become SKU; `brand` is not guaranteed to be manufacturer. No part number is supplied.
- Current mapper gap: no safe generic mapping for `id`; no manufacturer part number.

### 5. Supervisely snacks catalog

- Source: https://github.com/supervisely-ecosystem/snacks-catalog/blob/master/snacks_catalog.csv
- Type: scraped grocery/snack retail catalog
- Delimiter: comma
- Header: `Made in,Brand name,Product Name,Price,Page URL,Image URL,PRODUCT ID,Additional info`
- Observed useful fields: `Brand name`, `Product Name`, `PRODUCT ID`
- Mapping observations: normalized `Product Name` is a strong name candidate; normalized `Brand name` is a brand candidate; `PRODUCT ID` is a source product identifier and should not be treated as SKU without evidence.
- Current mapper gap: no alias for `brand_name` currently maps because it is supported as a brand alias only after normalization to `brand_name`; existing alias is present. `product_id` is intentionally not mapped to SKU.

### 6. Books catalogue scraper

- Source: https://github.com/0xCyclopath/books-catalogue-scraper/blob/main/output/books.csv
- Type: scraped online bookstore catalog
- Delimiter: comma
- Header: `title,category,price,availability,rating,product_url,image_url,scrape_timestamp`
- Observed useful fields: `title`, `category`
- Mapping observations: `title` and `category` are clear candidates. This retail catalog does not contain SKU, manufacturer, or part number.
- Current mapper gap: profile requirements are stricter than this source schema; this should remain unmapped/incomplete rather than inventing identifiers.

### 7. Best Buy scraped product catalog

- Source: https://github.com/ksaravan910/BestBuyCatalogScraper/blob/master/bestbuy-products.csv
- Type: scraped electronics retailer catalog
- Delimiter: comma
- Header: `ID,Name,Link,Image,Price,Category,,,,,,,Category`
- Observed useful fields: `ID`, `Name`, `Category`
- Mapping observations: `Name` and `Category` are clear candidates. `ID` is a retailer product ID, not necessarily a supplier SKU. The file contains empty header positions and a repeated `Category` header.
- Current mapper gap: current header normalization rejects empty headers and duplicate normalized headers. That is a deliberate safety behavior, but this real scraped export demonstrates a need for an explicit duplicate/blank-header handling policy rather than silently accepting ambiguous columns.

### 8. Grocery store product export

- Source: https://github.com/Varshinirao18/grocery-store-management-sql/blob/main/Products%20(1).csv
- Type: grocery inventory/product table
- Delimiter: comma
- Header: `ProductID,Name,SupplierID,CategoryID,Price`
- Mapping observations: `Name` is a clear name candidate. `ProductID` is a source-system identifier, not automatically a supplier SKU. `SupplierID` and `CategoryID` are foreign keys, not manufacturer/category names.
- Current mapper gap: this file needs relational lookups to resolve supplier and category IDs. Mapping the IDs directly to manufacturer/category would corrupt meaning.

## Findings so far

1. The current mapper already handles several common product headers: `sku`, `product_code`, `name`, `title`, `brand`, `brand_name`, `product_type`, `category`, and `manufacturer_part_number`.
2. A number of ordinary retail catalogs do not contain manufacturer part numbers. Requiring the current general profile's full field set makes them ineligible unless the user maps/ supplies missing values. Do not solve this by mapping unrelated IDs or descriptions into required fields.
3. Supplier feeds may use semicolon delimiters; current parser setup appears comma-only.
4. Scraped exports can contain blank or duplicate headers. Current rejection prevents silent data corruption, but the UI should explain the exact issue and allow a deliberate manual disambiguation path.
5. Generic identifiers (`id`, `product_id`, `variant_id`, `PRODUCT ID`) are not safe SKU aliases without source-specific context.
6. `brand`, `brand_name`, and `vendor` should not be treated as equivalent to legal manufacturer at full confidence.
7. Several datasets have useful fields outside the current canonical model: barcode/GTIN, price, currency, stock, availability, URLs, variant IDs, and provenance. These should not be forced into existing canonical fields.

## Next work

Continue inspecting datasets individually and append each verified file here. After the sample is broad enough, decide whether to add source profiles, context-aware mapping, optional-field support, delimiter detection, and an explicit duplicate-header workflow. Then update implementation and regression tests together.


### 9. Product CSV import minimal sample

- Source: https://github.com/robinprism/product-csv-import/blob/main/samples/valid.csv
- Type: minimal product import fixture
- Delimiter: comma
- Header: `sku,name,price`
- Sample rows: `MUG-01,Coffee mug,299`; `PEN-02,Blue pen,20`
- Mapping observations: `sku` and `name` are explicit and unambiguous. `price` is a commercial attribute, not a substitute for category, manufacturer, or part number.
- Current mapper gap: the fixture has only two of the current general profile's required fields. It should produce a clear missing-fields result rather than infer manufacturer/category/part number.

### 10. Refurbished device combination-count feed

- Source: https://github.com/gaurangkumar-patel/supplier-product-parser/blob/master/examples/combination_count.csv
- Type: refurbished electronics/device variant feed
- Delimiter: comma
- Header: `make,model,colour,capacity,network,grade,condition,count`
- Sample row: `Apple,Iphone 6s plus 16gb,Working,Grade C - Acceptable Condition,16GB,ROSE GOLD,Unlocked,17`
- Mapping observations: `make` identifies the device make/brand; `model` identifies model; `colour`, `capacity`, `network`, `grade`, and `condition` describe variant/condition attributes; `count` is quantity. The sample's values suggest the source data may have semantic column/value misalignment (e.g. `colour` contains "Working", while `condition` contains "Unlocked"), so don't infer mappings from names alone without validating row values.
- Current mapper gap: no canonical fields for brand/make, model, variant attributes, grade, condition, or quantity. Do not map `make` to manufacturer at full confidence or `model` to manufacturer part number without a source-specific rule.


## Implementation update after the first 10 samples

- Implemented common delimiter detection for comma, semicolon, tab, and pipe-separated files in `backend/app/services/catalog_csv.py`.
- Added regression coverage for semicolon supplier feeds, tab-delimited feeds, and pipe-delimited feeds in `backend/tests/test_catalog_csv.py`.
- The change deliberately does not add speculative aliases for generic IDs, brand/vendor-to-manufacturer, make/model-to-MPN, or retail product IDs.
- This is an initial parser improvement, not proof that every supplier CSV dialect is supported. Quoting, encoding, malformed headers, and unusual delimiters still require dedicated test coverage.
- CI/test execution status: pending verification after the latest commits.


### 11. Codbex Hestia product master export

- Source: https://github.com/codbex/codbex-hestia-data-sample/blob/5c148a5d00287c4941fbeabe8b1bb6af9d86804f/codbex-hestia-data-sample/products.csv
- Type: ERP-style product master export
- Delimiter: comma
- Header: `PRODUCT_ID,PRODUCT_SKU,PRODUCT_TITLE,PRODUCT_MODEL,PRODUCT_BATCH,PRODUCT_BASEUNIT,PRODUCT_PRICE,PRODUCT_VATRATE,PRODUCT_TYPE,PRODUCT_CATEGORY,PRODUCT_MANUFACTURER,PRODUCT_WEIGHT,PRODUCT_HEIGHT,PRODUCT_LENGTH,PRODUCT_WIDTH,PRODUCT_NAME,PRODUCT_COMPANY,PRODUCT_UPC,PRODUCT_EAN,PRODUCT_JAN,PRODUCT_ISBN,PRODUCT_MPN,PRODUCT_ENABLED`
- Mapping observations: normalized `PRODUCT_SKU`, `PRODUCT_TITLE`, `PRODUCT_CATEGORY`, and `PRODUCT_MANUFACTURER` align with existing aliases. `PRODUCT_MPN` is an explicit manufacturer part-number header and is a safe additional alias. `PRODUCT_MODEL` is not automatically MPN; `PRODUCT_ID` and `PRODUCT_COMPANY` are source-system keys. UPC/EAN/JAN/ISBN are distinct identifier types and must not be collapsed into SKU or MPN.
- Current mapper gap: no canonical barcode/GTIN or ISBN field; product model, batch, base unit, dimensions, tax rate, and enabled status are outside the current schema.

### 12. 9NJA Wholesales product export

- Source: https://github.com/Owotimilehin/9NJAWHOLESALES/blob/87b9643582bed68a5a149c28700aefd6dfe842b2/products.csv
- Type: wholesale product export template
- Delimiter: comma
- Header only: `name,sku,short_description,description,retail_price,wholesale_price,cost_price,sale_price,stock,low_stock_threshold,category_id,manufacturer_id,material,is_active,is_featured,is_new,installment_eligible,care_instructions,youtube_url,pieces_name_1,...,pieces_quantity_5`
- Mapping observations: `name` and `sku` are explicit. `category_id` and `manufacturer_id` are foreign keys, not category/manufacturer labels. The file contains no data rows, so value patterns and referential integrity cannot be checked.
- Current mapper gap: separate price types, stock thresholds, product flags, material, and component dimensions are not represented in the canonical schema. Do not map foreign-key IDs to descriptive fields.

### 13. Product Data Copilot sample catalog

- Source: https://github.com/david-r-tech/product-data-copilot/blob/8e1fc1beb5992088df9a0072a2fbc48ec7956025/data/sample_products.csv
- Type: multi-category DTC product catalog with enrichment fields
- Delimiter: comma
- Header: `sku,product_name,category,description,brand,manufacturer,attributes,ean,language,price,image_url,warning_notes,translation_de,translation_en`
- Mapping observations: explicit SKU, product name, category, and manufacturer are present. Both brand and manufacturer exist separately; preserve that distinction rather than treating them as synonyms. Rows include missing product names, blank brand/manufacturer values, empty prices, a zero price, malformed/short EAN-like values, missing image URLs, and relative image paths.
- Current mapper gap: no EAN/GTIN, language, structured attributes, warning notes, translation, price, or image fields. This sample is useful for testing row-level completeness and value validation, not just header matching.

### 14. Nested electronics product sample

- Source: https://github.com/bearcat513/json2csv/blob/69ec03a7537a9055a28c0237d7961c87ec998cdc/_dummy_files/example2-products.csv
- Type: electronics product sample
- Delimiter: comma
- Header: `sku,name,category,price,stock,manufacturer,releaseYear,specs.cpu,specs.ram,specs.storage`
- Mapping observations: SKU, name, category, and manufacturer are explicit. `releaseYear` and dotted `specs.*` headers represent attributes, not canonical part numbers or categories. The name contains a quoted inch mark, which is valid CSV quoting and should remain intact.
- Current mapper gap: product specifications, release year, price, and stock are outside the canonical schema.

### 15. OpenCart universal import sample

- Source: https://github.com/ahmtilri-glitch/opencart/blob/0a5101e9290934a56b9b097cd6364630693f6427/universal_import/demo/products.csv
- Type: OpenCart product import template
- Delimiter: comma
- Header: `name,description,seo_keyword,seo_h1,tag,model,sku,location,price,quantity,manufacturer,product_category,image`
- Mapping observations: name, SKU, manufacturer, and product_category are explicit. `model` is separate from SKU and cannot be presumed to be MPN. The sample repeats the same SKU value across multiple product rows, so duplicate-SKU validation should flag it. Quoted text containing commas in `tag` confirms the parser must respect CSV quoting.
- Current mapper gap: SEO fields, tags, image, location, price, and quantity are outside the canonical schema.

### 16. CIMS product master demo export

- Source: https://github.com/Raih9K/cims-microservice/blob/fb06c822d934d91d51402b02a3c17247d70e7550/frontend/public/demo_products.csv
- Type: multi-category commerce/catalog master
- Delimiter: comma
- Header: `SKU,Title,Category,Condition,Brand,Manufacturer,Country of Origin,Selling Price,Cost Price,MSRP,Purchase Price,Retail Price,Stock,Weight,Length,Width,Height,Short Description,Main Description`
- Mapping observations: SKU, Title, Category, and Manufacturer are explicit. Brand is separately supplied and should not overwrite Manufacturer. The four price columns are different commercial measures; none should be mapped into another. Condition and country of origin are product attributes.
- Current mapper gap: multiple price bases, stock, condition, origin, dimensions, and descriptions are not in the canonical model.

### 17. Pennbridge industrial fastener import template

- Source: https://github.com/Trueballs/pennbridge-order-desk/blob/b097f72a26917525327895ec9f43deb11c6cc9c4/docs/import-templates/products.csv
- Type: industrial/fastener product import template
- Delimiter: comma
- Header: `sku,description,selling_unit,list_price,family,category,units_per_pack,manufacturer_reference,active,attributes,external_id`
- Mapping observations: SKU and category are explicit. `description` may be a fallback product-name candidate only with low confidence and sample review. `family` is not necessarily category; `manufacturer_reference` is not necessarily a manufacturer part number; `external_id` is not SKU. The `attributes` cell uses semicolons inside a comma-delimited CSV record, so delimiter detection must not split values inside quoted fields.
- Current mapper gap: manufacturer reference, selling unit, pack quantity, active status, and structured attributes are not represented. No manufacturer name or explicit MPN is supplied.

### 18. RecallReady lot-level inventory sample

- Source: https://github.com/Pranay847/recallready/blob/90077fc81a710836c73c023d503d43a2df370fbd/public/samples/inventory.csv
- Type: lot/batch-level inventory and traceability feed
- Delimiter: comma
- Header: `id,product,brand,sku,upc,lot,quantity,unit,location`
- Mapping observations: SKU is explicit; `product` is a plausible name candidate in this inventory context but should not become a global alias without more evidence. `brand` is not guaranteed to be manufacturer. UPC, lot, quantity, unit, and location represent distinct traceability/inventory dimensions. One row has a missing lot and one row has zero quantity.
- Current mapper gap: no UPC/GTIN, lot/batch, inventory quantity, unit, or location fields.

### 19. Lotline inventory sample

- Source: https://github.com/vamsi920/lotline/blob/c254257a554c04f3361876d4dcc080c0387c374c/public/sample-inventory.csv
- Type: multi-location lot-level inventory
- Delimiter: comma
- Header: `id,sku,product,brand,lot,location,quantity,unit,unit_cost`
- Mapping observations: SKU is explicit; `product` and `brand` are context-dependent descriptive fields. The sample contains missing brand/lot values and apparent cross-field inconsistencies (for example, a row's product and SKU/brand combination do not consistently describe the same item). Lot values should not be treated as product part numbers. Repeated SKU values across locations/lots are legitimate inventory records and must not be evaluated as duplicate product-master SKUs without grouping by the intended business key.
- Current mapper gap: inventory location, lot, quantity, unit, and unit cost are not part of the product master schema. This is evidence that product-master duplicate rules cannot be reused unchanged for inventory feeds.

### 20. Order Management System inventory export

- Source: https://github.com/Farheen0519/Order_Management_System/blob/cf6d874dfcc4025a80e17dfa85676c4218a7158b/app/documents/inventory.csv
- Type: warehouse inventory/product export
- Delimiter: comma
- Header: `sku,product_name,category,brand,description,quantity_available,reorder_level,price,currency,warehouse_location,status`
- Mapping observations: SKU, product name, and category are explicit. Brand is a brand, not a guaranteed legal manufacturer. Quantity available and reorder level are separate inventory measures; price must be interpreted with currency. Warehouse location and status are operational fields.
- Current mapper gap: quantity available, reorder level, currency, warehouse location, and status are outside the canonical product schema.

## Findings after 20 individually inspected files

1. The observed sources now include ERP product masters, wholesale imports, DTC/retail catalogs, OpenCart imports, industrial fasteners, and lot-level inventory feeds.
2. Add `product_mpn` as an explicit alias for canonical `part_number`; do not infer MPN from `model`, `manufacturer_reference`, `external_id`, or lot values.
3. Keep brand, vendor, and manufacturer distinct when the source provides separate columns. The current lower-confidence brand-to-manufacturer fallback remains a compromise, not a semantic equivalence.
4. Preserve distinct identifiers: SKU, product ID, UPC/EAN/GTIN, ISBN, MPN, lot/batch, and supplier references are not interchangeable.
5. Inventory feeds require a different data model and duplicate-key policy from product-master catalogs. Repeated SKU by location/lot can be valid inventory granularity.
6. Multi-price feeds require explicit price types and currency. Do not collapse retail, wholesale, cost, sale, MSRP, and purchase price into one generic price field.
7. Sample values matter: missing names, zero/blank prices, malformed barcode values, repeated SKUs, missing lots, and inconsistent row relationships reveal issues that header-only mapping cannot catch.
8. One source (dataset 12) contained headers but no data rows; it is useful for schema inspection only, not for validating value patterns.
9. ML/AI should be used only to rank candidate mappings from header semantics plus sampled values and context, with confidence calibration and user confirmation. Validation metrics, duplicate detection, and data-quality calculations must remain deterministic. These 20 files are a discovery/evaluation seed, not a training corpus sufficient for a reliable general-purpose model.

## Implementation update after the first 20 samples

- Added `product_mpn` as a high-confidence alias for `part_number`, backed by an explicit header observed in dataset 11.
- Added a regression test for `product_mpn` mapping.
- Dataset review does not justify global aliases for `product`, `model`, `manufacturer_reference`, `external_id`, generic IDs, lot, UPC/EAN, or brand/vendor.
- The latest CI run (43557274169) completed successfully: backend tests, Alembic upgrade, Ruff, Bandit, frontend lint, and frontend production build all passed.
- No ML model has been trained or integrated yet. A labelled, source-separated mapping evaluation set and deterministic baseline are required before selecting or training a model.
