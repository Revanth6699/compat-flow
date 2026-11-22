from app.services.dataset_rules import profile_dataset_rules


def test_inventory_profile_reports_negative_and_unreconciled_quantities():
    result = profile_dataset_rules(
        ["sku", "quantity_on_hand", "quantity_reserved", "quantity_available"],
        [
            {"sku": "A", "quantity_on_hand": "10", "quantity_reserved": "2", "quantity_available": "8"},
            {"sku": "B", "quantity_on_hand": "-1", "quantity_reserved": "0", "quantity_available": "-2"},
        ],
    )
    assert result["dataset_type"] == "inventory"
    checks = {item["code"]: item for item in result["domain_checks"]}
    assert checks["NEGATIVE_INVENTORY_QUANTITY"]["issue_records"] == 1
    assert checks["INVENTORY_BALANCE_MISMATCH"]["issue_records"] == 1


def test_customer_profile_reports_malformed_emails_and_duplicate_ids():
    result = profile_dataset_rules(
        ["customer_id", "email"],
        [
            {"customer_id": "C1", "email": "valid@example.com"},
            {"customer_id": "C1", "email": "not-an-email"},
        ],
    )
    assert result["dataset_type"] == "customer records"
    checks = {item["code"]: item for item in result["domain_checks"]}
    assert checks["INVALID_EMAIL_FORMAT"]["issue_records"] == 1
    assert checks["DUPLICATE_CUSTOMER_IDENTIFIER"]["issue_records"] == 1


def test_orders_profile_detects_delivery_before_purchase():
    result = profile_dataset_rules(
        ["order_id", "order_purchase_timestamp", "order_delivered_customer_date"],
        [{
            "order_id": "O1",
            "order_purchase_timestamp": "2026-01-02T12:00:00",
            "order_delivered_customer_date": "2026-01-01T12:00:00",
        }],
    )
    assert result["dataset_type"] == "orders / transactions"
    check = next(item for item in result["domain_checks"] if item["code"] == "DELIVERY_BEFORE_PURCHASE")
    assert check["issue_records"] == 1
    assert check["severity"] == "critical"


def test_general_dataset_does_not_claim_domain_checks():
    result = profile_dataset_rules(["field_a", "field_b"], [{"field_a": "x", "field_b": "y"}])
    assert result["dataset_type"] == "general dataset"
    assert result["domain_checks"] == []
    assert result["domain_issues"] == []

def test_olist_unavailable_order_status_is_recognized():
    result = profile_dataset_rules(
        ["order_id", "order_status"],
        [
            {"order_id": "O1", "order_status": "unavailable"},
            {"order_id": "O2", "order_status": "delivered"},
            {"order_id": "O3", "order_status": "not_a_real_status"},
        ],
    )
    check = next(item for item in result["domain_checks"] if item["code"] == "UNRECOGNIZED_ORDER_STATUS")
    assert check["issue_records"] == 1
    assert "1 rows" in check["detail"]



def test_validation_catalog_shows_evaluated_and_not_applicable_rules_for_every_dataset():
    result = profile_dataset_rules(
        ["order_id", "order_status"],
        [{"order_id": "O1", "order_status": "unavailable"}],
    )
    rules = {item["code"]: item for item in result["validation_rules"]}
    assert rules["MISSING_VALUES"]["status"] == "evaluated"
    assert rules["EXACT_DUPLICATE_ROWS"]["status"] == "evaluated"
    assert rules["UNRECOGNIZED_ORDER_STATUS"]["status"] == "evaluated"
    assert rules["NEGATIVE_INVENTORY_QUANTITY"]["status"] == "not_applicable"
    assert rules["NEGATIVE_INVENTORY_QUANTITY"]["issue_records"] is None


def test_validation_catalog_marks_missing_required_columns_not_evaluated():
    result = profile_dataset_rules(
        ["quantity_on_hand"],
        [{"quantity_on_hand": "10"}],
    )
    rules = {item["code"]: item for item in result["validation_rules"]}
    assert rules["NEGATIVE_INVENTORY_QUANTITY"]["status"] == "evaluated"
    assert rules["INVENTORY_BALANCE_MISMATCH"]["status"] == "not_evaluated"
    assert rules["INVENTORY_BALANCE_MISMATCH"]["issue_records"] is None


def test_general_dataset_still_receives_structural_default_checks():
    result = profile_dataset_rules(["field_a"], [{"field_a": ""}, {"field_a": "x"}])
    rules = {item["code"]: item for item in result["validation_rules"]}
    assert rules["MISSING_VALUES"]["issue_records"] == 1
    assert rules["EXACT_DUPLICATE_ROWS"]["issue_records"] == 0
    assert all(
        item["status"] in {"evaluated", "not_applicable", "not_evaluated"}
        for item in result["validation_rules"]
    )



def test_product_catalog_defaults_check_missing_and_duplicate_seller_skus():
    result = profile_dataset_rules(
        ["sku", "name"],
        [
            {"sku": "A-1", "name": "Widget"},
            {"sku": "a-1", "name": "Widget duplicate"},
            {"sku": "", "name": "Missing SKU"},
        ],
    )
    rules = {item["code"]: item for item in result["validation_rules"]}
    assert result["dataset_type"] == "product catalog"
    assert rules["MISSING_PRODUCT_SKU"]["issue_records"] == 1
    assert rules["DUPLICATE_PRODUCT_SKU"]["issue_records"] == 1
    assert rules["DUPLICATE_PRODUCT_SKU"]["severity"] == "critical"


def test_supplier_offer_defaults_require_currency_for_priced_offers():
    result = profile_dataset_rules(
        ["supplier_sku", "unit_price", "currency"],
        [
            {"supplier_sku": "S1", "unit_price": "12.50", "currency": ""},
            {"supplier_sku": "S2", "unit_price": "8.00", "currency": "US"},
        ],
    )
    rules = {item["code"]: item for item in result["validation_rules"]}
    assert result["dataset_type"] == "supplier offers"
    assert rules["PRICE_WITHOUT_CURRENCY"]["issue_records"] == 1
    assert rules["INVALID_CURRENCY_FORMAT"]["issue_records"] == 1



def test_product_catalog_detects_missing_and_self_parent_references():
    result = profile_dataset_rules(
        ["product_id", "parent_product_id", "sku", "name"],
        [
            {"product_id": "P1", "parent_product_id": "", "sku": "A", "name": "Parent"},
            {"product_id": "P2", "parent_product_id": "MISSING", "sku": "B", "name": "Orphan"},
            {"product_id": "P3", "parent_product_id": "P3", "sku": "C", "name": "Self parent"},
        ],
    )
    rules = {item["code"]: item for item in result["validation_rules"]}
    assert rules["ORPHAN_PRODUCT_PARENT"]["issue_records"] == 1
    assert rules["SELF_REFERENCING_PRODUCT"]["issue_records"] == 1
    assert rules["ORPHAN_PRODUCT_PARENT"]["severity"] == "critical"


def test_product_catalog_validates_replacement_sku_references_case_insensitively():
    result = profile_dataset_rules(
        ["sku", "replacement_sku", "name"],
        [
            {"sku": "OLD-1", "replacement_sku": "new-1", "name": "Old"},
            {"sku": "NEW-1", "replacement_sku": "", "name": "New"},
            {"sku": "SELF-1", "replacement_sku": "self-1", "name": "Self"},
            {"sku": "BROKEN-1", "replacement_sku": "DOES-NOT-EXIST", "name": "Broken"},
        ],
    )
    rules = {item["code"]: item for item in result["validation_rules"]}
    assert rules["ORPHAN_REPLACEMENT_SKU"]["issue_records"] == 1
    assert rules["SELF_REPLACING_PRODUCT"]["issue_records"] == 1


def test_product_relationship_checks_are_not_evaluated_without_reference_columns():
    result = profile_dataset_rules(
        ["sku", "name"],
        [{"sku": "A-1", "name": "Widget"}],
    )
    rules = {item["code"]: item for item in result["validation_rules"]}
    assert rules["ORPHAN_PRODUCT_PARENT"]["status"] == "not_evaluated"
    assert rules["ORPHAN_PRODUCT_PARENT"]["issue_records"] is None
    assert rules["ORPHAN_REPLACEMENT_SKU"]["status"] == "not_evaluated"
    assert rules["ORPHAN_REPLACEMENT_SKU"]["issue_records"] is None

def test_olist_product_master_is_classified_without_mislabeling_product_id_as_sku():
    headers = [
        "product_id",
        "product_category_name",
        "product_name_lenght",
        "product_description_lenght",
        "product_photos_qty",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
    ]
    rows = [{
        "product_id": "P-001",
        "product_category_name": "perfumaria",
        "product_name_lenght": "40",
        "product_description_lenght": "287",
        "product_photos_qty": "1",
        "product_weight_g": "225",
        "product_length_cm": "16",
        "product_height_cm": "10",
        "product_width_cm": "14",
    }]
    result = profile_dataset_rules(headers, rows)
    rules = {item["code"]: item for item in result["validation_rules"]}

    assert result["dataset_type"] == "product catalog"
    # product_id is a source identity, not proof of a seller-assigned SKU.
    assert rules["MISSING_PRODUCT_SKU"]["status"] == "not_evaluated"
    assert rules["DUPLICATE_PRODUCT_SKU"]["status"] == "not_evaluated"
    assert rules["ORPHAN_PRODUCT_PARENT"]["status"] == "not_evaluated"
    assert rules["MISSING_SOURCE_PRODUCT_ID"]["status"] == "evaluated"
    assert rules["DUPLICATE_SOURCE_PRODUCT_ID"]["status"] == "evaluated"
    assert rules["MISSING_VALUES"]["status"] == "evaluated"


def test_product_id_alone_does_not_force_product_catalog_classification():
    result = profile_dataset_rules(["product_id", "created_at"], [
        {"product_id": "X1", "created_at": "2026-01-01"}
    ])
    assert result["dataset_type"] == "general dataset"

def test_product_source_identifier_checks_do_not_treat_ids_as_skus():
    result = profile_dataset_rules(
        ["product_id", "product_category_name", "product_weight_g"],
        [
            {"product_id": "P-1", "product_category_name": "tools", "product_weight_g": "10"},
            {"product_id": "p-1", "product_category_name": "tools", "product_weight_g": "12"},
            {"product_id": "", "product_category_name": "tools", "product_weight_g": "8"},
        ],
    )
    rules = {item["code"]: item for item in result["validation_rules"]}
    assert result["dataset_type"] == "product catalog"
    assert rules["MISSING_SOURCE_PRODUCT_ID"]["issue_records"] == 1
    assert rules["DUPLICATE_SOURCE_PRODUCT_ID"]["issue_records"] == 1
    assert rules["MISSING_PRODUCT_SKU"]["status"] == "not_evaluated"

def test_shopify_style_product_export_is_classified_from_variant_and_product_fields():
    headers = [
        "Handle", "Title", "Body (HTML)", "Vendor", "Type",
        "Variant SKU", "Variant Price", "Variant Barcode",
    ]
    result = profile_dataset_rules(headers, [{
        "Handle": "classic-shirt", "Title": "Classic Shirt",
        "Body (HTML)": "Cotton shirt", "Vendor": "Acme",
        "Type": "Apparel", "Variant SKU": "SHIRT-BLK-M",
        "Variant Price": "29.99", "Variant Barcode": "123456789012",
    }])
    assert result["dataset_type"] == "product catalog"


def test_woocommerce_style_export_is_classified_without_vendor_specific_filename():
    headers = ["ID", "Type", "SKU", "Name", "Published", "Regular price", "Categories", "Images"]
    result = profile_dataset_rules(headers, [{
        "ID": "100", "Type": "simple", "SKU": "MUG-01",
        "Name": "Coffee Mug", "Published": "1", "Regular price": "12.00",
        "Categories": "Kitchen", "Images": "https://example.invalid/mug.jpg",
    }])
    assert result["dataset_type"] == "product catalog"


def test_erp_item_master_export_is_classified_from_item_number_and_descriptors():
    headers = ["Item Number", "Material Description", "Product Group", "Gross Weight", "UOM"]
    result = profile_dataset_rules(headers, [{
        "Item Number": "MAT-100", "Material Description": "Steel fastener",
        "Product Group": "Fasteners", "Gross Weight": "0.25", "UOM": "KG",
    }])
    assert result["dataset_type"] == "product catalog"


def test_supplier_offer_schema_keeps_precedence_over_product_signals():
    result = profile_dataset_rules(
        ["supplier_id", "supplier_sku", "product_name", "unit_price", "currency"],
        [{"supplier_id": "SUP-1", "supplier_sku": "S-1", "product_name": "Widget",
          "unit_price": "10", "currency": "USD"}],
    )
    assert result["dataset_type"] == "supplier offers"


def test_generic_person_or_event_data_is_not_classified_as_product_catalog():
    result = profile_dataset_rules(
        ["id", "name", "created_at"],
        [{"id": "1", "name": "Alex", "created_at": "2026-01-01"}],
    )
    assert result["dataset_type"] == "general dataset"


def test_olist_product_master_maps_canonical_fields_and_runs_attribute_checks():
    headers = [
        "product_id", "product_category_name", "product_name_lenght",
        "product_description_lenght", "product_photos_qty", "product_weight_g",
        "product_length_cm", "product_height_cm", "product_width_cm",
    ]
    rows = [
        {
            "product_id": " P-001 ", "product_category_name": "perfumaria",
            "product_name_lenght": "40", "product_description_lenght": "287",
            "product_photos_qty": "1", "product_weight_g": "225",
            "product_length_cm": "16", "product_height_cm": "10", "product_width_cm": "14",
        },
        {
            "product_id": "P-002", "product_category_name": "  ",
            "product_name_lenght": "-1", "product_description_lenght": "not-a-number",
            "product_photos_qty": "-2", "product_weight_g": "0",
            "product_length_cm": "0", "product_height_cm": "", "product_width_cm": "12",
        },
    ]
    result = profile_dataset_rules(headers, rows)
    rules = {item["code"]: item for item in result["validation_rules"]}

    assert result["dataset_type"] == "product catalog"
    assert result["field_mappings"]["source_product_id"] == "product_id"
    assert result["field_mappings"]["product_category"] == "product_category_name"
    assert result["field_mappings"]["product_name_length"] == "product_name_lenght"
    assert rules["MALFORMED_PRODUCT_IDENTIFIER"]["issue_records"] == 1
    assert rules["INVALID_PRODUCT_NAME_LENGTH"]["issue_records"] == 1
    assert rules["INVALID_PRODUCT_DESCRIPTION_LENGTH"]["issue_records"] == 1
    assert rules["INVALID_PRODUCT_PHOTO_QUANTITY"]["issue_records"] == 1
    assert rules["NON_POSITIVE_PRODUCT_WEIGHT"]["issue_records"] == 1
    assert rules["NON_POSITIVE_PRODUCT_LENGTH"]["issue_records"] == 1
    assert rules["INCOMPLETE_PRODUCT_PHYSICAL_ATTRIBUTES"]["issue_records"] == 1


def test_shopify_and_erp_aliases_map_to_canonical_product_attributes():
    shopify = profile_dataset_rules(
        ["Handle", "Title", "Body (HTML)", "Vendor", "Type", "Variant SKU", "Variant Price", "Variant Barcode"],
        [{"Handle": "item-1", "Title": "Item", "Body (HTML)": "Description", "Vendor": "Acme",
          "Type": "Tools", "Variant SKU": "SKU-1", "Variant Price": "10", "Variant Barcode": "123"}],
    )
    assert shopify["field_mappings"]["product_name"] == "Title"
    assert shopify["field_mappings"]["seller_sku"] == "Variant SKU"
    assert shopify["field_mappings"]["product_description"] == "Body (HTML)"

    erp = profile_dataset_rules(
        ["Item Number", "Material Description", "Product Group", "Gross Weight", "Length", "Width", "Height"],
        [{"Item Number": "MAT-1", "Material Description": "Steel part", "Product Group": "Parts",
          "Gross Weight": "1.2", "Length": "10", "Width": "5", "Height": "2"}],
    )
    assert erp["field_mappings"]["source_product_id"] == "Item Number"
    assert erp["field_mappings"]["product_weight"] == "Gross Weight"


def test_product_numeric_checks_are_not_evaluated_when_source_fields_are_absent():
    result = profile_dataset_rules(["sku", "name"], [{"sku": "A-1", "name": "Widget"}])
    rules = {item["code"]: item for item in result["validation_rules"]}
    assert rules["INVALID_PRODUCT_PHOTO_QUANTITY"]["status"] == "not_evaluated"
    assert rules["NON_POSITIVE_PRODUCT_WEIGHT"]["status"] == "not_evaluated"
    assert rules["MALFORMED_PRODUCT_CATEGORY"]["status"] == "not_evaluated"
