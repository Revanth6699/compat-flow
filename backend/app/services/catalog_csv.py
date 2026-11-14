import csv
import io
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

from pydantic import ValidationError

from app.schemas import ImportPreviewRow


MAX_ROWS = 10_000
PREVIEW_LIMIT = 10
ERROR_LIMIT = 500

# Canonical product-catalog fields and common supplier/export header variants.
# Alias confidence is deliberately conservative: it is a mapping confidence,
# not a claim about the correctness of the underlying product data.
HEADER_ALIASES = {
    "sku": {
        "sku": 1.0, "product_sku": 0.98, "item_sku": 0.98,
        "product_code": 0.96, "item_code": 0.96, "item_number": 0.92,
        "part_id": 0.90, "stock_code": 0.90,
    },
    "name": {
        "name": 1.0, "product_name": 0.99, "item_name": 0.98,
        "title": 0.94, "product_title": 0.98, "description": 0.82,
        "short_description": 0.80,
    },
    "manufacturer": {
        "manufacturer": 1.0, "manufacturer_name": 0.99, "mfr": 0.97,
        "maker": 0.94, "brand": 0.88, "brand_name": 0.88,
    },
    "part_number": {
        "part_number": 1.0, "manufacturer_part_number": 0.99,
        "mfr_part_number": 0.98, "mpn": 0.98, "part_no": 0.96,
        "model_number": 0.90, "model_no": 0.88,
    },
    "category": {
        "category": 1.0, "product_category": 0.99, "category_name": 0.98,
        "product_type": 0.92, "item_type": 0.88,
    },
    "compatibility": {
        "compatibility": 1.0, "compatible_with": 0.98,
        "fits": 0.92, "vehicle_fitment": 0.90,
    },
    "replacement_sku": {
        "replacement_sku": 1.0, "supersedes_sku": 0.96,
        "alternate_sku": 0.92, "replacement_item": 0.86,
    },
}
REQUIRED_FIELDS = ("sku", "name", "manufacturer", "part_number", "category")
CATALOG_PROFILES = {
    "general": ("sku", "name", "manufacturer", "part_number", "category"),
    "automotive": ("sku", "name", "manufacturer", "part_number", "compatibility"),
    "electronics": ("sku", "name", "manufacturer", "part_number", "category", "replacement_sku"),
    "industrial": ("sku", "name", "manufacturer", "part_number", "category"),
}


class CatalogCSVValidationError(ValueError):
    """Raised when a CSV file has an invalid or ambiguous structure."""


@dataclass(frozen=True)
class CatalogCSVRowError:
    row_number: int
    field: str | None
    error_code: str
    message: str
    severity: str = "critical"
    category: str = "data_integrity"
    recommendation: str = "Review the value and correct it at the source."


@dataclass(frozen=True)
class CatalogCSVFieldMetric:
    field: str
    populated: int
    missing: int
    completeness_pct: float


@dataclass(frozen=True)
class CatalogCSVColumnMapping:
    field: str
    source_header: str
    confidence: float


@dataclass
class CatalogCSVResult:
    total_rows: int
    valid_rows: list[ImportPreviewRow]
    errors: list[str]
    row_errors: list[CatalogCSVRowError]
    valid_row_numbers: list[int]
    field_metrics: list[CatalogCSVFieldMetric]
    issue_categories: list[tuple[str, int]]
    column_mappings: list[CatalogCSVColumnMapping]
    unmapped_headers: list[str]
    validation_pass_rate: float
    data_quality_score: float
    critical_issues: int
    warning_issues: int
    profile_id: str = "general"
    records_with_issues: int = 0
    duplicate_sku_count: int = 0
    duplicate_rate: float = 0.0
    issue_density: float = 0.0
    critical_record_rate: float = 0.0

    @property
    def valid_count(self) -> int:
        return len(self.valid_rows)

    @property
    def invalid_count(self) -> int:
        return self.total_rows - self.valid_count

    @property
    def preview(self) -> list[ImportPreviewRow]:
        return self.valid_rows[:PREVIEW_LIMIT]


def _normalize_header(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).strip().casefold()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def _detect_columns(headers: list[str], required_fields=REQUIRED_FIELDS, column_mapping=None):
    normalized = [_normalize_header(header or "") for header in headers]
    if any(not header for header in normalized):
        raise CatalogCSVValidationError("CSV contains an empty column header.")
    if len(normalized) != len(set(normalized)):
        raise CatalogCSVValidationError(
            "CSV contains duplicate column headers after normalization."
        )

    alias_lookup = {
        alias: (field, confidence)
        for field, aliases in HEADER_ALIASES.items()
        for alias, confidence in aliases.items()
    }
    detected: dict[str, tuple[int, float]] = {}
    unmapped = []
    for index, header in enumerate(normalized):
        match = alias_lookup.get(header)
        if match is None:
            unmapped.append(headers[index])
            continue
        field, confidence = match
        if field in detected:
            previous_index, _ = detected[field]
            raise CatalogCSVValidationError(
                f"Ambiguous column mapping: '{headers[previous_index]}' and "
                f"'{headers[index]}' both map to '{field}'. Rename one column "
                "or provide a single unambiguous source column."
            )
        detected[field] = (index, confidence)

    if column_mapping is not None:
        allowed = set(HEADER_ALIASES)
        if set(column_mapping) - allowed:
            raise CatalogCSVValidationError("Manual mapping contains unsupported canonical fields.")
        indexes = {header: index for index, header in enumerate(headers)}
        selected = {}
        for field, source_header in column_mapping.items():
            if not isinstance(source_header, str) or source_header not in indexes:
                raise CatalogCSVValidationError(f"Mapped source column '{source_header}' does not exist.")
            selected[field] = (indexes[source_header], 1.0)
        target_indexes = [value[0] for value in selected.values()]
        if len(target_indexes) != len(set(target_indexes)):
            raise CatalogCSVValidationError("A source column cannot be mapped to more than one canonical field.")
        detected = selected
        unmapped = [header for index, header in enumerate(headers) if index not in target_indexes]

    missing = [field for field in required_fields if field not in detected]
    if missing:
        raise CatalogCSVValidationError(
            "Could not map required product fields: "
            + ", ".join(missing)
            + ". Recognized headers include common aliases such as product_sku, "
              "product_name, brand, mpn and product_category. Rename or map the "
              "missing source columns before validating."
        )

    mappings = [
        CatalogCSVColumnMapping(field, headers[index], confidence)
        for field, (index, confidence) in detected.items()
    ]
    return normalized, detected, mappings, unmapped


def parse_catalog_csv(content: str, max_rows: int = MAX_ROWS, profile_id: str = "general", column_mapping: dict[str, str] | None = None) -> CatalogCSVResult:
    if profile_id not in CATALOG_PROFILES:
        raise CatalogCSVValidationError(f"Unknown catalog profile '{profile_id}'.")
    required_fields = CATALOG_PROFILES[profile_id]
    stream = io.StringIO(content, newline="")
    reader = csv.reader(stream, strict=True)
    headers = next(reader, None)
    if not headers:
        raise CatalogCSVValidationError("CSV header row is missing.")

    normalized_headers, detected, mappings, unmapped_headers = _detect_columns(headers, required_fields, column_mapping)
    valid_rows = []
    valid_row_numbers = []
    errors = []
    row_errors = []
    seen_skus = {}
    seen_part_numbers = {}
    field_populated = Counter()
    total_rows = 0

    def add_issue(row_number, field, code, message, severity, category, recommendation):
        row_errors.append(CatalogCSVRowError(
            row_number=row_number, field=field, error_code=code, message=message,
            severity=severity, category=category, recommendation=recommendation,
        ))
        if len(errors) < ERROR_LIMIT:
            errors.append(f"Row {row_number}: {message}")

    for line_number, values in enumerate(reader, start=2):
        if not values or all(not value.strip() for value in values):
            continue
        total_rows += 1
        if total_rows > max_rows:
            raise CatalogCSVValidationError(f"CSV exceeds the {max_rows:,}-row limit.")

        if len(values) != len(normalized_headers):
            add_issue(
                line_number, None, "COLUMN_COUNT_MISMATCH",
                f"Expected {len(normalized_headers)} columns but found {len(values)}.",
                "critical", "file_structure",
                "Check delimiters and quoted values so each record has the same "
                "number of columns as the header.",
            )
            continue

        source_row = {
            header: (value or "").strip()
            for header, value in zip(normalized_headers, values)
        }
        row = {
            field: source_row[normalized_headers[index]]
            for field, (index, _) in detected.items()
        }
        for field in required_fields:
            if row.get(field, "").strip():
                field_populated[field] += 1

        missing_profile_fields = [field for field in required_fields if not row.get(field, "").strip()]
        if missing_profile_fields:
            for field in missing_profile_fields:
                add_issue(line_number, field, "PROFILE_REQUIRED_FIELD_MISSING",
                    f"Required field '{field}' is empty for the {profile_id} profile.",
                    "critical", "field_validation",
                    f"Provide a non-empty {field} value for this profile.")
            continue

        try:
            parsed = ImportPreviewRow.model_validate(row)
        except ValidationError as exc:
            for detail in exc.errors():
                location = detail.get("loc", ())
                field = str(location[0]) if location else None
                if field not in REQUIRED_FIELDS and field not in ("compatibility", "replacement_sku"):
                    field = None
                code = str(detail.get("type", "invalid_value")).upper().replace(".", "_")
                if field:
                    message = (
                        f"Required field '{field}' is empty or exceeds its allowed length."
                        if field in REQUIRED_FIELDS
                        else f"Optional field '{field}' exceeds its allowed length."
                    )
                    recommendation = (
                        f"Provide a non-empty {field} value within the documented field length."
                        if field in REQUIRED_FIELDS
                        else f"Shorten or remove the {field} value."
                    )
                else:
                    message = "Record contains an invalid product value."
                    recommendation = "Review the mapped product fields and correct the record."
                add_issue(line_number, field, code, message, "critical", "field_validation", recommendation)
            continue

        sku_key = parsed.sku.casefold()
        if sku_key in seen_skus:
            add_issue(
                line_number, "sku", "DUPLICATE_SKU_IN_FILE",
                f"Duplicate SKU '{parsed.sku}' matches row {seen_skus[sku_key]}.",
                "critical", "duplicate_identifier",
                "Confirm which record is authoritative and provide a unique SKU.",
            )
            continue
        seen_skus[sku_key] = line_number

        part_key = (parsed.manufacturer.casefold(), parsed.part_number.casefold())
        if part_key in seen_part_numbers:
            add_issue(
                line_number, "part_number", "DUPLICATE_MANUFACTURER_PART_NUMBER",
                f"Manufacturer and part number combination duplicates row {seen_part_numbers[part_key]}.",
                "warning", "possible_duplicate",
                "Confirm whether these records represent the same product or legitimate variants.",
            )
        else:
            seen_part_numbers[part_key] = line_number

        valid_rows.append(parsed)
        valid_row_numbers.append(line_number)

    field_metrics = []
    for field in REQUIRED_FIELDS:
        populated = field_populated[field]
        missing_count = total_rows - populated
        pct = round((populated / total_rows) * 100, 2) if total_rows else 100.0
        field_metrics.append(CatalogCSVFieldMetric(field, populated, missing_count, pct))

    critical = sum(issue.severity == "critical" for issue in row_errors)
    records_with_issues = len({issue.row_number for issue in row_errors})
    duplicate_sku_count = sum(issue.error_code == "DUPLICATE_SKU_IN_FILE" for issue in row_errors)
    critical_records = len({issue.row_number for issue in row_errors if issue.severity == "critical"})
    warnings = sum(issue.severity == "warning" for issue in row_errors)
    pass_rate = round((len(valid_rows) / total_rows) * 100, 2) if total_rows else 100.0
    completeness = (
        sum(metric.completeness_pct for metric in field_metrics) / len(field_metrics)
        if field_metrics else 100.0
    )
    # Explicit heuristic, not model accuracy: 70% accepted-record rate and
    # 30% required-field completeness. Warning-only records remain accepted.
    quality_score = round((pass_rate * 0.7) + (completeness * 0.3), 2)
    categories = Counter(issue.category for issue in row_errors)

    return CatalogCSVResult(
        total_rows=total_rows,
        valid_rows=valid_rows,
        errors=errors,
        row_errors=row_errors[:ERROR_LIMIT],
        valid_row_numbers=valid_row_numbers,
        field_metrics=field_metrics,
        issue_categories=sorted(categories.items(), key=lambda item: (-item[1], item[0])),
        column_mappings=mappings,
        unmapped_headers=unmapped_headers,
        validation_pass_rate=pass_rate,
        data_quality_score=quality_score,
        critical_issues=critical,
        warning_issues=warnings,
        profile_id=profile_id,
        records_with_issues=records_with_issues,
        duplicate_sku_count=duplicate_sku_count,
        duplicate_rate=round(duplicate_sku_count / total_rows * 100, 2) if total_rows else 0.0,
        issue_density=round((critical + warnings) / total_rows, 3) if total_rows else 0.0,
        critical_record_rate=round(critical_records / total_rows * 100, 2) if total_rows else 0.0,
    )
