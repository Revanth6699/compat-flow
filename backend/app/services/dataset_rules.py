"""Evidence-based, dataset-specific checks for structural dataset profiling.

These checks are intentionally conservative: they only run when the relevant
source columns are present and never claim external/reference validation.
"""
from __future__ import annotations

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


def profile_dataset_rules(headers: list[str], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a conservative dataset classification and applicable rule findings."""
    by_name = {_norm(header): header for header in headers}
    names = set(by_name)
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
    elif names & {"sku", "product_sku", "item_sku", "product_code", "product_name", "item_name", "manufacturer", "manufacturer_name", "part_number", "mpn", "category", "product_category"}:
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

    if dataset_type == "orders / transactions":
        status_col = header("order_status", "status")
        # Do not guess a universal order-status vocabulary. Status values vary
        # by source system and workflow (for example, Olist's "unavailable").
        # A status rule should run only when the customer supplies an allowed
        # vocabulary in a validation profile.
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

    return {"dataset_type": dataset_type, "domain_checks": checks, "domain_issues": issues}
