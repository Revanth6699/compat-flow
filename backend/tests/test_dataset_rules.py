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
