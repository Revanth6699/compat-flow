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


## Implementation update after the first 40 samples

- Added `device_name` as a high-confidence product-name alias based on the smart-home catalog's explicit field.
- Added `manufacturer_number` and the exact normalized Shopify field `google_shopping_manufacturer_part_number_mpn` as MPN candidates because the source labels explicitly identify manufacturer part numbers.
- Added regression tests for all three aliases.
- CI run 43558312383 completed successfully after the newline fixture correction: backend and frontend jobs passed. The newer alias changes are in CI run 43558661844 and have not completed yet.
- The ML/AI direction remains a mapping assistant, not an automated validator: inspect header meaning, value shapes, related columns, and source context; rank suggestions with evidence; require confirmation for ambiguous mappings. Deterministic validation and metric computation remain authoritative.


### 41. BuildWithBharat multi-source product extraction export

- Source: https://github.com/Atul-Kumar29/buildwithbharat/blob/49e4c35e55df1e1e4bc91f1000655691a9723653/backend/data/output/products.csv
- Type: manufacturer/seller product extraction and enrichment feed
- Delimiter: comma
- Header: `product_name,brand,model_number,source_type,seller_name,price,currency,product_url,image_url,specifications,scraped_at,sku,mpn,gtin,error`
- Mapping observations: SKU, MPN, and GTIN have separate top-level columns. Manufacturer and seller records are distinguished by `source_type`; `seller_name` must not be treated as manufacturer. The `specifications` cell is JSON containing nested raw/normalized values. Some top-level SKU/MPN/GTIN fields are blank even when identifiers appear inside the JSON attributes.
- Current mapper gap: nested JSON extraction, source provenance, seller identity, GTIN, currency, and multi-source reconciliation are unsupported. Do not use model_number as MPN.

### 42. Instagram product publishing feed

- Source: https://github.com/Hari99-ai/software-assigment/blob/2da03b4dea86697898c67c862be79f8faac36a2e/instagram-automation/products.csv
- Type: product content and social publishing workflow feed
- Delimiter: comma
- Header: `product_id,product_name,category,description,features,price,product_image_url,publication_status,scheduled_date,generated_caption,published_post_url,error_message,publication_timestamp`
- Mapping observations: `product_id` values such as WP001 are workflow record IDs, not proven supplier SKUs. Product model/SKU appears embedded in free-text `features` (for example `Model / SKU: 111192`). Product name and category are explicit. Scheduled dates are future test values, not inventory or availability evidence.
- Current mapper gap: no social publication state, scheduled content, product image, or embedded feature extraction. Do not map product_id to SKU or the full features field to MPN.

### 43. Pioneer industrial catalog demo

- Source: https://github.com/My-Catalyst-Innovations/pioneer-industrial-catalog-demo/blob/098a0ae71659019b95a9f576037a5cca0cc6a3cd/data/demo_products.csv
- Type: industrial distributor catalog
- Delimiter: comma
- Header: `product_id,SKU / Pioneer part number,manufacturer,manufacturer_part_number,product_name,category,subcategory,description,specs,unit_of_measure,quantity_in_stock,reorder_point,price,customer_specific_price,image_ref,lead_time,warehouse_location,is_icc_supply,tags,safety_stock_status`
- Mapping observations: Product ID, Pioneer SKU/part number, manufacturer, and manufacturer part number are distinct fields even when the sample values happen to match. Category and subcategory are separate. Price and customer-specific price are separate. Quantity, reorder point, warehouse, lead time, and supply flags are operational data.
- Current mapper gap: the compound SKU/Pioneer part number header needs explicit manual or source-specific mapping; customer pricing, unit, stock, reorder point, lead time, and warehouse need an industrial inventory profile.

### 44. Aïcha semicolon-delimited product extraction record

- Source: https://github.com/JusteOgodja/Stage-Redmac-Consulting-Docs/blob/6b2b982d96e12bb9dc4bbde80236eafbfac51796/Scraping/07_Campagne_Finale_Expert/results/aicha/products.csv
- Type: FMCG web extraction/provenance export
- Delimiter: semicolon
- Header: 60+ fields including `platform_name,product_name,product_url,product_id,sku,brand,seller_or_supplier,manufacturer,variant_name,main_category,sub_category,price,currency,availability,stock_status,barcode,ingredients,allergens,nutritional_information,field_provenance,data_completeness_score,extraction_status,record_hash,data_origin`
- Mapping observations: the inspected row represents a category/brand landing page rather than a specific SKU-level product. Many fields contain the literal French placeholder `Non disponible`; the record still reports a completeness score of 60.0. `field_provenance` is a JSON object and records the extraction strategy. This file is useful for testing semicolon parsing, placeholders, provenance, and distinction between a product page and a product record, but not for training SKU/MPN mapping.
- Current mapper gap: placeholder normalization, provenance, page-type classification, multilingual content, FMCG attributes, and extraction-status fields are absent.

### 45. Easy ACP sample product catalog

- Source: https://github.com/raft-2025-hackseoul/easy-acp/blob/949179a797df6285035806c2f9af627179382fa2/example-products.csv
- Type: general commerce product feed
- Delimiter: comma
- Header: `product_id,product_name,product_description,price_usd,stock_status,brand_name,category,main_image,product_url,upc_code,color,size,rating,review_count,weight_lb,manufacturer,warranty_months`
- Mapping observations: Product name, category, manufacturer, UPC, and brand are separate. `product_id` values resemble SKU strings (SKU001, SKU002) but the header explicitly says product_id and there is no separate SKU field. UPC is a separate identifier. Manufacturer and brand differ for some rows (e.g. a Hydro Flask brand item lists Helen of Troy as manufacturer).
- Current mapper gap: no product ID, UPC, stock status, USD price, images, reviews, warranty, color, size, or weight fields. Treat product_id as a candidate SKU only after source confirmation.

### 46. Auto Ontology Evaluation product dimension

- Source: https://github.com/arananet/auto-ontology-eval/blob/ca6e19792958b1d3e9392e3fab2a7bc12160a5dc/fixture/source_a/seeds/dim_product.csv
- Type: compact retail product dimension
- Delimiter: comma
- Header: `sku,product_name,brand,category,list_price`
- Mapping observations: SKU, product name, category, and brand are explicit. No manufacturer field is present. Brand must not be automatically promoted to manufacturer. This is a compact fixture useful for testing incomplete general profiles.
- Current mapper gap: no manufacturer, part number, or profile-specific missing-field strategy.

### 47. FEC Sales Analysis Power BI product dimension

- Source: https://github.com/skx56/fec-sales-analysis/blob/5b09a7502e660ce6e7d331315307b0582964ef09/data/powerbi/dim_product.csv
- Type: retail data-warehouse product dimension
- Delimiter: comma
- Header: `product_id,sku,product_name,category,subcategory,brand_type,uom,standard_cost,list_price`
- Mapping observations: product_id and SKU are separate. Category and subcategory are separate. `brand_type` values such as Branded/Private Label describe a classification, not a brand name or manufacturer. Standard cost and list price are distinct measures.
- Current mapper gap: no product surrogate ID, subcategory, unit of measure, cost, list price, or branded/private-label classification.

### 48. Magic Store product dimension fixture

- Source: https://github.com/shr-eddie/magic_store/blob/790e6f5ab1e59c8e9fa605e41363be4522c18eca/data/dim_product.csv
- Type: compact product dimension with explicit brand/manufacturer split
- Delimiter: comma
- Header: `product_id,product_name,list_price,cost,weight,category,sub_category,manufacturer,brand,sku`
- Mapping observations: product ID, product name, SKU, manufacturer, and brand are separate. Category and sub_category are separate. List price and cost are distinct. The dataset is fictional/demo content, so it supports schema semantics but not realistic value-distribution learning.
- Current mapper gap: no product ID, subcategory, list price, cost, or weight fields. This file further confirms that brand and manufacturer cannot be globally merged.

### 49. E-commerce data warehouse product dimension

- Source: https://github.com/shivamdubey2310/E-commerce_data_warehouse/blob/d829a77589b998ecea56d61fd92b1d7de6c10038/data/DimProduct.csv
- Type: broad retail/warehouse product dimension
- Delimiter: comma
- Header: `product_key,sku_number,product_name,brand_name,subcategory_name,category_name,department_name,package_type,package_size,weight,shelf_life_days,storage_requirement`
- Mapping observations: `sku_number` is explicitly the SKU field; `product_key` is a warehouse surrogate key. Brand, subcategory, category, and department are separate dimensions. Package type/size, shelf life, and storage requirement are attributes. Sample product names and weight values appear synthetic/inconsistent, so don't use them as realistic value-distribution ground truth.
- Current mapper gap: recognize `sku_number`; warehouse key, brand, category hierarchy, packaging, shelf life, and storage requirements need separate fields.

### 50. FoodMart reduced product dimension

- Source: https://github.com/DAINTINESS-Group/DelianCubeEngine/blob/4f9c86a6d72ab176aba396c1147f51812c7ce719/InputFiles/foodmart_reduced/Data/product.csv
- Type: FoodMart-style grocery/retail product dimension
- Delimiter: comma
- Header: `product_id,product_class_id,brand_name,product_name,SKU,SRP,gross_weight,net_weight,recyclable_package,low_fat,units_per_case,cases_per_pallet,shelf_width,shelf_height,shelf_depth,product_subcategory,product_category,product_department,product_family,All`
- Mapping observations: Product ID and product class ID are surrogate/foreign keys; SKU is a distinct business identifier. Brand, product name, category, subcategory, department, and family are separate. SRP is suggested retail price; gross/net weight, case quantities, dimensions, and package/food flags are separate attributes. Do not map product_class_id to category or SRP to generic cost.
- Current mapper gap: grocery-specific packaging, hierarchy, nutrition/package flags, SRP, weights, dimensions, and case/pallet quantities are outside the current schema.

## Findings after 50 individually inspected files

1. SKU evidence is stronger when the header is explicit (`sku`, `sku_number`) than when the value merely looks like a SKU under `product_id`. Product IDs and warehouse surrogate keys remain separate.
2. Brand and manufacturer repeatedly appear as distinct fields, including rows where the brand is Sony/Hydro Flask while the manufacturer is a different legal company. Remove brand/brand_name from automatic manufacturer mapping; manual confirmation remains available.
3. Descriptions and short descriptions are not product names. Remove them from automatic name mapping; do not satisfy a required product name with a long descriptive paragraph.
4. Product variants, parent groups, supplier offers, social publishing records, warehouse dimensions, and inventory performance require different record types/profiles. The single generic product profile cannot safely absorb all of them.
5. Semicolon-delimited multilingual extraction files may contain placeholders such as `Non disponible`, provenance JSON, and category-page records without an actual SKU. Parsing successfully is not the same as having a valid product record.
6. Nested JSON and free-text fields sometimes contain identifiers that are absent from top-level columns. AI can suggest extracting these fields, but must show the source path and exact value and require confirmation.
7. Warehouse dimension tables contain surrogate keys, business SKUs, and foreign keys together. A model must not map a key to SKU solely because its values resemble SKU strings.
8. Synthetic/demo datasets are useful for schema and edge-case discovery but should be tagged and excluded or separately weighted in any training/evaluation corpus.


## Implementation update after the first 50 samples

- Added `sku_number` and the exact observed `SKU / Pioneer part number` header as SKU aliases.
- Removed `brand` and `brand_name` from automatic manufacturer mapping. Dataset 48 explicitly carries both columns, and dataset 45 shows that brand and manufacturer can be different legal entities.
- Removed `description` and `short_description` from automatic product-name mapping. A description must not silently become a product title.
- Added normalization for common unavailable markers (`N/A`, `not available`, `Non disponible`, `null`, and dash placeholders) so placeholder text is not counted as a populated required value.
- Added regression tests for the new SKU aliases, brand/description safety, and placeholder handling.
- CI run 43558661844 passed completely for the previous alias batch. The latest changes from commits 04846d2 and 201ee42 are in a new CI run and remain unverified until that run completes.
- No ML model has been trained or connected. The AI design is being separated from deterministic validation; see `docs/column-mapping-ai-design.md`.


### 51. PairSight sandbox product identity dataset

- Source: https://github.com/naisxx/pairsight/blob/a46525f15ff64ebe626ae992496980008a7c20f9/prisma/demo/sandbox-products.csv
- Type: product identity/variant matching benchmark
- Delimiter: comma
- Header: `record_id,product_name,brand,manufacturer,gtin,mpn,sku,model_number,category,color,size`
- Mapping observations: record_id, SKU, GTIN, MPN, model number, brand, and manufacturer are separate fields. The same product name appears across size/color variants with different GTIN/SKU values; manufacturer and MPN are often blank. Product-name casing varies across records. This is strong evidence for variant identity and identifier separation, though the synthetic names/values should be tagged as benchmark data.
- Current mapper gap: record ID, GTIN, model, color, size, and product-variant grouping are outside the current canonical model.

### 52. Tailwagg product dimension

- Source: https://github.com/PDRWeb/tailwagg/blob/dd45342b769e2ba7674fb929f5a1bc18d0557447/data/raw/dim_product.csv
- Type: pet retail product dimension
- Delimiter: comma
- Header: `product_id,sku,name,category_id,brand_id,is_active,attributes,created_at,discontinued_at`
- Mapping observations: product_id and SKU are distinct. Name is explicit. The columns called category_id and brand_id contain text-like values in the sample, but the names still imply references rather than canonical labels; do not map them automatically. The attributes cell is a Python-dict-like string using single quotes, not valid JSON, so a JSON-only extractor will fail. Active/discontinued dates are lifecycle attributes.
- Current mapper gap: category/brand references, lifecycle dates, and safe parsing of non-JSON structured attribute strings are unsupported. Do not pass Python literal strings to eval.

### 53. Novexa home analytics product dimension

- Source: https://github.com/mmoudoulaud-cyber/novexa-home-analytics/blob/000e38bf83497662d12bc1636102e2d694c81c7f/data/raw/Dim_Product.csv
- Type: home retail data-warehouse product dimension
- Delimiter: comma
- Header: `Product_ID,SKU,Product_Name,Brand,Supplier_ID,Category,Subcategory,Price_Segment,Unit_Cost,Unit_Price,Base_Margin_Rate,Launch_Date,Product_Status`
- Mapping observations: Product ID, SKU, product name, brand, supplier ID, category, and subcategory are distinct. Brand is not manufacturer; supplier_id is a foreign key. Unit cost, unit price, and base margin are separate financial measures. Some category/subcategory combinations appear semantically mismatched in the synthetic sample.
- Current mapper gap: category hierarchy, supplier references, price segment, cost/price/margin, launch date, and product status are not represented.

### 54. LH Nautical product/variant dimension

- Source: https://github.com/LeoRam0s/lh-nautical/blob/b786421ac3756b26be8ddf2acfefdc9d7ab4deb5/data/2-lh_nautical_gold/dim_product.csv
- Type: marine equipment product/variant export
- Delimiter: comma
- Header: `product_variant_id,product_id,sku,barcode_ean,sale_price,cost_price,weight_kg,icms_rate,ipi_rate,is_active_variant,product_name,description,brand_id,category_id,ncm_code,unit_of_measure,is_active_product,category_name,slug,parent_category_id,is_active_category,brand_name,country,is_active_brand`
- Mapping observations: product_variant_id, product_id, and SKU are separate; several variant rows share a parent product name and product_id. Barcode/EAN values are represented as floating-point numbers with trailing .0, which risks losing leading zeros and exact identifier digits. Brand/category IDs coexist with brand/category labels. Sale price, cost price, taxes, NCM code, unit, and status fields are distinct.
- Current mapper gap: variant identity, exact barcode preservation, category/brand references, taxes, customs classification, and unit-of-measure fields need domain-aware support. Numeric barcode coercion must be flagged.

### 55. Tudzai Power BI product dimension fixture

- Source: https://github.com/Tudzai/powerbi-fpa-analytics-portfolio/blob/325b58155b8e4eb110d74d8b15e334cffa9fe044/Project%2004%20-%20Customer%20Funnel%20Conversion/bi_customer_funnel_conversion_dashboard/data/powerbi_template_compat/dim_product.csv
- Type: Power BI compatibility product dimension
- Delimiter: comma
- Header: UTF-8 BOM-prefixed `product_id,product_name,category,subcategory,brand,base_price,launch_date,unit_cost,active_flag`
- Mapping observations: product_id values resemble SKU strings (SKU_1001 etc.) but the header is explicitly product_id and no SKU field exists. Brand, category, and subcategory are separate. The BOM appears only at the beginning of the first header and must not prevent recognition. Base price, unit cost, and active flag are distinct.
- Current mapper gap: no surrogate product ID, subcategory, price/cost, launch date, or active-state fields. Do not infer SKU from product_id based on value pattern alone.

### 56. Supply Chain Analytics product dimension

- Source: https://github.com/amanydv09/Supply-Chain-Analytics-and-Business-Intelligence/blob/38b054ee0b615aa1c9bfedd2a402424eb252dae2/Dim_Product.csv
- Type: compact supply-chain product dimension
- Delimiter: comma
- Header: `Product_ID,Product_Name,Category,Brand,Unit_Cost`
- Mapping observations: product ID, product name, category, brand, and unit cost are explicit. No SKU, manufacturer, or MPN is provided. Sample names/brands contain obvious synthetic cross-brand/model combinations (for example, an Apple-branded Galaxy or Vivo-branded iPhone), so this is a useful data-quality anomaly fixture but not reliable semantic training data.
- Current mapper gap: no SKU, manufacturer, MPN, or unit-cost field. Brand must remain distinct from manufacturer.

### 57. Retail Trend Tracker product dimension

- Source: https://github.com/AnirudhHanda/retail_trend_tracker_infosys_winternship/blob/0f02a0a9c293026c9099ca84460f5ee94a756af1/retail_trend_tracker_data/dim_product.csv
- Type: retail analytics product dimension
- Delimiter: comma
- Header: `product_id,subcategory_id,brand_id,product_name,product_description,product_price,product_cost,product_weight,product_upc,product_sku,product_launch_date,is_active`
- Mapping observations: product_id, subcategory_id, brand_id, UPC, and SKU are separate. product_sku is a direct SKU candidate; product_upc is a barcode identifier and must not map to SKU or MPN. Brand/category references are IDs, not labels. Product description is separate from product name. UPC values are numeric-looking and some start with zero, so they must remain strings.
- Current mapper gap: UPC, surrogate/reference IDs, product price/cost/weight, launch date, active status, and subcategory hierarchy are unsupported.

### 58. Quick-commerce dark-store inventory test dataset

- Source: https://github.com/Cheeku29/AI-Inventory-Management-System/blob/2b08f278b438bd2245749c0ed88e101c2f11a6d6/frontend/public/sample_datasets/quick_commerce_darkstore_inventory.csv
- Type: store-level inventory and anomaly test fixture
- Delimiter: comma
- Header: `item_code,product_name,category,store_code,available_qty,expected_inventory,daily_demand,retail_price,cost_price,delivery_days,moq,pack_size,supplier_name,test_case_note`
- Mapping observations: item_code is an explicit operational item identifier and can be mapped to SKU only under a source-specific contract; supplier_name is not manufacturer. Available and expected inventory are separate. The sample deliberately contains zero/negative stock and mismatches between recorded and expected inventory. test_case_note contains prewritten anomaly labels and should not be treated as independently computed ground truth without verification.
- Current mapper gap: store location, stock reconciliation, daily demand, MOQ, pack size, supplier, and test annotations belong to an inventory profile, not the current product master.

### 59. SupplyGuard AI inventory sample

- Source: https://github.com/mohamednafrisnrs-source/supplyguard-ai/blob/3c90b37129cf5bf183631185d4fd04ae1c7ca7a3/src/data/inventory.csv
- Type: replenishment/safety-stock inventory feed
- Delimiter: comma
- Header: `sku,product_name,current_stock,average_daily_demand,lead_time_days,safety_stock,supplier`
- Mapping observations: SKU and product name are explicit. Current stock, average daily demand, lead time, and safety stock are separate inventory measures. Supplier is not manufacturer. The compact sample is useful for inventory schema discovery but cannot satisfy the current general product profile.
- Current mapper gap: inventory and replenishment fields require a separate inventory profile and validation rules.

### 60. AWS retail intelligence product master

- Source: https://github.com/aws-samples/sample-amazon-qbusiness-and-quicksight-for-retail-intelligence/blob/b6ed997d28a9531c3a47456f6fcbad45431a486d/csv/product_master.csv
- Type: retail product master with supplier and inventory measures
- Delimiter: comma
- Header: `product_id,sku,product_name,top_category,sub_category,brand,unit_price,unit_cost,current_stock,min_stock_level,max_stock_level,supplier,launch_date,is_active,margin`
- Mapping observations: Product ID and SKU are separate; product name and top/subcategory are separate. Brand and supplier are separate from manufacturer. Unit price, unit cost, stock bounds, and margin are distinct. The sample margin is consistent with a derived gross-margin percentage for the inspected rows, but the source value should still be recalculated from price/cost for validation rather than trusted. Some product names and SKU strings appear synthetic or malformed.
- Current mapper gap: top_category, subcategory, supplier, inventory bounds, unit price/cost, launch date, active status, and margin are outside the current canonical model.

## Findings after 60 individually inspected files

1. Product ID and SKU are separate even when product_id values look like SKUs. Do not infer identity from formatting alone.
2. Product variants are distinct records: parent product ID, variant ID, SKU, GTIN, size/color, and product name can have different cardinalities.
3. Numeric coercion of GTIN/EAN/UPC can corrupt identifiers through decimal suffixes, scientific notation, precision loss, or dropped leading zeros. Identifier columns must be preserved as strings and validated separately.
4. Brand, manufacturer, supplier, and seller are distinct roles. Do not auto-map one to another.
5. Structured attributes may be JSON or Python-literal-like strings. Never use eval; use a safe parser and require a recognized format before extracting fields.
6. Inventory fields such as available/current/expected stock, daily demand, safety stock, lead time, and MOQ require inventory-specific validation and metrics.
7. Data quality test fixtures sometimes contain prewritten issue labels. Treat those labels as test metadata, not as ground truth for model training or measured validation outcomes.
8. A product master with top_category and sub_category provides evidence for a top_category alias, but the hierarchy must be preserved separately when both fields exist.


### 61. Swaadhi hospital inventory product master

- Source: https://github.com/Swaadhi/hospital-inventory-intelligence/blob/eac8d86df2599ea36a1d72565b596d6a3bfd8c59/data/Product_master.csv
- Type: hospital procurement/inventory product master
- Delimiter: comma
- Header: `SKU,Product_Name,Category,Unit,Unit_Price_USD,Reorder_Point,Max_Stock,Lead_Time_Days,Safety_Stock,WHO_Essential`
- Mapping observations: SKU, product name, and category are explicit. Unit, price, reorder point, max stock, lead time, safety stock, and WHO essential flag are separate. There is no manufacturer or MPN field, so this file cannot satisfy the current general product profile.
- Current mapper gap: unit, USD price, stock bounds, replenishment, and essential-list classification require an inventory/procurement profile.

### 62. ZURU toy channel product master

- Source: https://github.com/Saurav-Kanegaonkar/ZURU-Toy-Channel-Data-Quality-Analysis-Pack/blob/05e16acb3cc905b7b33f1ed21a79b65e11243bd8/data/product_master.csv
- Type: compact toy product master fixture
- Delimiter: comma
- Header: `sku_id,product_name,category,unit_price`
- Mapping observations: `sku_id` contains SKU-shaped values and is explicitly named as an SKU identifier. Product name and category are explicit. No manufacturer, MPN, or separate product ID is supplied. This supports a sku_id alias but not a generic product_id alias.
- Current mapper gap: unit price and source ID are outside the canonical schema; manufacturer and MPN are absent.

### 63. Cinderhaven CPG item-setup master

- Source: https://github.com/lailarallc/item-setup-form-preflight/blob/9763a6389214fc0f8ab2026e61928aaa3c078b7e/public/sample/product_master.csv
- Type: consumer packaged goods retailer item-setup and GS1 data export
- Delimiter: comma
- Header: 40+ fields including `sku,product_name,product_line,subcategory,gtin14,upc,case_pack_qty,unit_weight_lbs,case_weight_lbs,msrp,serving_size,calories_per_serving,total_fat_g,sodium_mg,total_carb_g,protein_g,brand_owner,country_of_origin,product_description,category,wholesale_price,list_price,map_price,shelf_life_days,inner_pack_count,ti,hi,cases_per_layer,layers_per_pallet,pallet_weight_lb,active_retailers,oneworldsync_status,last_updated,updated_by`
- Mapping observations: SKU, GTIN-14, UPC, brand owner, and category are distinct. GTIN/UPC values have leading zeros and must remain strings. Brand owner is not automatically a legal manufacturer. MSRP, wholesale, list, and MAP prices are separate. Nutrition, case/pallet logistics, retailer distribution, and GS1 registration state are specialized attributes. Some dimension and case-weight fields are blank.
- Current mapper gap: GS1 identifiers, nutrition, price types, packaging, palletization, retailer distribution, ownership, and item-setup status need a CPG profile.

### 64. SwiftOps India procurement product master

- Source: https://github.com/Naseem-Naaz/SwiftOps/blob/a1517872cf9805da0c8d6b076260b15806233d9c/Product_Master.csv
- Type: Indian multi-category procurement and inventory product master
- Delimiter: comma
- Header: `Product_ID,SKU_Code,Product_Category,Sub_Category,Product_Name,Brand,Procurement_Cost_INR,Selling_Price_INR,Target_Profit_Margin_%,Unit_Weight_Kg,Packaging_Type,ABC_Class,XYZ_Class,Reorder_Level,EOQ,Average_Monthly_Demand,Lead_Time_Days,Storage_Zone,Temperature_Controlled,Hazardous_Material,Damage_Risk,Demand_Seasonality,GST_%`
- Mapping observations: Product ID and SKU_Code are distinct. Product category, subcategory, name, and brand are separate. Procurement cost and selling price are INR-denominated measures; target margin, EOQ, demand, lead time, storage, hazard, and GST fields have separate semantics. No manufacturer or MPN is present.
- Current mapper gap: add the explicit SKU_Code alias; INR cost/price, margin, GST, ABC/XYZ, packaging, storage, and replenishment require separate fields.

### 65. Faraz Supply Chain Inventory Intelligence product master

- Source: https://github.com/Faraz-05/Supply-Chain-Inventory-Intelligence/blob/0061240a80967b5c144789d4fa9e65c6918bb3eb/data/processed/product_master.csv
- Type: compact multi-category product dimension
- Delimiter: comma
- Header: `SKU_ID,Product_Name,Brand,Category`
- Mapping observations: SKU_ID, product name, brand, and category are explicit. Some product names redundantly append the SKU value, while others do not. Brand is not manufacturer. No manufacturer or MPN is present. This independently supports treating an explicitly named SKU_ID as an SKU, while not promoting generic product_id to SKU.
- Current mapper gap: add SKU_ID alias; no manufacturer or MPN means this sample cannot satisfy the general profile.

### 66. Nobu dbt marketplace product master

- Source: https://github.com/NobuYoshi928/dbt_training/blob/402a76d5f80832be7414f6a45aa73720c68b6574/setup/sample_data/product_master.csv
- Type: multi-marketplace product identifier mapping
- Delimiter: comma
- Header: `product_id,product_name,category,amazon_sku,rakuten_item_code`
- Mapping observations: product_id, Amazon SKU, and Rakuten item code are three distinct identifier namespaces. The source does not provide a universal supplier SKU. Product name and category are explicit. Channel-specific identifiers should not be collapsed into the canonical SKU without a source contract.
- Current mapper gap: marketplace-specific identifiers and cross-channel product mappings are not represented.

### 67. Indigo manufacturing cost-analysis product master

- Source: https://github.com/Indigo-data/Manufacturing_Cost_Analysis/blob/f15282dbe25b95058e1e105819e23593767feb61/data/bronze/product_master.csv
- Type: manufacturing procurement and production-planning catalog
- Delimiter: comma
- Header: `sku,manufacturer,product_name,vendor,category,unit_of_measure,product_spec,case_pack,standard_unit_cost,pricing_basis,minimum_order_units,standard_lead_time_days,reorder_point_units,machine_line_count,operating_shifts_per_day,units_issued_per_line_shift,eligible_lines`
- Mapping observations: SKU, manufacturer, product name, vendor, and category are explicit. Manufacturer and vendor are distinct; the sample includes a manufacturer and a separate wholesale account. Product spec is a technical description, not MPN. Standard unit cost depends on pricing_basis, and production capacity fields are operational constraints.
- Current mapper gap: vendor, UOM, technical specification, case pack, cost basis, MOQ, lead time, reorder point, and production constraints need a manufacturing/procurement profile.

### 68. Nyayomat marketplace product import template

- Source: https://github.com/nyayomat/Nyayomat-Web_Production-Environment/blob/57cca58143c85bd634cca98e64451973602dfded/public/csv_templates/products.csv
- Type: marketplace product import template
- Delimiter: comma
- Header: `NAME,SLUG,ACTIVE,CATEGORIES,GTIN,GTIN_TYPE,MODEL_NUMBER,BRAND,MPN,DESCRIPTION,MANUFACTURER,ORIGIN_COUNTRY,HAS_VARIANT,REQUIRES_SHIPPING,MINIMUM_PRICE,MAXIMUM_PRICE,IMAGE_LINK,TAGS`
- Mapping observations: NAME, MANUFACTURER, MPN, GTIN, and BRAND are separate. GTIN_TYPE distinguishes UPC and EAN. MODEL_NUMBER is not MPN. CATEGORIES is plural and can contain multiple category values; it should not silently map to a single scalar category. The sample contains a misspelled boolean literal `FASLE`, missing MPN/manufacturer values, and price bounds.
- Current mapper gap: slug, GTIN/type, model number, origin, variant/shipping flags, min/max prices, images, and multi-valued categories/tags need marketplace support.

### 69. PriceMatch identifier comparison test products

- Source: https://github.com/muchecomanoj/pricemtch/blob/66e99d4641e1b6c34dc9fe20c83935276226a1ad/frontend/test-products.csv
- Type: product matching test fixture with marketplace identifiers
- Delimiter: comma
- Header: `sku,title,brand,category,condition,packQuantity,asin,upc,ean,gtin,mpn`
- Mapping observations: SKU, ASIN, UPC, EAN, GTIN, and MPN are separate identifiers. UPC/EAN/GTIN values include leading zeros; they must be preserved as strings. Title is a product-name candidate. Brand is distinct from manufacturer. Pack quantity and condition are attributes. The sample is intentionally compact and should be tagged as test data.
- Current mapper gap: ASIN, barcode/GTIN, condition, pack quantity, and product matching across identifier types are unsupported.

### 70. Perishable Stock Recovery product master

- Source: https://github.com/lamjahnavy/perishable--Stock-Recovery-Desk/blob/4d6154e26a06b23d238f417578d50f2b77062c62/data/C30_Dataset_CSVs/Product_Master.csv
- Type: cafe/grocery perishable product and demand-assumption master
- Delimiter: comma
- Header: `Product_ID,Business_Type,Product_Name,Category,Sell_Unit,Selling_Price_INR,Unit_Cost_INR,Unit_Contribution_Before_Overheads_INR,Shelf_Life_Days,Lead_Time_Days,Order_Pack_Size_Units,Demand_Penetration_Assumption,Weekend_Demand_Factor,Promotion_Uplift_Assumption,Stock_Input_Definition`
- Mapping observations: Product_ID is not explicitly SKU. Business_Type differentiates cafe-prepared products from grocery supplier-receipt products. Unit contribution is a derived measure and should be recomputed from selling price and unit cost. Shelf life, lead time, order pack, demand penetration, weekend factor, promotion uplift, and stock-input definition are separate business semantics.
- Current mapper gap: business type, sell unit, perishability, demand assumptions, promotion factors, and unit contribution require a perishable inventory/planning profile.

## Findings after 70 individually inspected files

1. Explicit SKU_ID and SKU_Code headers can be safely recognized as SKU candidates; generic product_id, record_id, marketplace IDs, and warehouse keys remain separate.
2. Marketplace-specific identifiers (Amazon SKU, Rakuten item code, ASIN) must remain in separate namespaces. A canonical SKU should not be fabricated by choosing one marketplace identifier.
3. GTIN-14, UPC, EAN, and MPN are independent identifiers. Leading zeros are meaningful; values must remain strings throughout ingestion and validation.
4. CPG/retail item setup includes brand ownership, GS1 registration, nutrition, pack hierarchies, pallet configuration, retailer distribution, and several price types. This cannot be compressed into the existing seven-field product schema.
5. Manufacturing procurement feeds distinguish manufacturer from vendor, and unit cost may depend on an explicit pricing basis.
6. Inventory and perishable planning feeds include derived contributions, demand assumptions, reorder rules, shelf life, and business-type-specific stock definitions. These are not product identity fields.
7. Templates can contain malformed boolean values and blank required identifiers. Structural import should preserve the source value and deterministic validation should report the exact malformed cell.


## Implementation update after the first 70 samples

- Added `sku_id` and `sku_code` as explicit SKU aliases, supported by separate observed product-master files. Generic `product_id` remains unmapped.
- Added tests for both aliases. The top_category and UTF-8 BOM regression tests passed in CI run 43559543754.
- CI run 43559764619 is checking the latest SKU ID/code alias tests. Backend container initialization and frontend setup have started; test and build steps are still pending.
- No barcode/GTIN aliases were added. UPC, EAN, GTIN-14, ASIN, and marketplace item identifiers remain distinct from SKU and MPN.
- The AI mapping design remains a controlled suggestion layer; no model or external AI provider is active.


### 71. Meridian industrial multi-warehouse inventory

- Source: https://github.com/prachi-shah-ds/DBS-/blob/e8cbe988833e0520142b187767a34d4dc5078fc7/SAMPLE_DATA/meridian_industrial_supply_data/inventory.csv
- Type: industrial SKU-by-warehouse inventory snapshot
- Delimiter: comma
- Header: `sku_id,product_name,category,warehouse_id,warehouse_name,current_stock,safety_stock,reorder_point,unit_cost,supplier_id,lead_time_days,last_restock_date,stockout_flag,obsolete_flag`
- Mapping observations: sku_id, product name, and category are explicit. The same SKU repeats across several warehouse rows, so it is not a duplicate product-master record. Warehouse ID/name, current stock, safety stock, reorder point, supplier ID, lead time, restock date, stockout and obsolete flags are separate inventory facts.
- Current mapper gap: inventory grain must include SKU + warehouse (and potentially snapshot date), not SKU alone. Supplier/warehouse IDs and replenishment metrics need an inventory profile.

### 72. Superlinked supplier product matching feed

- Source: https://github.com/superlinked/cookbook/blob/45369d88d617babb4c69352c29f03db85eb1aa1d/ecommerce/match_products_to_catalog/data/supplier_feed.csv
- Type: incoming supplier offers for product matching
- Delimiter: comma
- Header: `record_id,brand,title,gtin,model_number,color,size,pack_count,plug,material,x,y,w,h`
- Mapping observations: record_id is a feed-record ID, not SKU. Brand and title are explicit; GTIN/model_number are often blank. Color, size, pack count, plug, and material describe variant identity. Coordinates x/y/w/h refer to image tiles, not product dimensions. The feed deliberately includes near-duplicate titles (different cable lengths, charger plugs, salted vs unsalted cashews, sandal colors/sizes).
- Current mapper gap: supplier-offer record type, variant attributes, image provenance, and product-match outcomes (same product / variant / new) are separate from the current canonical product mapping.

### 73. Superlinked PIM product catalog

- Source: https://github.com/superlinked/cookbook/blob/45369d88d617babb4c69352c29f03db85eb1aa1d/ecommerce/match_products_to_catalog/data/pim_products.csv
- Type: product information management catalog with parent/variant structure
- Delimiter: comma
- Header: `record_id,parent_id,product_line,brand,title,gtin,model_number,color,size,pack_count,plug,material,x,y,w,h`
- Mapping observations: record_id, parent_id, and product_line are separate identity/grouping concepts. Brand and title are explicit. GTIN/model_number are identifiers, while color/size/pack_count/plug/material define variants. A single parent product can have multiple variant records. The example README documents exact GTIN/model matching and review for ambiguous near-matches.
- Current mapper gap: parent-child catalog relationships, variant attributes, GTIN/model identity and source-specific record IDs need an extended PIM model. Do not map record_id or parent_id to SKU.

### 74. Superlinked manufacturing parts catalog

- Source: https://github.com/superlinked/cookbook/blob/45369d88d617babb4c69352c29f03db85eb1aa1d/manufacturing/fill_work_order_from_notes/data/parts_catalog.csv
- Type: maintenance storeroom spare-parts catalog
- Delimiter: comma
- Header: `part_no,description,unit`
- Mapping observations: part_no is an explicit spare-part identifier and description is a part description; unit is the issue/stock unit. Values include gasket, bearing, seal, impeller, contactor, belt, coupling guard, and grease. No manufacturer or product SKU is supplied.
- Current mapper gap: a maintenance-parts profile needs part identity, unit, equipment compatibility, and storeroom context. Description is not automatically a product name.

### 75. Superlinked retail shelf-price product catalog

- Source: https://github.com/superlinked/cookbook/blob/45369d88d617babb4c69352c29f03db85eb1aa1d/retail/check_shelf_from_photo/data/catalog.csv
- Type: grocery UPC-to-product and shelf-price reference
- Delimiter: comma
- Header: `upc,brand,product,regular_price`
- Mapping observations: UPC is the product identifier; brand and product name are separate; regular_price is a shelf price. UPC values are fixed-width strings with leading zeros. Some product names are close or near-identical (multiple granola, cheesecake, beet juice and whipped-topping variants), and brand casing is inconsistent.
- Current mapper gap: UPC/GTIN, price, and brand fields are outside the current schema. The generic `product` header is a contextual name candidate here, but should not be a global alias without additional source evidence.

### 76. Pharmacy scraped product listing dataset

- Source: https://github.com/mouniksai/pharmacy-stockout-prediction/blob/737a0cb52b3f9d6878c3e6eec2db612783c215da/data/scraped_pharmacy_data_raw.csv
- Type: public pharmacy catalog extraction
- Delimiter: comma
- Header: `Medicine_Name,Category,Manufacturer,Pack_Size,Composition,Scraped_Price_INR,Scraped_Availability,Source_Portal,Source_URL`
- Mapping observations: Medicine_Name, Category, and Manufacturer are explicit. There is no SKU/MPN field. Pack size and composition distinguish strengths/formulations; scraped price and availability are time-sensitive observations, while source portal and URL are provenance. Product names and compositions contain variable whitespace.
- Current mapper gap: medicine-name alias, pack/composition, INR price, availability, source provenance, and scrape timestamp require a pharmacy profile.

### 77. Pharmacy stockout modeling raw dataset

- Source: https://github.com/mouniksai/pharmacy-stockout-prediction/blob/737a0cb52b3f9d6878c3e6eec2db612783c215da/data/pharmacy_stockout_raw.csv
- Type: pharmacy product plus replenishment/stockout modeling dataset
- Delimiter: comma
- Header: `Medicine_ID,Medicine_Name,Category,Manufacturer,Pack_Size,Composition,Unit_Price_INR,Criticality,Seasonal_Demand,Source_Portal,Source_URL,Current_Stock,Daily_Sales,Supplier_Lead_Time,Reorder_Level,Expiry_Date,Minimum_Order_Quantity,Storage_Condition,Stock_Status`
- Mapping observations: Medicine_ID is a source record ID, not a confirmed SKU. Manufacturer is explicit; pack size and composition identify formulation. Current stock, daily sales, supplier lead time, reorder level, expiry, MOQ, storage, and stock status are operational data. The source describes a modeled/expanded cohort; derived or simulated inventory fields must be tagged separately from scraped catalog facts.
- Current mapper gap: medicine identity and operational stockout features need separate source lineage and a pharmacy inventory profile.

### 78. StockWise sample inventory upload

- Source: https://github.com/kirtibhushanIIMBG/StockWise-AI/blob/80a15be7bbd56968c1a8bbfd1483abfd171790d1/data/sample_inventory.csv
- Type: Indian SMB inventory upload example
- Delimiter: comma
- Header: `sku,product_name,category,supplier,current_stock,avg_daily_demand,lead_time_days,unit_cost,selling_price,safety_stock,demand_std,incoming_stock,backorders`
- Mapping observations: SKU, product name, and category are explicit. Supplier is not manufacturer. Current stock, average daily demand, lead time, cost, selling price, safety stock, demand standard deviation, incoming stock, and backorders are distinct. Some demo rows have missing demand_std/safety_stock, zero stock, and zero demand; these are legitimate edge cases, not necessarily malformed product identity.
- Current mapper gap: inventory and demand planning need separate profile fields. Missing operational values must not be confused with missing product identity.

### 79. WR Bryan inventory accuracy product master

- Source: https://github.com/wrbryan/data-analysis-showcase/blob/e0bfd3846889207d1588745c6f4e4109ea89cacb/projects/01-inventory-accuracy-stockout-risk/data/sample/product_master.csv
- Type: industrial inventory accuracy product master
- Delimiter: comma
- Header: `sku,product_name,category,supplier,unit_cost,lead_time_days,reorder_point,safety_stock,annual_demand_estimate,active_flag`
- Mapping observations: SKU, product name, category, and supplier are explicit. Supplier is not manufacturer. Unit cost, lead time, reorder point, safety stock, annual demand estimate, and active flag are separate fields. This is synthetic sample data and should be tagged as such.
- Current mapper gap: supplier, cost, lead time, stock thresholds, demand estimate, and active state belong to an inventory profile.

### 80. WR Bryan multi-location inventory snapshot

- Source: https://github.com/wrbryan/data-analysis-showcase/blob/e0bfd3846889207d1588745c6f4e4109ea89cacb/projects/01-inventory-accuracy-stockout-risk/data/sample/inventory_snapshot.csv
- Type: dated physical-vs-system inventory snapshot
- Delimiter: comma
- Header: `snapshot_date,sku,location,zone,system_qty,physical_qty,unit_cost`
- Mapping observations: SKU is a reference to the product master. Snapshot date, location, and zone define the row grain; multiple rows per SKU are expected. system_qty and physical_qty are separate observed quantities, and discrepancies are meaningful. This file is not a product master and must not be validated with product-level duplicate rules.
- Current mapper gap: snapshot lineage, compound uniqueness, system/physical quantity reconciliation, location hierarchy, and inventory valuation are separate validation capabilities.

## Findings after 80 individually inspected files

1. Inventory row grain is now repeatedly confirmed as SKU + location/warehouse + snapshot date (and sometimes lot). Duplicate SKU rows are often valid.
2. Supplier feeds and PIM catalogs need matching/variant semantics: record IDs, parent IDs, product lines, GTIN/model numbers, and variant attributes are not interchangeable.
3. UPC/GTIN values with leading zeros must remain strings. Exact identifier matching should normalize to a defined canonical representation without numeric coercion.
4. Product description fields are not product names; the generic product header can only be a contextual AI/manual suggestion.
5. Pharmacy catalog facts and modeled inventory fields need separate provenance. Scraped price/availability, manufacturer, pack size and composition should not be mixed with synthetic or derived stockout metrics.
6. Product identity validation and inventory reconciliation are different product capabilities. Inventory profile rules need composite keys and deterministic reconciliation metrics.
7. The same-source PIM and supplier files provide a valuable paired matching benchmark, but their synthetic identifiers and attribute labels must be tagged; do not count correlated files as independent evidence for model generalization.


## Implementation update after the first 80 samples

- Added `medicine_name` as an explicit pharmacy-domain product-name alias, with a regression test.
- CI run 43559764619 passed for SKU ID/code alias tests. CI run 43559810602 passed the top_category and BOM changes.
- The medicine_name change is being checked in CI run 43560138904; backend and frontend jobs are running. No success is claimed until completion.
- No new generic aliases were added for `record_id`, `medicine_id`, `parent_id`, `warehouse_id`, `supplier_id`, `amazon_sku`, `rakuten_item_code`, or barcode fields.
- The audit now distinguishes product master, supplier feed, PIM parent/variant catalog, warehouse inventory, inventory snapshot, pharmacy catalog, and replenishment data. These need separate validation grains and profiles.


### 81. Amazon Honest Company scraped product listings

- Source: https://github.com/cordelldb/amazon-crawler-scrapy/blob/8983e2b47ac14dba1733ab62b4af0b3c1fa31c77/product_crawler/spiders/honest_products.csv
- Type: marketplace product listing scrape
- Delimiter: comma
- Header: `product_id,marketplace_id,product_title,title_desc,product_price,list_price,manufacturer,upc,model_name,product_dimensions,product_weight,customer_ratings,average_rating,listing_url,image_url,seller_name,seller_url`
- Mapping observations: product_id values are Amazon ASIN-like marketplace IDs, not supplier SKUs. Product title, manufacturer, UPC, model name, and seller are distinct. Seller_name is a marketplace seller, not manufacturer. Customer ratings are count-like strings with thousands separators, while average_rating is a separate rating value. Many UPC/model/manufacturer cells are blank.
- Current mapper gap: marketplace ID, UPC, model, seller, listing/image URLs, rating counts, and price types require a marketplace listing profile.

### 82. JeelPatel warehouse inventory stock feed

- Source: https://github.com/JeelPatel-045/etl-checker/blob/bc9aa491283acb097d87620d1bd1159051e884ca7/sample-data/inventory_stock.csv
- Type: multi-warehouse stock position
- Delimiter: comma
- Header: `sku,product_name,category,warehouse,quantity_on_hand,quantity_reserved,quantity_available,reorder_point,reorder_quantity,unit_cost,last_updated,supplier,lead_days`
- Mapping observations: SKU, product name, category, and warehouse are explicit. Quantity on hand, reserved, and available are distinct measures; available should reconcile to on_hand minus reserved. Supplier is not manufacturer. A row has blank quantity_on_hand while available is zero, which should be reported as missing source data rather than inferred.
- Current mapper gap: inventory grain, quantity reconciliation, reorder quantity, cost, supplier, and lead-time validation need an inventory profile.

### 83. FlowGrid Flipkart catalog template

- Source: https://github.com/adityapatil400/ADITYA-SGU-3rd/blob/4e362d5a2df5dc63f85974242b7b5dc9d3d33dd8/flowgrid_flipkart_100sku/templates/flipkart_product_catalog.csv
- Type: Flipkart listing/catalog template
- Delimiter: comma
- Header only: `sku_id,product_name,brand,category_id,pack_size_text,unit_of_measure,listing_price_inr,source_listing_url,source_capture_date,source_platform,price_snapshot_status,price_note,logistics_weight_kg,logistics_volume_l,weight_basis,logistics_specs_source,estimated_total_shelf_life_days,min_remaining_shelf_life_days,storage_class,catalog_data_status,data_origin`
- Mapping observations: the file has headers but no data rows. SKU_ID is explicitly an SKU candidate; category_id is a reference key, not category text. Listing price and logistics values include source/estimation metadata. Without rows, value formats, null rates, and referential validity cannot be assessed.
- Current mapper gap: source listing snapshots, estimated logistics values, category references, and data provenance are not represented.

### 84. Tower demo product catalog

- Source: https://github.com/tower/tower-demo/blob/ad67d13255ece2f973c5312e0d5c7099c64add56/data/product_catalog.csv
- Type: retail product catalog with size/color variants
- Delimiter: comma
- Header: `sku,product_name,category,subcategory,brand,unit_price,weight_kg,dimensions_cm,color,size,description,supplier_id,created_date,status`
- Mapping observations: SKU and product name are explicit. Category/subcategory, brand, and supplier ID are separate. The same product name appears in multiple rows with different sizes/colors and distinct SKUs; these are variants, not duplicates. Description is not product name.
- Current mapper gap: variant attributes, supplier references, price, weight/dimensions, created date, and lifecycle status need separate fields.

### 85. MarketMind Indonesian beauty catalog

- Source: https://github.com/zidanarsyad/marketmind/blob/e2fbc1bfe237f6323827a68b8c159e9344a4ea92/data/raw/product_catalog.csv
- Type: Indonesian skincare/beauty product catalog
- Delimiter: comma
- Header: `sku_id,brand,product_name,category,key_ingredient,size_ml,price_idr,launch_month,fragrance_free,spf,price_per_ml_idr,halal_certified,bpom_registered,rating_avg,review_count,units_sold_estimate`
- Mapping observations: SKU_ID, brand, product name, and category are explicit. Key ingredient, size, price, launch month, fragrance-free, SPF, halal certification, BPOM registration, ratings, reviews, and estimated units sold are distinct attributes. price_per_ml_idr is derived and should be recalculated from price and size. Brand is not manufacturer.
- Current mapper gap: beauty-specific ingredients, regulatory certification, size, IDR pricing, rating, review, and sales estimate fields require a beauty/marketplace profile.

### 86. AI Agent Workflow product catalog duplicate fixture

- Source: https://github.com/theonlyaks/ai_agent_workflow/blob/775cff619219a9a3ed43ede68c37404c31c0e07e/data/samples/product_catalog.csv
- Type: product deduplication and matching fixture
- Delimiter: comma
- Header: `sku,product_name,brand,category,color,size,material,price`
- Mapping observations: SKU, product name, brand, and category are explicit. The sample intentionally includes a duplicate-like SKU with lowercase and trailing whitespace (`sku-1001 `), near-identical names (Slim Fit Denim Jeans vs Slim-Fit Denim Jeans), same product/variant rows, and different materials. Normalization must be conservative: trim surrounding whitespace and compare case-insensitively for duplicate detection, but retain the original source value and distinguish true variants from duplicate records.
- Current mapper gap: normalized identifier comparisons, duplicate candidate explanations, and variant-aware matching are outside the current parser.

### 87. RAGOps Copilot knowledge-base product catalog

- Source: https://github.com/shivakhoshhal94/ragops-copilot/blob/fba3835f89b880e73f6b9e5230a6496f0a3469f8/data/knowledge_base/product_catalog.csv
- Type: compact retrieval knowledge-base product catalog
- Delimiter: comma
- Header: `sku,product_name,category,brand,price,currency,stock_quantity,main_image_url,description`
- Mapping observations: SKU, product name, category, and brand are explicit. Price and currency are separate; stock quantity and image URL are not identity fields. Brand is not manufacturer. This is a clean compact knowledge-base fixture but lacks manufacturer and MPN.
- Current mapper gap: currency, stock, image, and descriptive content are not represented in the current canonical model.

### 88. Vietnamese data-agent retail catalog

- Source: https://github.com/dauvannam1804/data-agent-demo/blob/fb128c33c4b0e00dc55923e4cf6e3944f400e465/data-code/sale_data/product_catalog.csv
- Type: Vietnamese multi-category retail product/sales catalog
- Delimiter: comma
- Header: `Product_Name,SKU,Category,Brand,Supplier,Cost_Price,Selling_Price,Profit_Margin_Percent,Stock_Quantity,Reorder_Level,Launch_Date,Warranty_Months,Avg_Rating,Total_Reviews`
- Mapping observations: Product name, SKU, category, brand, and supplier are separate. Brand and supplier are not manufacturer. Cost, selling price, and profit margin are distinct; margin should be recalculated from cost/selling price. Stock/reorder, launch date, warranty, rating, and review count are operational/commercial fields. Category values include Vietnamese text; parsing and validation must preserve Unicode.
- Current mapper gap: Unicode category values, supplier, price/margin, stock, warranty, ratings, and review count need an extended retail profile.

### 89. Power BI smart retail product catalog

- Source: https://github.com/1234-ad/powerbi-smart-retail-analytics-dashboard/blob/5821e81afe298e39e094ced6c8086d1aebde6192/data/product_catalog.csv
- Type: compact Power BI retail product dimension
- Delimiter: comma
- Header: `ProductID,ProductName,SKU,Category,SubCategory,Brand,UnitPrice,Cost,LaunchDate,Status,PriceTier`
- Mapping observations: ProductID and SKU are separate. ProductName, Category, SubCategory, and Brand are distinct. UnitPrice and Cost are separate; Status and PriceTier are classifications. No manufacturer/MPN is present.
- Current mapper gap: product ID, subcategory, unit price/cost, launch date, status, and price tier are outside the canonical schema.

### 90. GridScout laptop product knowledge catalog

- Source: https://github.com/juanmh10/gridscout/blob/9ab90929fa0c81b1897d17e20aeb5b7c30d9dc53/fixtures/product_knowledge/notebook_catalog.csv
- Type: enriched laptop product knowledge catalog
- Delimiter: comma
- Header: 45+ fields including `product_id,brand,family,series,model,full_name,manufacturer_code,sku,mpn,ean,gtin,aliases,cpu_brand,cpu_model,cpu_generation,ram_gb,ram_type,storage_gb,storage_type,gpu,screen_size_inches,screen_resolution,screen_type,wifi_standard,keyboard_type,operating_system,price_brl,condition,source,source_product_id,url,title_raw,model_raw,cpu_raw,screen_raw,wifi_raw,keyboard_raw,sources,collection_status,created_at,updated_at`
- Mapping observations: Product ID, brand, model, full name, manufacturer code, SKU, MPN, EAN, GTIN, source product ID, and aliases are all distinct. The sample has records where EAN/GTIN are literal `unknown`, and others contain numeric strings. Manufacturer_code is a code, not a manufacturer name. Full_name is the clearest product-name candidate; model and raw model are separate. The file also preserves source and raw extraction values, which is useful for provenance and AI-assisted extraction review.
- Current mapper gap: identifier registry, aliases, laptop specifications, condition, price/currency, raw extraction provenance, and source reconciliation require a specialized product-knowledge model.

## Findings after 90 individually inspected files

1. Marketplace product IDs such as ASIN and product_id are not canonical SKUs. Marketplace IDs, supplier SKUs, manufacturer codes, MPNs, GTIN/EAN/UPC, and source product IDs need separate identifier types.
2. Full-name/title fields can be stronger product-name candidates than model fields; model and manufacturer_code must not be mistaken for MPN.
3. SKU normalization should trim surrounding whitespace and compare case-insensitively for duplicate detection while preserving the original value for audit and display.
4. Duplicate detection needs separate outcomes for exact duplicate, normalization collision, same product variant, and possible near-match. Similar titles alone are insufficient.
5. Multi-currency prices and derived metrics must retain currency/formula context. Margins and price-per-unit fields should be recomputed from their source values.
6. Empty template files provide schema evidence only; they cannot support value-pattern confidence or data-quality claims.
7. Multilingual content and identifiers must be preserved exactly; normalization should target comparison keys, not rewrite source text.
