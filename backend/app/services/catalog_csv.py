import csv
import io
from collections import Counter
from dataclasses import dataclass

from pydantic import ValidationError

from app.schemas import ImportPreviewRow


REQUIRED_COLUMNS = {"sku", "name", "manufacturer", "part_number", "category"}
REQUIRED_FIELDS = ("sku", "name", "manufacturer", "part_number", "category")
MAX_ROWS = 10_000
PREVIEW_LIMIT = 10
ERROR_LIMIT = 500


class CatalogCSVValidationError(ValueError):
    """Raised when a CSV file has an invalid header or structure."""


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


@dataclass
class CatalogCSVResult:
    total_rows: int
    valid_rows: list[ImportPreviewRow]
    errors: list[str]
    row_errors: list[CatalogCSVRowError]
    valid_row_numbers: list[int]
    field_metrics: list[CatalogCSVFieldMetric]
    issue_categories: list[tuple[str, int]]
    validation_pass_rate: float
    data_quality_score: float
    critical_issues: int
    warning_issues: int

    @property
    def valid_count(self) -> int:
        return len(self.valid_rows)

    @property
    def invalid_count(self) -> int:
        return self.total_rows - self.valid_count

    @property
    def preview(self) -> list[ImportPreviewRow]:
        return self.valid_rows[:PREVIEW_LIMIT]


def parse_catalog_csv(content: str, max_rows: int = MAX_ROWS) -> CatalogCSVResult:
    stream = io.StringIO(content, newline="")
    reader = csv.reader(stream, strict=True)
    headers = next(reader, None)
    if not headers:
        raise CatalogCSVValidationError("CSV header row is missing.")

    normalized_headers = [(header or "").strip().lower() for header in headers]
    if any(not header for header in normalized_headers):
        raise CatalogCSVValidationError("CSV contains an empty column header.")
    if len(normalized_headers) != len(set(normalized_headers)):
        raise CatalogCSVValidationError("CSV contains duplicate column headers.")

    missing = REQUIRED_COLUMNS - set(normalized_headers)
    if missing:
        raise CatalogCSVValidationError(
            f"Missing required columns: {', '.join(sorted(missing))}"
        )

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
                "Make sure every record has the same number of columns as the header.",
            )
            continue

        row = {header: value.strip() for header, value in zip(normalized_headers, values)}
        for field in REQUIRED_FIELDS:
            if row.get(field, "").strip():
                field_populated[field] += 1

        try:
            parsed = ImportPreviewRow.model_validate(row)
        except ValidationError as exc:
            for detail in exc.errors():
                location = detail.get("loc", ())
                field = str(location[0]) if location else None
                if field not in normalized_headers:
                    field = None
                code = str(detail.get("type", "invalid_value")).upper().replace(".", "_")
                if field:
                    message = f"Required field '{field}' is empty or violates its allowed length."
                    recommendation = f"Provide a non-empty {field} value within the documented field length."
                else:
                    message = "Record contains an invalid required value."
                    recommendation = "Review required product fields and correct the record."
                add_issue(line_number, field, code, message, "critical", "required_field", recommendation)
            continue

        sku_key = parsed.sku.casefold()
        if sku_key in seen_skus:
            add_issue(
                line_number, "sku", "DUPLICATE_SKU_IN_FILE",
                f"SKU '{parsed.sku}' duplicates row {seen_skus[sku_key]}.",
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
    warnings = sum(issue.severity == "warning" for issue in row_errors)
    pass_rate = round((len(valid_rows) / total_rows) * 100, 2) if total_rows else 100.0
    completeness = (
        sum(metric.completeness_pct for metric in field_metrics) / len(field_metrics)
        if field_metrics else 100.0
    )
    # Transparent heuristic: 70% record acceptance + 30% required-field completeness.
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
        validation_pass_rate=pass_rate,
        data_quality_score=quality_score,
        critical_issues=critical,
        warning_issues=warnings,
    )
