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


### 21. Nagual legacy commerce product export

- Source: https://github.com/magma-labs/nagual/blob/988d7d1991041ba4bbb5c48fcb0b9d481953fd40/data_examples/products.csv
- Type: legacy commerce product export fixture
- Delimiter: comma
- Header: `id,mode,ean,upc,unit,step,name,description,long_description,status,from,to,searchable?,searchable if unavailable?,template,tax class id,brand,manufacturer,SKU,placement,rank,sitemap?,sitemap change frequency,sitemap priority,page title,page keywords,color,organization`
- Mapping observations: `name`, `SKU`, and `manufacturer` are explicit headers. `id`, EAN, and UPC remain separate identifiers. The sample rows look like schema fixtures/placeholders rather than reliable commercial records; values such as `EAN`, `UPC`, and `MANUFACTURER` are literal placeholders. The `color` value contains a comma and is correctly quoted.
- Current mapper gap: no barcode/GTIN, unit, tax, status, dates, SEO, or product-attribute fields.

### 22. Cordango warehouse inventory sample

- Source: https://github.com/Cordango/examples/blob/457ada54c4850231b31507abb09cbbc8c6c58ac7/warehouse/samples/inventory.csv
- Type: automotive parts warehouse inventory feed
- Delimiter: comma
- Header: `SKU,Name,ManufacturerPartNumber,Barcode,Category,Location,Quantity,SafetyStock,Supplier,SupplierSKU,UnitCost`
- Mapping observations: SKU, Name, Category, and ManufacturerPartNumber are explicit. CamelCase `ManufacturerPartNumber` normalizes to `manufacturerpartnumber`, not the existing snake_case alias. `SupplierSKU` is a separate supplier-specific identifier and must not replace the internal SKU. Barcode, quantity, safety stock, location, and unit cost are separate fields. One SKU appears twice with the same product/stock details, so duplicate interpretation needs source context.
- Current mapper gap: add the exact camelCase MPN header form; inventory quantity, safety stock, location, supplier SKU, barcode, and unit cost remain outside the current product master.

### 23. StoreFrontServer inventory sample

- Source: https://github.com/DammitJavi/StoreFrontServer/blob/d0949f4bd820a90196262d30be7f38e9fd3e9d3f/src/assets/inventory.csv
- Type: general retail inventory export
- Delimiter: comma
- Header: `ID,Name,Category,Price,Quantity,SKU,Barcode,Supplier,Last Restock Date,Low Stock Threshold,Weight (lbs),Dimensions (in),Status`
- Mapping observations: Name, Category, and SKU are explicit. Generic ID is a database key; Barcode is not SKU; Supplier is not necessarily Manufacturer. Quantity and low-stock threshold have different meanings. The sample includes multiple product categories and status values.
- Current mapper gap: no barcode, supplier, stock quantity, reorder threshold, restock date, weight, dimensions, price, or status fields.

### 24. MedCure drug inventory sample

- Source: https://github.com/KurisuuChan/MedCure_Official/blob/0f462dfc4fa77983d358efc25302c4f13782d84c/public/sample_drug_inventory.csv
- Type: pharmacy/drug inventory catalog
- Delimiter: comma
- Header: `product_name,generic_name,brand,category,dosage_form,dosage_strength,unit,price,quantity,reorder_level,expiry_date,supplier,description,barcode,sku`
- Mapping observations: Product name, SKU, and category are explicit. Generic name, brand, and supplier are distinct attributes; supplier must not be inferred as manufacturer. Dosage form/strength, expiry date, barcode, and inventory quantity carry domain-specific meaning.
- Current mapper gap: no generic name, dosage, expiry, barcode, inventory, supplier, or unit fields. This is a specialized inventory/product schema, not evidence for mapping medicine attributes into existing generic fields.

### 25. Brelinx inventory sample

- Source: https://github.com/Uwami-Mgxekwa/Brelinx-Inventory/blob/540cdad9b24485514d320221f337a329f1bbd1c1/sample_inventory.csv
- Type: general stock and supplier inventory
- Delimiter: comma
- Header: `name,sku,category,price,cost,quantity,min_stock,max_stock,supplier,barcode,description`
- Mapping observations: Name, SKU, and category are explicit. Supplier and barcode remain separate from manufacturer and SKU. Cost and price are different monetary measures; quantity, min_stock, and max_stock are different inventory measures.
- Current mapper gap: no cost, price, stock bounds, supplier, or barcode fields.

### 26. Steelite Utopia scraped catalog

- Source: https://github.com/Aru-gxtx/Web-Scraping-Test/blob/3565764b4a2e632626dca538547db86419d1e4da/steelite/utopia_products.csv
- Type: hospitality/tableware scraped product catalog
- Delimiter: comma
- Header: `name,item_sku,model_number,manufacturer,image_link,overview,material,color,pattern,length,width,height,volume_capacity,diameter,country_of_origin,upc_barcode,ean_code,hazmat,oversize,marketplace_uom,product_url`
- Mapping observations: Name and item_sku are explicit. `model_number` is distinct from item_sku and is frequently `N/A`; it should not be automatically treated as an MPN. More seriously, the sampled `manufacturer` values repeat the item SKU rather than a manufacturer name, so the header label alone does not guarantee semantically valid data. UPC and EAN remain separate identifiers.
- Current mapper gap: material, dimensions, country of origin, barcode, images, product URL, and handling flags are not represented. Sample values show why header-only mapping confidence is insufficient.

### 27. Steelite/Wasserstrom scraped catalog

- Source: https://github.com/Aru-gxtx/Web-Scraping-Test/blob/3565764b4a2e632626dca538547db86419d1e4da/steelite/wasserstrom_products.csv
- Type: hospitality/tableware distributor catalog
- Delimiter: comma
- Header: `name,item_sku,model_number,manufacturer,image_link,overview,material,color,pattern,length,width,height,volume_capacity,diameter,country_of_origin,upc_barcode,ean_code,hazmat,oversize,marketplace_uom,product_url`
- Mapping observations: this is a separate file from the same repository and shares the Utopia schema, so it is an individually inspected file but not independent evidence for a new schema family. `item_sku` and `model_number` are separate. Manufacturer values again appear identical to item SKUs, and many fields use `N/A`. Quoted product names/descriptions contain embedded quotes and commas, which must be parsed without shifting columns.
- Current mapper gap: same extended hospitality attributes as dataset 26. Keep this as a parser/value-quality test fixture, not a source for new manufacturer/MPN aliases.

### 28. WooCommerce Pawsome product export

- Source: https://github.com/madrasthemes/assets/blob/6cda2aee8f0dc00386f3d9a76c70d0df6073a3c2/data/pawsome/products.csv
- Type: WooCommerce product import/export
- Delimiter: comma
- Header: wide WooCommerce schema including `ID,Type,SKU,GTIN, UPC, EAN, or ISBN,Name,Published,Is featured?,Visibility in catalog,Short description,Description,...,Stock,...,Sale price,Regular price,Categories,Tags,...,Parent,Grouped products,...,Brands,Attribute 1 name,...`
- Mapping observations: the combined barcode header is a distinct product identifier field, not SKU/MPN. Product ID, product type, SKU, name, parent/grouped product references, categories, brands, and variation attributes have separate roles. The inspected rows contain empty SKU/barcode values, and the wide import has many optional/relationship columns.
- Current mapper gap: no product-type, parent/variant, barcode, publication, inventory, price, brand, taxonomy, or attribute support. The current seven-field product schema cannot represent this feed without an extended profile or preservation of source columns.

### 29. InsightMesh product inventory sample

- Source: https://github.com/murugadossp/insightmesh_backend/blob/23e5faa322fca6a69df3e5bf051ff383f05838a4/sample_data/product_inventory.csv
- Type: broad warehouse/product analytics inventory export
- Delimiter: comma
- Header: 45 fields including `product_id,product_name,category,subcategory,brand,supplier_id,cost_price,selling_price,discount_percentage,tax_rate,stock_quantity,reorder_level,minimum_order_quantity,lead_time_days,shelf_location,warehouse_location,...,batch_number,barcode,sku,condition,warranty_months,...,average_daily_demand,demand_variability,abc_classification`
- Mapping observations: Product name, category, and SKU are explicit. Product ID and supplier ID are source keys; brand is not manufacturer; subcategory is not necessarily the canonical category. Cost/selling price, inventory thresholds, batch, barcode, and derived analytics remain separate fields.
- Current mapper gap: inventory, commercial, traceability, warranty, product-attribute, and demand-planning fields require separate domain models or extended profiles. Do not treat precomputed metrics as raw product attributes.

### 30. Cosmic-Mart compact product feed

- Source: https://github.com/btbferguson/Cosmic-Mart/blob/f18b84ac90011cc35d2af4362f2022670e655b0e/src/data/cosmic_mart_products.csv
- Type: compact multi-category product feed with free-text specifications
- Delimiter: comma
- Header: `sku_id,product_name,product_category,specs`
- Mapping observations: product name and category are explicit. `sku_id` contains SKU-like values such as `SKU-1001`, but the suffix `_id` can also mean a database key; treat it as an AI/manual suggestion until the source contract confirms it. Specs are long free-text descriptions containing attributes and claims, not a manufacturer part number.
- Current mapper gap: no explicit manufacturer or MPN. A compact feed like this cannot satisfy the current general profile without missing-field handling or a different profile.

## Findings after 30 individually inspected files

1. CamelCase headers are a real gap: `ManufacturerPartNumber` normalizes to `manufacturerpartnumber`. Add that exact high-confidence alias rather than rewriting all header normalization in a way that could create collisions.
2. `model_number` is not a safe automatic MPN alias. Multiple inspected schemas keep model number separate from SKU, and sampled values may be placeholders or inconsistent. Remove it from automatic MPN mapping; it can remain an AI/manual candidate when the source values and supplier context support it.
3. Supplier SKU, internal SKU, barcode/GTIN, product ID, and MPN are separate identifier namespaces.
4. Manufacturer and supplier are not interchangeable. A supplier can distribute a product made by another company.
5. Inventory exports are not product-master exports. Repeated SKU across location/lot is often valid and requires a compound inventory key; don't run product-master duplicate logic on such rows.
6. Wide commerce exports carry variant relationships, publication state, multiple prices, stock, categories, brands, attributes, and identifiers. The current canonical schema is intentionally narrower and should not silently discard or misclassify these fields.
7. Some datasets contain placeholder or semantically inconsistent values despite plausible headers. A mapping assistant must inspect value distributions and consistency, not just match header strings.
8. The compact `sku_id` feed is a good candidate for contextual AI suggestion, not a global deterministic alias.

## Implementation update after the first 30 samples

- Added the normalized CamelCase header `manufacturerpartnumber` as a high-confidence alias for `part_number`.
- Removed `model_number` and `model_no` from automatic MPN mapping because the inspected evidence shows they are not reliably equivalent.
- Added regression tests for CamelCase MPN detection and for keeping `model_number` unmapped by default.
- The first CI run after the product_mpn test addition failed because the new test fixture contained literal backslash-n text instead of line breaks (67 passed, 1 failed). The fixture was corrected and the stricter alias tests were pushed afterward. The newest CI run is still in progress; do not treat it as green until it completes.
- No ML model is trained or active. The next useful ML/AI step is a candidate ranker that combines header semantics, sample-value patterns, related columns, and source context; deterministic validation and metric computation stay outside the model.


### 31. GTCatalog product/variant export

- Source: https://github.com/kukulis/gtcatalog/blob/d53601aaecf3bf6e448ef5401b55bb667f1a8fda/data/products.csv
- Type: multi-attribute product and variant export
- Delimiter: comma
- Header includes: `sku,brand,line,parent_sku,origin_country_code,vendor,manufacturer,type,purpose,measure,color,...,name,description,label,label_size,variant_name,tags,categories`
- Mapping observations: SKU, name, and manufacturer are separate. Brand and vendor are also present and must not be collapsed into manufacturer. `parent_sku` groups variants; it is not the row SKU. `line`, `type`, and `categories` carry different taxonomy meanings. Sample values appear placeholder-like, so this is stronger evidence for schema shape than for real-world value distributions.
- Current mapper gap: parent/variant relationships, vendor, line, origin, product attributes, labels, tags, and category hierarchies are not represented.

### 32. Shopify Online Store 2.0 export

- Source: https://github.com/mykola-havrylov/shopify-os2-sections-case/blob/1d4ea741328d4da750aa33c91b084bf8710aeabe/data/products.csv
- Type: Shopify product and variant export
- Delimiter: comma
- Header includes: `Title,URL handle,Description,Vendor,Product category,Type,Tags,Published on online store,Status,SKU,Variant Barcodes,Option1 name,Option1 value,...,Price,Compare-at price,Cost per item,...,Inventory quantity,...,Google Shopping / Manufacturer part number (MPN),...`
- Mapping observations: SKU is explicit. Product rows and variant rows share a handle; continuation rows can have a blank Title while retaining a distinct SKU and option value. This means row-level required-name validation without parent/variant context can incorrectly reject valid variant records. Vendor is not manufacturer. The MPN field is explicitly prefixed by Google Shopping and should be suggested as MPN only when that exact source header is present. Variant barcode, option names/values, and product-level metadata must remain distinct.
- Current mapper gap: parent-child inheritance, variants, option attributes, barcodes, vendor, multiple price bases, stock, publication state, and source-specific MPN headers are not modeled.

### 33. SmartHome device catalog

- Source: https://github.com/NationalAssociationOfRealtors/SmartHomeChecklist/blob/d1734e69c3b7853c2768e9f0a75f33123cd19518/sample-products.csv
- Type: smart-home device reference catalog
- Delimiter: comma
- Header: `device_class,device_name,hash,image,last_modified,manufacturer,support,website`
- Mapping observations: `device_name` is a clear product-name candidate; `manufacturer` is explicit. `hash` is a source record key, not a SKU. `device_class` is a taxonomy label, not necessarily the product category used by a supplier. There is no SKU or MPN.
- Current mapper gap: device_name alias, source record hash, device class, image, support URL, website, and update timestamp are not represented.

### 34. Mediescare legacy medicine catalog

- Source: https://github.com/ThemedEdits/mediescare-new/blob/90a894c43151f4a490ef0e12415195333abdf21f/docs/legacy-sample/products.csv
- Type: pharmacy medicine catalog
- Delimiter: comma
- Header: `Brand name,Generic name,Strength,Dosage form,Category,Manufacturer,Smallest unit,Pack unit,Units in one pack,MRP per pack,Trade price per pack,Barcode,SKU`
- Mapping observations: Brand name, Manufacturer, Category, and SKU are separate fields. Generic name and strength describe the active medicine; barcode is distinct from SKU. MRP and trade price are different commercial values. One row has a missing strength.
- Current mapper gap: generic name, dosage, pack hierarchy, MRP/trade price, and barcode require domain-specific fields. Brand name should not be treated as manufacturer.

### 35. PharmacyCentral medicine import sample

- Source: https://github.com/nielpattin/PharmacyCentral/blob/80a0c08628882fb834681520119cc15fbaf57ad1/data/import-samples/products.csv
- Type: pharmacy product import with regulatory and clinical metadata
- Delimiter: comma
- Header: `sku,name,category,manufacturer,genericName,activeIngredient,strength,dosageForm,packageDescription,unitName,unitPrice,barcode,registrationNumber,prescriptionRequired,imageUrl,status,effectiveFrom,indications`
- Mapping observations: SKU, name, category, and manufacturer are explicit. Generic name, active ingredient, strength, dosage form, registration number, prescription flag, and indications are distinct fields. Barcode is not SKU. The sample contains multilingual product names/descriptions and long quoted indications.
- Current mapper gap: medicine-specific identifiers and attributes, regulatory state, pricing, image, and effective dates are outside the current product schema.

### 36. BrightSky scraped medical supply catalog

- Source: https://github.com/Aaron199191/brightsky-scraper/blob/1bfbb538782ae7dfae6fc9ea2b90c0fd2ac88600/products.csv
- Type: scraped medical supplies catalog with embedded JSON attributes
- Delimiter: comma
- Header: `sku,name,url,price,regular_price,sale_price,availability,categories,short_description,description,image_url,gallery_images,attributes`
- Mapping observations: many top-level SKU and name cells are blank. The `attributes` column contains a quoted JSON object with nested `Product Number`, `Manufacturer Number`, `Manufacturer`, `Brand`, `Category`, and `title` values. Product Number and Manufacturer Number are distinct identifiers. The actual product name/manufacturer/MPN are not reliably available as top-level columns. This is a strong example for structured-cell extraction and AI-assisted mapping suggestions, but values must be parsed and reviewed before mapping.
- Current mapper gap: JSON-in-cell parsing, nested attribute selection, source URL, multiple price fields, stock status, image galleries, and distinct product/manufacturer identifiers are unsupported.

### 37. Snapdragon development-board parts catalog

- Source: https://github.com/ThyFriendlyFox/via/blob/b14e84c4825c93fe2f7b3dd0b4dd0a7b13667c43/examples/snapdragon-dev-board/parts/catalog.csv
- Type: electronics component BOM/parts sourcing catalog
- Delimiter: comma
- Header: `Value,Footprint,Qty,Manufacturer,MPN,Supplier,SKU,Pack,Breaks,Stock,Checked,URL,Note`
- Mapping observations: Manufacturer, MPN, Supplier, and SKU are explicitly separate. MPN is the manufacturer's identifier; SKU is the distributor-specific ordering code; Supplier is the source. `Value` is an electrical component value (e.g. 10k, 0.33), not product name. `Footprint` describes the PCB package, not category. `Qty`, pack breaks, stock, and pricing notes are procurement data.
- Current mapper gap: a distinct supplier SKU, BOM quantity, footprint, electrical value, pack pricing, stock, checked date, and sourcing URL are needed for this domain.

### 38. ShelfReady Seiko watch catalog fixture

- Source: https://github.com/jplogix/shelfReady/blob/41c8435cb34a836d1c9fd7eb752f3d3b9d892f8c/fixtures/seiko_demo_catalog.csv
- Type: watch product master and validation fixture
- Delimiter: comma
- Header: `sku,title,description,brand,color,category,product_type,price,currency,stock,image_filename,model,mpn,case_diameter,case_thickness,lug_to_lug,lug_width,caliber,movement_type,power_reserve,case_material,crystal,bracelet_material,water_resistance,weight,collection,demo_scenario`
- Mapping observations: SKU, title, category, model, and MPN are distinct. MPN is explicitly named, but some rows have no MPN. Brand casing varies (`Seiko` vs `SEIKO`); title is missing on a row; image files are missing or mismatched to variants; one row has conflicting case-diameter data; one row is explicitly marked ambiguous. This is a valuable row-level data quality fixture.
- Current mapper gap: currency, image, stock, model, MPN, watch specifications, collection, and variant-specific media are not in the canonical schema.

### 39. TS-System apparel inventory export

- Source: https://github.com/hp2025-final/TS-System/blob/46961d86ed448d6eb7571a28bd03bac8fe249f0e/080825-Inventory.csv
- Type: apparel collection/size inventory
- Delimiter: comma
- Header: `BarCode,Product Name,SKU,Collection,SIZE,Sale Price,Cost Price,Collection Description,Collection Discount,Tax Percentage,STATUS`
- Mapping observations: Barcode, Product Name, and SKU are separate. Collection groups styles; SIZE is a variant attribute. The same SKU is repeated across multiple sizes and some rows are repeated exactly, so SKU uniqueness cannot be assumed at variant-row level. Sale Price and Cost Price are separate; values include quoted thousands separators and whitespace.
- Current mapper gap: variant groups, size, collection, barcode, sale/cost prices, discounts, tax, and status require an apparel/inventory profile.

### 40. Cosmic-Mart inventory and performance feed

- Source: https://github.com/btbferguson/Cosmic-Mart/blob/f18b84ac90011cc35d2af4362f2022670e655b0e/src/data/cosmic_mart_inventory.csv
- Type: inventory, sales velocity, and listing-risk feed
- Delimiter: comma
- Header: `sku_id,product_name,product_category,current_stock,sales_velocity_weekly,days_of_supply,season_relevance,our_price,competitor_price,return_rate_pct,notes`
- Mapping observations: Product name and category are explicit. `sku_id` contains SKU-shaped values but remains source-specific until its contract is confirmed. Current stock, weekly velocity, days of supply, season, our price, competitor price, return rate, and free-text notes are operational/analytical fields, not product master attributes. The notes contain qualitative assertions that must not be converted into validated metrics without evidence.
- Current mapper gap: stock, velocity, seasonality, competitive pricing, return metrics, and issue notes belong to an inventory/performance layer separate from catalog identity.

## Findings after 40 individually inspected files

1. Product variants are now a major confirmed gap. Shopify and apparel exports legitimately have multiple rows per parent product, blank repeated parent-level titles, and repeated SKUs across size/variant rows. Product-master duplicate rules must not be applied blindly to variant or inventory feeds.
2. Structured data can be hidden inside JSON-valued cells. BrightSky stores product number, manufacturer number, manufacturer, brand, category, and title inside an `attributes` cell while top-level fields are blank. AI-assisted extraction can help propose nested mappings, but extraction must be deterministic and reviewable.
3. Explicit `Manufacturer Number`, `Manufacturer Part Number`, `MPN`, and integration-qualified MPN fields are strong MPN candidates. `Product Number`, `model`, `SKU`, and `Supplier SKU` remain distinct identifiers.
4. Supplier, vendor, brand, and manufacturer appear together in multiple exports and are not synonyms. Preserve their source semantics.
5. Domain-specific feeds (medicine, electronic components, watches, apparel, smart-home devices) contain required attributes that do not fit the current generic product schema. Add profiles/extensions rather than forcing them into unrelated canonical fields.
6. Source values can be more informative than names: blank top-level values, placeholder manufacturers, missing titles, invalid or absent barcodes, and mismatched variant images all require value-aware checks.
7. AI should propose candidate mappings and explain evidence; deterministic parsing, schema checks, duplicate rules, and metrics should remain authoritative. The current 40 inspected files are a discovery corpus, not enough to claim model training quality.
