"""Evidence-based, dataset-specific checks for structural dataset profiling.

These checks are intentionally conservative: they only run when the relevant
source columns are present and never claim external/reference validation.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from typing import Any


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        cleaned = str(value).strip().replace(",", "").replace("$", "").replace("₹", "").replace("€", "")
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = "-" + cleaned[1:-1]
        return float(cleaned)
    except (TypeError, ValueError):
        return None


def profile_dataset_rules(
    headers: list[str], rows: list[dict[str, Any]],
    *, missing_cells: int | None = None, duplicate_rows: int | None = None,
) -> dict[str, Any]:
    """Return a conservative dataset classification and applicable rule findings."""
    by_name = {_norm(header): header for header in headers}
    names = set(by_name)
    # Some real product masters use source-system product IDs and descriptive
    # attributes without exposing a seller SKU or a conventional "name" column.
    # Require multiple product-specific signals (or product_id plus one such
    # attribute) so a generic ID column alone cannot force product classification.
    olist_product_signals = {
        "product_category_name", "product_name_lenght", "product_name_length",
        "product_description_lenght", "product_description_length",
        "product_photos_qty", "product_weight_g", "product_length_cm",
        "product_height_cm", "product_width_cm",
    }
    has_product_signature = (
        len(names & olist_product_signals) >= 2
        or ("product_id" in names and bool(names & olist_product_signals))
    )
    if {"supplier_id", "unit_price"} <= names or {"supplier_sku", "unit_price"} <= names:
        dataset_type = "supplier offers"
    elif names & {"quantity_on_hand", "quantity_available", "stock_quantity", "available_quantity"}:
        dataset_type = "inventory"
    elif names & {"order_id", "order_status", "order_purchase_timestamp", "order_item_id"}:
        dataset_type = "orders / transactions"
    elif names & {"transaction_id", "payment_id", "invoice_id"} and names & {"amount", "total", "total_amount", "transaction_amount"}:
        dataset_type = "financial transactions"
    elif names & {"email", "customer_email", "email_address", "customer_id", "customer_unique_id"}:
        dataset_type = "customer records"
    elif has_product_signature or names & {"sku", "product_sku", "item_sku", "product_code", "product_name", "item_name", "manufacturer", "manufacturer_name", "part_number", "mpn", "category", "product_category", "product_category_name"}:
        dataset_type = "product catalog"
    else:
        dataset_type = "general dataset"

    checks: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []

    def add_check(code: str, title: str, count: int, detail: str, recommendation: str, severity: str = "warning") -> None:
        checks.append({"code": code, "title": title, "issue_records": count, "severity": severity, "detail": detail, "recommendation": recommendation})
        if count:
            issues.append({"code": code, "title": title, "count": count, "severity": severity, "detail": detail, "recommendation": recommendation})

    def header(*candidates: str) -> str | None:
        return next((by_name[name] for name in candidates if name in by_name), None)

    if dataset_type == "product catalog":
        source_id_col = header("product_id", "source_product_id", "catalog_id", "item_id")
        if source_id_col:
            source_ids = [
                str(row.get(source_id_col)).strip().casefold()
                for row in rows
                if row.get(source_id_col) not in (None, "") and str(row.get(source_id_col)).strip()
            ]
            missing_source_ids = sum(
                1 for row in rows
                if row.get(source_id_col) in (None, "") or not str(row.get(source_id_col)).strip()
            )
            duplicate_source_ids = sum(count - 1 for count in Counter(source_ids).values() if count > 1)
            add_check(
                "MISSING_SOURCE_PRODUCT_ID", "Missing source product IDs", missing_source_ids,
                f"{missing_source_ids} product records have no source product identifier.",
                "Provide the source system's product ID. Do not substitute a seller SKU, MPN, or barcode.",
                "critical",
            )
            add_check(
                "DUPLICATE_SOURCE_PRODUCT_ID", "Duplicate source product IDs", duplicate_source_ids,
                f"{duplicate_source_ids} product records repeat a source product identifier.",
                "Confirm the dataset grain and source-system uniqueness rules; repeated IDs may represent variants or multiple offers rather than duplicate products.",
            )

        sku_col = header("sku", "product_sku", "item_sku", "product_code")
        if sku_col:
            missing_skus = sum(1 for row in rows if row.get(sku_col) in (None, "") or not str(row.get(sku_col)).strip())
            add_check(
                "MISSING_PRODUCT_SKU", "Missing product SKUs", missing_skus,
                f"{missing_skus} product records have no seller SKU.",
                "Provide the seller-assigned SKU or use a different source profile when the source identifier is not a seller SKU.",
                "critical",
            )
            sku_values = [
                str(row.get(sku_col)).strip().casefold()
                for row in rows
                if row.get(sku_col) not in (None, "") and str(row.get(sku_col)).strip()
            ]
            duplicate_skus = sum(count - 1 for count in Counter(sku_values).values() if count > 1)
            add_check(
                "DUPLICATE_PRODUCT_SKU", "Duplicate product SKUs", duplicate_skus,
                f"{duplicate_skus} product records repeat a seller SKU.",
                "Confirm whether repeated SKUs are duplicate products or legitimate variant/location records; choose the matching dataset grain.",
                "critical",
            )

        # Validate only explicit relationships whose target keys are present in
        # this same dataset. Never treat a missing external master file as proof
        # that a reference is invalid.
        product_id_col = header("product_id", "source_product_id", "item_id")
        parent_col = header("parent_product_id", "parent_id")
        if product_id_col and parent_col:
            known_product_ids = {
                str(row.get(product_id_col)).strip().casefold()
                for row in rows
                if row.get(product_id_col) not in (None, "")
                and str(row.get(product_id_col)).strip()
            }
            orphan_parents = 0
            self_parent_references = 0
            for row in rows:
                product_id = row.get(product_id_col)
                parent_id = row.get(parent_col)
                if parent_id in (None, "") or not str(parent_id).strip():
                    continue
                normalized_parent = str(parent_id).strip().casefold()
                if product_id not in (None, "") and normalized_parent == str(product_id).strip().casefold():
                    self_parent_references += 1
                elif normalized_parent not in known_product_ids:
                    orphan_parents += 1
            add_check(
                "ORPHAN_PRODUCT_PARENT", "Product parent reference not found", orphan_parents,
                f"{orphan_parents} product records reference a parent ID that is absent from this dataset.",
                "Include the referenced parent product or correct the parent ID. External references are not checked by this file-level rule.",
                "critical",
            )
            add_check(
                "SELF_REFERENCING_PRODUCT", "Product references itself as parent", self_parent_references,
                f"{self_parent_references} product records use their own product ID as the parent ID.",
                "Correct the parent relationship; a product cannot be its own parent.",
                "critical",
            )

        replacement_col = header("replacement_sku", "superseded_by_sku")
        if sku_col and replacement_col:
            known_skus = {
                str(row.get(sku_col)).strip().casefold()
                for row in rows
                if row.get(sku_col) not in (None, "")
                and str(row.get(sku_col)).strip()
            }
            orphan_replacements = 0
            self_replacements = 0
            for row in rows:
                replacement = row.get(replacement_col)
                sku = row.get(sku_col)
                if replacement in (None, "") or not str(replacement).strip():
                    continue
                normalized_replacement = str(replacement).strip().casefold()
                if sku not in (None, "") and normalized_replacement == str(sku).strip().casefold():
                    self_replacements += 1
                elif normalized_replacement not in known_skus:
                    orphan_replacements += 1
            add_check(
                "ORPHAN_REPLACEMENT_SKU", "Replacement SKU not found", orphan_replacements,
                f"{orphan_replacements} product records point to a replacement SKU that is absent from this dataset.",
                "Include the replacement product or correct the replacement SKU. References outside this dataset are not checked.",
                "critical",
            )
            add_check(
                "SELF_REPLACING_PRODUCT", "Product replaces itself", self_replacements,
                f"{self_replacements} product records use their own SKU as the replacement SKU.",
                "Correct the replacement relationship; a product cannot replace itself.",
                "critical",
            )
    elif dataset_type == "orders / transactions":
        status_col = header("order_status", "status")
        if status_col:
            allowed = {"created", "pending", "approved", "processing", "shipped", "delivered", "cancelled", "canceled", "returned", "refunded", "completed", "paid", "invoiced", "unavailable", "sent"}
            unknown = sum(1 for row in rows if row.get(status_col) not in (None, "") and str(row[status_col]).strip().casefold() not in allowed)
            add_check("UNRECOGNIZED_ORDER_STATUS", "Unrecognized order statuses", unknown, f"{unknown} rows contain statuses outside the recognized order-status vocabulary. Review these values against your business workflow.", "Confirm the allowed order-status vocabulary and normalize inconsistent values.")
        start = header("order_purchase_timestamp", "purchase_date", "order_date", "created_at")
        end = header("order_delivered_customer_date", "delivered_at", "delivery_date", "delivered_date")
        if start and end:
            reversed_dates = 0
            for row in rows:
                try:
                    a = datetime.fromisoformat(str(row.get(start)).strip().replace("Z", "+00:00"))
                    b = datetime.fromisoformat(str(row.get(end)).strip().replace("Z", "+00:00"))
                    reversed_dates += b < a
                except (TypeError, ValueError):
                    continue
            add_check("DELIVERY_BEFORE_PURCHASE", "Delivery date precedes purchase date", reversed_dates, f"{reversed_dates} rows have a delivery timestamp earlier than the purchase timestamp.", "Correct the source timestamps or investigate timezone and date-mapping errors.", "critical")
    elif dataset_type == "inventory":
        quantity_cols = [header(name) for name in ("quantity_on_hand", "quantity_available", "available_quantity", "stock_quantity", "quantity_reserved") if header(name)]
        negative = sum(1 for row in rows if any(_number(row.get(col)) is not None and _number(row.get(col)) < 0 for col in quantity_cols))
        add_check("NEGATIVE_INVENTORY_QUANTITY", "Negative inventory quantities", negative, f"{negative} records contain at least one quantity below zero.", "Verify stock movements, reservations and adjustment signs before importing.", "critical")
        on_hand, reserved, available = header("quantity_on_hand", "stock_quantity"), header("quantity_reserved"), header("quantity_available", "available_quantity")
        if on_hand and reserved and available:
            mismatch = 0
            for row in rows:
                a, b, c = _number(row.get(on_hand)), _number(row.get(reserved)), _number(row.get(available))
                if a is not None and b is not None and c is not None and abs((a - b) - c) > 0.000001:
                    mismatch += 1
            add_check("INVENTORY_BALANCE_MISMATCH", "Available stock does not reconcile", mismatch, f"{mismatch} rows do not satisfy available = on-hand minus reserved.", "Reconcile stock, reservations and available quantities using the source system's inventory rules.")
    elif dataset_type == "supplier offers":
        price_col, moq_col = header("unit_price", "price"), header("minimum_order_quantity", "moq")
        if price_col:
            invalid = sum(1 for row in rows if _number(row.get(price_col)) is not None and _number(row.get(price_col)) <= 0)
            add_check("NON_POSITIVE_SUPPLIER_PRICE", "Non-positive supplier prices", invalid, f"{invalid} supplier offers have a price of zero or less.", "Confirm whether free or zero-priced offers are valid; otherwise correct the price.")
        if moq_col:
            invalid = sum(1 for row in rows if _number(row.get(moq_col)) is not None and _number(row.get(moq_col)) <= 0)
            add_check("INVALID_MINIMUM_ORDER_QUANTITY", "Invalid minimum order quantities", invalid, f"{invalid} offers have a minimum order quantity of zero or less.", "Set a positive MOQ or explicitly define how non-positive values should be handled.")
        currency_col = header("currency", "currency_code")
        if price_col and currency_col:
            missing_currency = sum(
                1 for row in rows
                if row.get(price_col) not in (None, "")
                and row.get(currency_col) in (None, "")
            )
            add_check(
                "PRICE_WITHOUT_CURRENCY", "Price missing currency", missing_currency,
                f"{missing_currency} priced offers do not specify a currency.",
                "Provide the ISO 4217 currency code; do not infer currency from locale or supplier location.",
                "critical",
            )
            invalid_currency = sum(
                1 for row in rows
                if row.get(currency_col) not in (None, "")
                and not re.fullmatch(r"[A-Z]{3}", str(row[currency_col]).strip().upper())
            )
            add_check(
                "INVALID_CURRENCY_FORMAT", "Invalid currency code format", invalid_currency,
                f"{invalid_currency} offers contain a currency value that is not a three-letter code.",
                "Normalize currency values to ISO 4217 codes and verify the code is supported.",
            )
    elif dataset_type == "financial transactions":
        amount_col = header("amount", "total", "total_amount", "transaction_amount")
        if amount_col:
            negative = sum(1 for row in rows if _number(row.get(amount_col)) is not None and _number(row.get(amount_col)) < 0)
            add_check("NEGATIVE_TRANSACTION_AMOUNT", "Negative transaction amounts", negative, f"{negative} transaction amounts are negative.", "Confirm whether negative values represent refunds/chargebacks or incorrect transaction amounts.")
    elif dataset_type == "customer records":
        email_col = header("email", "customer_email", "email_address")
        if email_col:
            invalid = sum(1 for row in rows if row.get(email_col) not in (None, "") and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", str(row[email_col]).strip()))
            add_check("INVALID_EMAIL_FORMAT", "Malformed email addresses", invalid, f"{invalid} non-empty email values do not match a basic email-address format.", "Correct malformed addresses; verify deliverability separately with an email verification service.")
        id_col = header("customer_id", "customer_unique_id")
        if id_col:
            ids = [str(row[id_col]).strip() for row in rows if row.get(id_col) not in (None, "")]
            duplicate_count = sum(count - 1 for count in Counter(ids).values() if count > 1)
            add_check("DUPLICATE_CUSTOMER_IDENTIFIER", "Duplicate customer identifiers", duplicate_count, f"{duplicate_count} repeated customer identifier values were found.", "Confirm whether repeated IDs represent duplicate customer records or legitimate multiple transactions.")

    # A stable rule catalogue is returned for every dataset, not only when a
    # domain-specific rule happens to match. This makes applicability explicit
    # and prevents an absent check from being mistaken for a successful check.
    if missing_cells is None:
        missing_cells = sum(
            1 for row in rows for column in headers
            if row.get(column) is None or str(row.get(column)).strip() == ""
        )
    if duplicate_rows is None:
        row_counts: Counter[str] = Counter()
        duplicate_rows = 0
        for row in rows:
            key = json.dumps(
                [row.get(column) for column in headers],
                ensure_ascii=False, separators=(",", ":"), default=str,
            )
            row_counts[key] += 1
            if row_counts[key] > 1:
                duplicate_rows += 1

    evaluated = {item["code"]: item for item in checks}
    rule_definitions = [
        ("MISSING_VALUES", "Missing values", "structural", "warning", None),
        ("EXACT_DUPLICATE_ROWS", "Exact duplicate rows", "structural", "warning", None),
        ("MISSING_SOURCE_PRODUCT_ID", "Missing source product IDs", "product catalog", "critical", "product catalog"),
        ("DUPLICATE_SOURCE_PRODUCT_ID", "Duplicate source product IDs", "product catalog", "warning", "product catalog"),
        ("MISSING_PRODUCT_SKU", "Missing product SKUs", "product catalog", "critical", "product catalog"),
        ("DUPLICATE_PRODUCT_SKU", "Duplicate product SKUs", "product catalog", "critical", "product catalog"),
        ("ORPHAN_PRODUCT_PARENT", "Product parent reference not found", "product catalog", "critical", "product catalog"),
        ("SELF_REFERENCING_PRODUCT", "Product references itself as parent", "product catalog", "critical", "product catalog"),
        ("ORPHAN_REPLACEMENT_SKU", "Replacement SKU not found", "product catalog", "critical", "product catalog"),
        ("SELF_REPLACING_PRODUCT", "Product replaces itself", "product catalog", "critical", "product catalog"),
        ("PRICE_WITHOUT_CURRENCY", "Price missing currency", "supplier offers", "critical", "supplier offers"),
        ("INVALID_CURRENCY_FORMAT", "Invalid currency code format", "supplier offers", "warning", "supplier offers"),
        ("UNRECOGNIZED_ORDER_STATUS", "Unrecognized order statuses", "orders / transactions", "warning", "orders / transactions"),
        ("DELIVERY_BEFORE_PURCHASE", "Delivery date precedes purchase date", "orders / transactions", "critical", "orders / transactions"),
        ("NEGATIVE_INVENTORY_QUANTITY", "Negative inventory quantities", "inventory", "critical", "inventory"),
        ("INVENTORY_BALANCE_MISMATCH", "Available stock does not reconcile", "inventory", "warning", "inventory"),
        ("NON_POSITIVE_SUPPLIER_PRICE", "Non-positive supplier prices", "supplier offers", "warning", "supplier offers"),
        ("INVALID_MINIMUM_ORDER_QUANTITY", "Invalid minimum order quantities", "supplier offers", "warning", "supplier offers"),
        ("NEGATIVE_TRANSACTION_AMOUNT", "Negative transaction amounts", "financial transactions", "warning", "financial transactions"),
        ("INVALID_EMAIL_FORMAT", "Malformed email addresses", "customer records", "warning", "customer records"),
        ("DUPLICATE_CUSTOMER_IDENTIFIER", "Duplicate customer identifiers", "customer records", "warning", "customer records"),
    ]
    validation_rules = []
    for code, title, category, severity, required_dataset in rule_definitions:
        if code == "MISSING_VALUES":
            validation_rules.append({
                "code": code, "title": title, "category": category,
                "severity": severity, "status": "evaluated",
                "records_evaluated": len(rows), "issue_records": missing_cells,
                "detail": f"{missing_cells} empty cells were found across the dataset.",
                "recommendation": "Review missing values against the fields required by your business process.",
            })
        elif code == "EXACT_DUPLICATE_ROWS":
            validation_rules.append({
                "code": code, "title": title, "category": category,
                "severity": severity, "status": "evaluated",
                "records_evaluated": len(rows), "issue_records": duplicate_rows,
                "detail": f"{duplicate_rows} rows repeat an earlier exact row.",
                "recommendation": "Confirm whether repeated rows are accidental duplicates or legitimate repeated events.",
            })
        elif required_dataset != dataset_type:
            validation_rules.append({
                "code": code, "title": title, "category": category,
                "severity": severity, "status": "not_applicable",
                "records_evaluated": 0, "issue_records": None,
                "detail": f"This check applies to {required_dataset} datasets, not {dataset_type}.",
                "recommendation": "No action required unless the dataset is reclassified.",
            })
        else:
            result = evaluated.get(code)
            if result is None:
                validation_rules.append({
                    "code": code, "title": title, "category": category,
                    "severity": severity, "status": "not_evaluated",
                    "records_evaluated": 0, "issue_records": None,
                    "detail": "The required source columns were not available, so this check could not run.",
                    "recommendation": "Provide the relevant source columns or review the dataset profile.",
                })
            else:
                validation_rules.append({
                    **result, "category": category, "status": "evaluated",
                    "records_evaluated": len(rows),
                })

    return {
        "dataset_type": dataset_type,
        "domain_checks": checks,
        "domain_issues": issues,
        "validation_rules": validation_rules,
    }
