"""Deterministic validation of parsed rows against the five catalog record types."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.schemas import (
    InventorySnapshotCreateRequest,
    ProductCreateRequest,
    ProductIdentifierCreateRequest,
    ProductVariantCreateRequest,
    SupplierOfferCreateRequest,
)
from app.services.ingestion_adapters import ParsedSource


RECORD_MODELS = {
    "products": ProductCreateRequest,
    "product_variants": ProductVariantCreateRequest,
    "supplier_offers": SupplierOfferCreateRequest,
    "inventory_snapshots": InventorySnapshotCreateRequest,
    "product_identifiers": ProductIdentifierCreateRequest,
}
ALIASES = {
    "sku": {"product_sku", "item_sku", "product_code"},
    "name": {"product_name", "item_name", "title"},
    "manufacturer": {"manufacturer_name", "mfr"},
    "part_number": {"mpn", "manufacturer_part_number", "mfr_part_number"},
    "category": {"product_category", "category_name"},
    "variant_sku": {"sku", "variant_code"},
    "supplier_sku": {"vendor_sku", "supplier_item_code"},
    "supplier_id": {"vendor_id"},
    "product_id": {"catalog_product_id"},
    "warehouse_code": {"warehouse", "location_code"},
    "quantity_on_hand": {"on_hand", "stock_on_hand"},
    "quantity_reserved": {"reserved_quantity"},
    "quantity_available": {"available_quantity", "available_stock"},
    "identifier_type": {"id_type", "barcode_type"},
    "value": {"identifier_value", "barcode", "gtin", "ean", "upc"},
    "unit_price": {"price", "cost"},
    "currency": {"currency_code"},
    "minimum_order_quantity": {"moq"},
    "lead_time_days": {"lead_time"},
}


class RecordMappingError(ValueError):
    pass


@dataclass(frozen=True)
class RecordImportResult:
    record_type: str
    total_records: int
    valid_records: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    mappings: list[dict[str, Any]]
    unmapped_headers: list[str]
    field_completeness: list[dict[str, Any]]

    @property
    def invalid_records(self) -> int:
        return self.total_records - len(self.valid_records)


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().casefold()).strip("_")


def _resolve_mapping(
    record_type: str,
    headers: list[str],
    manual_mapping: dict[str, str] | None,
) -> tuple[dict[str, str], list[str], list[dict[str, Any]]]:
    if record_type not in RECORD_MODELS:
        raise RecordMappingError("Unsupported catalog record type.")
    allowed = set(RECORD_MODELS[record_type].model_fields)
    if manual_mapping is not None:
        if set(manual_mapping) - allowed:
            raise RecordMappingError("Manual mapping contains fields not allowed for this record type.")
        if any(source not in headers for source in manual_mapping.values()):
            raise RecordMappingError("Manual mapping references a source header that does not exist.")
        if len(set(manual_mapping.values())) != len(manual_mapping):
            raise RecordMappingError("A source column cannot map to multiple canonical fields.")
        mapping = dict(manual_mapping)
        confidence = 1.0
    else:
        mapping: dict[str, str] = {}
        used: set[str] = set()
        for header in headers:
            normalized = _normalize(header)
            candidate = normalized if normalized in allowed else None
            if candidate is None:
                candidate = next(
                    (field for field in allowed if normalized in ALIASES.get(field, set())),
                    None,
                )
            if candidate is None:
                continue
            if candidate in mapping or header in used:
                raise RecordMappingError(
                    f"Ambiguous source columns map to '{candidate}'. Supply a manual mapping."
                )
            mapping[candidate] = header
            used.add(header)
        confidence = 0.95

    required = {
        name for name, field in RECORD_MODELS[record_type].model_fields.items()
        if field.is_required()
    }
    mapped_sources = set(mapping.values())
    details = [
        {"field": field, "source_header": source, "confidence": confidence}
        for field, source in mapping.items()
    ]
    unmapped = [header for header in headers if header not in mapped_sources]
    if record_type == "product_variants":
        unmapped = [header for header in unmapped if not header.startswith("attributes.")]
    return mapping, unmapped, details


def validate_parsed_records(
    parsed: ParsedSource,
    record_type: str,
    manual_mapping: dict[str, str] | None = None,
    *,
    error_limit: int = 500,
) -> RecordImportResult:
    mapping, unmapped, mapping_details = _resolve_mapping(
        record_type, parsed.headers, manual_mapping
    )
    model = RECORD_MODELS[record_type]
    valid: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen: dict[tuple[Any, ...], str] = {}
    populated: Counter[str] = Counter()
    required_fields = [
        name for name, field in model.model_fields.items() if field.is_required()
    ]

    for record in parsed.records:
        row = {
            field: record.values.get(source)
            for field, source in mapping.items()
            if source in record.values
        }
        if "attributes" in model.model_fields:
            attributes = row.get("attributes")
            if isinstance(attributes, str):
                import json
                try:
                    row["attributes"] = json.loads(attributes)
                except json.JSONDecodeError:
                    pass
            nested_attributes = {
                key.removeprefix("attributes."): value
                for key, value in record.values.items()
                if key.startswith("attributes.")
            }
            if nested_attributes:
                row["attributes"] = nested_attributes
        for field in required_fields:
            if row.get(field) not in (None, ""):
                populated[field] += 1
        try:
            parsed_model = model.model_validate(row)
        except ValidationError as exc:
            if len(errors) < error_limit:
                for detail in exc.errors():
                    errors.append({
                        "source_location": record.source_location,
                        "field": ".".join(str(part) for part in detail.get("loc", ())) or None,
                        "error_code": str(detail.get("type", "invalid_value")).upper(),
                        "message": detail.get("msg", "Invalid value."),
                    })
                    if len(errors) >= error_limit:
                        break
            continue

        values = parsed_model.model_dump(mode="json")
        duplicate_key: tuple[Any, ...] | None = None
        if record_type == "products":
            duplicate_key = ("sku", str(values["sku"]).casefold())
        elif record_type == "product_variants" and values.get("variant_sku"):
            duplicate_key = ("variant_sku", str(values["variant_sku"]).casefold())
        elif record_type == "supplier_offers" and values.get("supplier_sku"):
            duplicate_key = ("supplier_sku", str(values["supplier_id"]), str(values["supplier_sku"]).casefold())
        elif record_type == "product_identifiers":
            duplicate_key = (
                "identifier", values["identifier_type"], values.get("namespace", "global"),
                str(values["value"]).casefold(),
            )
        if duplicate_key and duplicate_key in seen:
            if len(errors) < error_limit:
                errors.append({
                    "source_location": record.source_location,
                    "field": duplicate_key[0],
                    "error_code": "DUPLICATE_IN_FILE",
                    "message": f"Duplicate key matches {seen[duplicate_key]}.",
                })
            continue
        if duplicate_key:
            seen[duplicate_key] = record.source_location
        valid.append(values)

    completeness = [
        {
            "field": field,
            "populated": populated[field],
            "missing": len(parsed.records) - populated[field],
            "completeness_pct": round(populated[field] / len(parsed.records) * 100, 2)
            if parsed.records else 100.0,
        }
        for field in required_fields
    ]
    return RecordImportResult(
        record_type=record_type,
        total_records=len(parsed.records),
        valid_records=valid,
        errors=errors,
        mappings=mapping_details,
        unmapped_headers=unmapped,
        field_completeness=completeness,
    )
