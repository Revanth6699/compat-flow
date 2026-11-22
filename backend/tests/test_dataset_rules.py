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
