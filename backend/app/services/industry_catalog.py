"""Flexible industry-aware CSV profiling and validation.

This layer deliberately does not coerce flexible industry records into the legacy
five-required-field Product model. It returns a stateless validation preview.
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

MAX_ROWS = 10_000
PREVIEW_LIMIT = 10
ERROR_LIMIT = 500

# Canonical field aliases are intentionally explicit. Ambiguous identifiers such
# as product_id, item_code and part_number are not treated as seller SKU by default.
ALIASES: dict[str, set[str]] = {
    "source_product_id": {"product_id", "source_product_id", "catalog_id", "item_id", "listing_id"},
    "sku": {"sku", "seller_sku", "merchant_sku", "product_sku", "item_sku", "stock_keeping_unit"},
    "buyer_sku": {"buyer_sku", "customer_sku"},
    "supplier_sku": {"supplier_sku", "vendor_sku", "supplier_item_code"},
    "supplier_id": {"supplier_id", "vendor_id", "supplier_code"},
    "title": {"title", "product_title", "product_name", "item_name", "name"},
    "description": {"description", "product_description", "long_description"},
    "name_length": {"product_name_lenght", "product_name_length", "name_length"},
    "description_length": {"product_description_lenght", "product_description_length", "description_length"},
    "brand": {"brand", "brand_name"},
    "manufacturer": {"manufacturer", "manufacturer_name", "mfr", "maker"},
    "mpn": {"mpn", "manufacturer_part_number", "mfr_part_number", "manufacturerpartnumber"},
    "model_number": {"model_number", "model_no", "model"},
    "gtin": {"gtin", "barcode", "ean", "upc", "gtin_8", "gtin_12", "gtin_13", "gtin_14"},
    "category": {"category", "product_category", "product_category_name", "category_name"},
    "product_type": {"product_type", "item_type"},
    "parent_product_id": {"parent_product_id", "parent_id", "item_group_id", "style_id"},
    "variant_id": {"variant_id", "option_id"},
    "size": {"size", "size_name"},
    "colour": {"colour", "color", "color_name"},
    "material": {"material", "fabric", "composition"},
    "image_count": {"product_photos_qty", "image_count", "photo_count"},
    "weight_g": {"product_weight_g", "weight_g"},
    "length_cm": {"product_length_cm", "length_cm"},
    "height_cm": {"product_height_cm", "height_cm"},
    "width_cm": {"product_width_cm", "width_cm"},
    "unit_price": {"price", "unit_price", "selling_price", "wholesale_price", "unit_cost", "cost"},
    "currency": {"currency", "currency_code"},
    "quantity": {"quantity", "stock", "available_qty", "inventory_qty", "quantity_available"},
    "quantity_on_hand": {"quantity_on_hand", "on_hand", "stock_on_hand"},
    "quantity_reserved": {"quantity_reserved", "reserved_quantity"},
    "moq": {"moq", "minimum_order_quantity"},
    "order_multiple": {"order_multiple", "order_increment"},
    "unit_of_measure": {"unit_of_measure", "uom", "unit"},
    "lead_time_days": {"lead_time_days", "lead_time"},
    "year": {"year", "vehicle_year", "model_year"},
    "make": {"make", "vehicle_make"},
    "vehicle_model": {"vehicle_model", "car_model"},
    "engine": {"engine", "engine_type"},
    "submodel": {"submodel", "trim"},
    "position": {"position", "placement"},
    "compatibility": {"compatibility", "compatible_with", "compatible_models", "model_compatibility"},
    "replacement_part": {"replacement_part", "replacement_sku", "supersedes", "superseded_by", "interchange"},
    "voltage": {"voltage", "input_voltage"},
    "power_w": {"power_w", "wattage", "power"},
    "frequency_hz": {"frequency_hz", "frequency"},
    "capacity": {"capacity", "storage_capacity"},
    "diameter": {"diameter"},
    "pressure_rating": {"pressure_rating", "max_pressure"},
    "temperature_range": {"temperature_range", "operating_temperature"},
    "standard": {"standard", "specification", "certification"},
    "pack_size": {"pack_size", "units_per_case", "case_qty"},
    "lead_time": {"lead_time"},
}

PROFILES: dict[str, dict[str, Any]] = {
    "d2c": {"required": ("title",), "signals": {"brand", "parent_product_id", "variant_id", "size", "colour", "material"}},
    "ecommerce": {"required": ("title",), "signals": {"sku", "gtin", "category", "unit_price", "currency", "quantity"}},
    "automotive": {"required": ("manufacturer", "mpn"), "signals": {"year", "make", "vehicle_model", "engine", "submodel", "position", "compatibility", "replacement_part"}},
    "electronics": {"required": ("manufacturer", "mpn"), "signals": {"model_number", "voltage", "power_w", "frequency_hz", "capacity", "compatibility", "standard"}},
    "industrial": {"required": ("manufacturer", "mpn"), "signals": {"product_type", "material", "diameter", "pressure_rating", "temperature_range", "standard", "replacement_part"}},
    "wholesale": {"required": ("supplier_sku",), "signals": {"supplier_id", "buyer_sku", "unit_price", "currency", "quantity", "moq", "order_multiple", "unit_of_measure", "lead_time_days", "pack_size"}},
}

NUMERIC_NONNEGATIVE = {
    "name_length", "description_length", "image_count", "weight_g", "length_cm",
    "height_cm", "width_cm", "unit_price", "quantity", "quantity_on_hand",
    "quantity_reserved", "moq", "order_multiple", "lead_time_days", "year",
    "voltage", "power_w", "frequency_hz", "capacity", "diameter", "pressure_rating",
    "pack_size",
}


class IndustryCSVError(ValueError):
    pass


def normalize_header(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).strip().casefold()
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_")


def detect_industry(headers: list[str]) -> dict[str, Any]:
    normalized = {normalize_header(h) for h in headers}
    scores = {
        profile: len(normalized & spec["signals"])
        for profile, spec in PROFILES.items()
    }
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best, score = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 0
    # Do not force an industry where evidence is weak or tied.
    if score < 2 or score == second:
        return {"profile_id": None, "confidence": 0.0, "scores": scores, "needs_confirmation": True}
    confidence = round(min(0.99, 0.55 + 0.10 * (score - second)), 2)
    return {"profile_id": best, "confidence": confidence, "scores": scores, "needs_confirmation": False}


def validate_industry_csv(content: str, profile_id: str | None = None, max_rows: int = MAX_ROWS) -> dict[str, Any]:
    if profile_id is not None and profile_id not in PROFILES:
        raise IndustryCSVError(f"Unknown industry profile '{profile_id}'.")
    try:
        dialect = csv.Sniffer().sniff(content[:65536], delimiters=",;\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","
    reader = csv.reader(io.StringIO(content, newline=""), delimiter=delimiter, strict=True)
    headers = next(reader, None)
    if not headers:
        raise IndustryCSVError("CSV header row is missing.")
    normalized = [normalize_header(h) for h in headers]
    if any(not h for h in normalized):
        raise IndustryCSVError("CSV contains an empty column header.")
    if len(normalized) != len(set(normalized)):
        raise IndustryCSVError("CSV contains duplicate column headers after normalization.")

    detected = detect_industry(headers)
    selected_profile = profile_id or detected["profile_id"]
    if selected_profile is None:
        return {
            "profile_id": None, "profile_detection": detected, "total_rows": 0,
            "valid_rows": 0, "invalid_rows": 0, "column_mappings": [],
            "unmapped_headers": headers, "field_metrics": [], "issues": [],
            "preview": [], "metrics": {"mapping_coverage_pct": 0.0},
            "requires_profile_confirmation": True,
        }

    alias_lookup: dict[str, str] = {}
    for field, aliases in ALIASES.items():
        for alias in aliases | {field}:
            alias_lookup[alias] = field
    mapped: dict[str, tuple[int, float]] = {}
    ambiguous: set[str] = set()
    unmapped: list[str] = []
    for index, header in enumerate(normalized):
        field = alias_lookup.get(header)
        if field is None or field in ambiguous:
            unmapped.append(headers[index])
            continue
        if field in mapped:
            previous = mapped.pop(field)[0]
            unmapped.extend([headers[previous], headers[index]])
            ambiguous.add(field)
            continue
        # Explicit source ID is not treated as a SKU. Confidence is based on exact
        # normalized aliases only; ambiguous generic part_number is intentionally unmapped.
        mapped[field] = (index, 0.99 if header == field else 0.95)

    mappings = [
        {"field": field, "source_header": headers[index], "confidence": confidence}
        for field, (index, confidence) in mapped.items()
    ]
    required = PROFILES[selected_profile]["required"]
    rows: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    populated: Counter[str] = Counter()
    seen: dict[str, dict[str, int]] = {}
    total = 0
    valid = 0

    def add_issue(row_number: int, field: str | None, code: str, message: str, severity: str = "critical"):
        if len(issues) < ERROR_LIMIT:
            issues.append({"row_number": row_number, "field": field, "error_code": code, "message": message, "severity": severity})

    for line_number, values in enumerate(reader, start=2):
        if not values or all(not str(v).strip() for v in values):
            continue
        total += 1
        if total > max_rows:
            raise IndustryCSVError(f"CSV exceeds the {max_rows:,}-row limit.")
        if len(values) != len(headers):
            add_issue(line_number, None, "COLUMN_COUNT_MISMATCH", f"Expected {len(headers)} columns but found {len(values)}.")
            continue
        row: dict[str, Any] = {}
        for field, (index, _) in mapped.items():
            raw = (values[index] or "").strip()
            row[field] = None if raw.casefold() in {"", "n/a", "null", "none", "-", "--"} else raw
            if row[field] is not None:
                populated[field] += 1
        row_issue_count = len(issues)
        for field in required:
            if row.get(field) in (None, ""):
                add_issue(line_number, field, "PROFILE_REQUIRED_FIELD_MISSING", f"Required field '{field}' is missing for profile '{selected_profile}'.")
        for field in NUMERIC_NONNEGATIVE & row.keys():
            value = row.get(field)
            if value is None:
                continue
            try:
                number = Decimal(str(value).replace(",", ""))
                if not number.is_finite() or number < 0:
                    raise InvalidOperation
            except (InvalidOperation, ValueError):
                add_issue(line_number, field, "INVALID_NONNEGATIVE_NUMBER", f"'{value}' is not a valid non-negative number for '{field}'.")
        if row.get("currency") is not None and not re.fullmatch(r"[A-Za-z]{3}", str(row["currency"])):
            add_issue(line_number, "currency", "INVALID_CURRENCY_CODE", "Currency must be a three-letter ISO 4217 code.")
        elif row.get("currency") is not None:
            row["currency"] = str(row["currency"]).upper()
        if row.get("unit_price") is not None and row.get("currency") is None:
            add_issue(line_number, "currency", "PRICE_CURRENCY_MISSING", "A price cannot be interpreted without its currency.")
        for positive_field, code, message in (
            ("moq", "MOQ_MUST_BE_POSITIVE", "Minimum order quantity must be greater than zero."),
            ("order_multiple", "ORDER_MULTIPLE_MUST_BE_POSITIVE", "Order multiple must be greater than zero."),
        ):
            if row.get(positive_field) is not None:
                try:
                    if Decimal(str(row[positive_field])) <= 0:
                        add_issue(line_number, positive_field, code, message)
                except InvalidOperation:
                    pass  # The numeric validator above already reports the malformed value.
        if row.get("quantity_on_hand") is not None and row.get("quantity_reserved") is not None and row.get("quantity_available") is not None:
            try:
                if Decimal(str(row["quantity_available"])) != Decimal(str(row["quantity_on_hand"])) - Decimal(str(row["quantity_reserved"])):
                    add_issue(line_number, "quantity_available", "INVENTORY_QUANTITY_MISMATCH", "Available quantity does not equal on-hand minus reserved quantity.", "warning")
            except InvalidOperation:
                pass
        unique_field = "sku" if row.get("sku") else "supplier_sku" if row.get("supplier_sku") else None
        if unique_field and row.get(unique_field):
            scope = str(row.get("supplier_id") or "default").casefold() if unique_field == "supplier_sku" else "seller"
            key = f"{unique_field}:{scope}:{str(row[unique_field]).casefold()}"
            if key in seen:
                add_issue(line_number, unique_field, "DUPLICATE_IDENTIFIER", f"Identifier duplicates row {seen[key]['row']}.")
            else:
                seen[key] = {"row": line_number}
        if len(issues) == row_issue_count:
            valid += 1
        if len(rows) < PREVIEW_LIMIT:
            rows.append(row)

    metrics = []
    for field in sorted(set(required) | set(mapped)):
        count = populated[field]
        metrics.append({
            "field": field, "applicable": True, "populated": count,
            "missing": total - count,
            "completeness_pct": round(count / total * 100, 2) if total else 100.0,
        })
    relevant_columns = len(headers)
    mapping_coverage = round(len(mapped) / relevant_columns * 100, 2) if relevant_columns else 0.0
    valid_rate = round(valid / total * 100, 2) if total else 100.0
    return {
        "profile_id": selected_profile,
        "profile_detection": detected,
        "requires_profile_confirmation": profile_id is None and detected["needs_confirmation"],
        "total_rows": total, "valid_rows": valid, "invalid_rows": total - valid,
        "validation_pass_rate": valid_rate,
        "column_mappings": mappings, "unmapped_headers": unmapped,
        "field_metrics": metrics, "issues": issues, "preview": rows,
        "metrics": {
            "mapping_coverage_pct": mapping_coverage,
            "validation_pass_rate_pct": valid_rate,
            "issue_count": len(issues),
            "critical_issue_count": sum(i["severity"] == "critical" for i in issues),
            "warning_issue_count": sum(i["severity"] == "warning" for i in issues),
        },
        "persisted": False,
        "validation_scope": "industry_profile_mapping_and_row_level_syntax_checks; no external reference-data verification",
    }
