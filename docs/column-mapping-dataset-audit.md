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
