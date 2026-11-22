"""Release-blocking regression benchmark for dataset profiling.

The benchmark intentionally uses small, reviewed fixtures with explicit expected
classifications and findings. It complements focused unit tests: every change to
the profiler must preserve deterministic output and internally consistent rule
metadata across representative business datasets.
"""
from __future__ import annotations

import pytest

from app.services.dataset_rules import profile_dataset_rules


CASES = [
    pytest.param(
        ["sku", "name", "manufacturer", "part_number", "category"],
        [{"sku": "SKU-1", "name": "Widget", "manufacturer": "Acme",
          "part_number": "A-1", "category": "Parts"}],
        "product catalog",
        id="product-catalog",
    ),
    pytest.param(
        ["quantity_on_hand", "quantity_reserved", "quantity_available"],
        [{"quantity_on_hand": "10", "quantity_reserved": "2", "quantity_available": "8"},
         {"quantity_on_hand": "-1", "quantity_reserved": "0", "quantity_available": "-2"}],
        "inventory",
        id="inventory",
    ),
    pytest.param(
        ["customer_id", "email"],
        [{"customer_id": "C-1", "email": "valid@example.com"},
         {"customer_id": "C-1", "email": "not-an-email"}],
        "customer records",
        id="customer-records",
    ),
    pytest.param(
        ["order_id", "order_status", "order_purchase_timestamp",
         "order_delivered_customer_date"],
        [{"order_id": "O-1", "order_status": "delivered",
          "order_purchase_timestamp": "2026-01-02T12:00:00",
          "order_delivered_customer_date": "2026-01-01T12:00:00"}],
        "orders / transactions",
        id="orders",
    ),
    pytest.param(
        ["supplier_id", "supplier_sku", "unit_price", "currency"],
        [{"supplier_id": "S-1", "supplier_sku": "P-1",
          "unit_price": "12.50", "currency": "USD"},
         {"supplier_id": "S-2", "supplier_sku": "P-2",
          "unit_price": "0", "currency": ""}],
        "supplier offers",
        id="supplier-offers",
    ),
    pytest.param(
        ["transaction_id", "amount"],
        [{"transaction_id": "T-1", "amount": "10.00"},
         {"transaction_id": "T-2", "amount": "-1.00"}],
        "financial transactions",
        id="financial-transactions",
    ),
    pytest.param(
        ["field_a", "field_b"],
        [{"field_a": "x", "field_b": "y"}],
        "general dataset",
        id="general-dataset",
    ),
]


@pytest.mark.parametrize(("headers", "rows", "expected_type"), CASES)
def test_reviewed_dataset_classification_and_rule_metadata(headers, rows, expected_type):
    result = profile_dataset_rules(headers, rows, missing_cells=2, duplicate_rows=0)

    assert result["dataset_type"] == expected_type
    assert isinstance(result["validation_rules"], list)
    assert result["validation_rules"], "Every profiled dataset must expose its rule catalogue."

    codes = [rule["code"] for rule in result["validation_rules"]]
    assert len(codes) == len(set(codes)), "Rule codes must be unique within a report."

    for rule in result["validation_rules"]:
        assert rule["status"] in {"evaluated", "not_applicable", "not_evaluated"}
        assert isinstance(rule["records_evaluated"], int)
        assert rule["records_evaluated"] >= 0
        if rule["status"] == "evaluated":
            assert isinstance(rule["issue_records"], int)
            assert rule["issue_records"] >= 0
            assert rule["records_evaluated"] == len(rows)
        else:
            assert rule["issue_records"] is None
            assert rule["records_evaluated"] == 0


@pytest.mark.parametrize(("headers", "rows", "expected_type"), CASES)
def test_reviewed_dataset_profiles_are_deterministic(headers, rows, expected_type):
    first = profile_dataset_rules(headers, rows, missing_cells=2, duplicate_rows=0)
    second = profile_dataset_rules(headers, rows, missing_cells=2, duplicate_rows=0)

    assert first == second
    assert first["dataset_type"] == expected_type


def test_rule_status_totals_reconcile_with_the_report_catalogue():
    result = profile_dataset_rules(
        ["order_id", "order_status"],
        [{"order_id": "O-1", "order_status": "unavailable"}],
        missing_cells=1,
        duplicate_rows=0,
    )
    rules = result["validation_rules"]
    status_counts = {
        status: sum(rule["status"] == status for rule in rules)
        for status in ("evaluated", "not_applicable", "not_evaluated")
    }

    assert sum(status_counts.values()) == len(rules)
    assert status_counts["evaluated"] > 0
    assert status_counts["not_applicable"] > 0
    assert status_counts["not_evaluated"] > 0


def test_domain_issue_list_is_exactly_the_nonzero_subset_of_domain_checks():
    result = profile_dataset_rules(
        ["customer_id", "email"],
        [{"customer_id": "C-1", "email": "valid@example.com"},
         {"customer_id": "C-1", "email": "invalid"}],
    )

    expected = {
        check["code"]: check["issue_records"]
        for check in result["domain_checks"]
        if check["issue_records"] > 0
    }
    actual = {issue["code"]: issue["count"] for issue in result["domain_issues"]}

    assert actual == expected


def test_olist_source_identifier_is_not_promoted_to_seller_sku():
    headers = [
        "product_id", "product_category_name", "product_name_lenght",
        "product_description_lenght", "product_photos_qty", "product_weight_g",
        "product_length_cm", "product_height_cm", "product_width_cm",
    ]
    rows = [{
        "product_id": "P-1", "product_category_name": "tools",
        "product_name_lenght": "40", "product_description_lenght": "200",
        "product_photos_qty": "2", "product_weight_g": "500",
        "product_length_cm": "20", "product_height_cm": "10",
        "product_width_cm": "15",
    }]

    result = profile_dataset_rules(headers, rows)
    rules = {rule["code"]: rule for rule in result["validation_rules"]}

    assert result["dataset_type"] == "product catalog"
    assert result["field_mappings"]["source_product_id"] == "product_id"
    assert rules["MISSING_PRODUCT_SKU"]["status"] == "not_evaluated"
    assert rules["DUPLICATE_PRODUCT_SKU"]["status"] == "not_evaluated"
    assert rules["MISSING_SOURCE_PRODUCT_ID"]["issue_records"] == 0
    assert rules["DUPLICATE_SOURCE_PRODUCT_ID"]["issue_records"] == 0


def test_olist_physical_attribute_rules_distinguish_partial_and_all_missing():
    headers = [
        "product_id", "product_category_name", "product_weight_g",
        "product_length_cm", "product_width_cm",
    ]
    rows = [
        {"product_id": "P-1", "product_category_name": "tools",
         "product_weight_g": "10", "product_length_cm": "", "product_width_cm": "4"},
        {"product_id": "P-2", "product_category_name": "tools",
         "product_weight_g": "", "product_length_cm": "", "product_width_cm": ""},
    ]

    result = profile_dataset_rules(headers, rows)
    checks = {check["code"]: check for check in result["domain_checks"]}

    assert checks["INCOMPLETE_PRODUCT_PHYSICAL_ATTRIBUTES"]["issue_records"] == 1
    assert checks["MISSING_PRODUCT_PHYSICAL_ATTRIBUTES"]["issue_records"] == 1
