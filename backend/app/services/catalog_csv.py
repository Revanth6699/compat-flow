
import csv
import io
from dataclasses import dataclass

from pydantic import ValidationError

from app.schemas import ImportPreviewRow


REQUIRED_COLUMNS = {
    "sku",
    "name",
    "manufacturer",
    "part_number",
    "category",
}

MAX_ROWS = 10_000
PREVIEW_LIMIT = 10


class CatalogCSVValidationError(ValueError):
    """Raised when a CSV file has an invalid header or structure."""


@dataclass(frozen=True)
class CatalogCSVRowError:
    row_number: int
    field: str | None
    error_code: str
    message: str

@dataclass
class CatalogCSVResult:
    total_rows: int
    valid_rows: list[ImportPreviewRow]
    errors: list[str]
    row_errors: list[CatalogCSVRowError]
    valid_row_numbers: list[int]

    @property
    def valid_count(self) -> int:
        return len(self.valid_rows)

    @property
    def invalid_count(self) -> int:
        return self.total_rows - self.valid_count

    @property
    def preview(self) -> list[ImportPreviewRow]:
        return self.valid_rows[:PREVIEW_LIMIT]


def parse_catalog_csv(
    content: str,
    max_rows: int = MAX_ROWS,
) -> CatalogCSVResult:
    stream = io.StringIO(content, newline="")
    reader = csv.reader(stream, strict=True)

    headers = next(reader, None)

    if not headers:
        raise CatalogCSVValidationError("CSV header row is missing.")

    normalized_headers = []

    for header in headers:
        normalized = (header or "").strip().lower()

        if not normalized:
            raise CatalogCSVValidationError(
                "CSV contains an empty column header."
            )

        normalized_headers.append(normalized)

    if len(normalized_headers) != len(set(normalized_headers)):
        raise CatalogCSVValidationError(
            "CSV contains duplicate column headers."
        )

    missing = REQUIRED_COLUMNS - set(normalized_headers)

    if missing:
        raise CatalogCSVValidationError(
            f"Missing required columns: {', '.join(sorted(missing))}"
        )

    valid_rows = []
    valid_row_numbers = []
    errors = []
    row_errors = []
    seen_skus = set()
    total_rows = 0

    for line_number, values in enumerate(reader, start=2):
        # Ignore completely blank lines.
        if not values or all(not value.strip() for value in values):
            continue

        total_rows += 1

        if total_rows > max_rows:
            raise CatalogCSVValidationError(
                f"CSV exceeds the {max_rows:,}-row limit."
            )

        if len(values) != len(normalized_headers):
            message = (
                f"Row {line_number}: expected "
                f"{len(normalized_headers)} columns, "
                f"received {len(values)}."
            )
            errors.append(message)
            row_errors.append(
                CatalogCSVRowError(
                    row_number=line_number,
                    field=None,
                    error_code="COLUMN_COUNT_MISMATCH",
                    message=message,
                )
            )
            continue

        row = {
            header: value.strip()
            for header, value in zip(normalized_headers, values)
        }

        try:
            parsed = ImportPreviewRow.model_validate(row)
        except ValidationError as exc:
            errors.append(
                f"Row {line_number}: invalid or missing required value."
            )

            for detail in exc.errors():
                location = detail.get("loc", ())
                field_name = (
                    str(location[0])
                    if location and location[0] in normalized_headers
                    else None
                )

                error_type = str(detail.get("type", "invalid_value"))
                error_code = error_type.upper().replace(".", "_")

                if field_name:
                    message = f"Invalid or missing value for field '{field_name}'."
                else:
                    message = "Invalid or missing required value."

                row_errors.append(
                    CatalogCSVRowError(
                        row_number=line_number,
                        field=field_name,
                        error_code=error_code,
                        message=message,
                    )
                )

            continue

        sku_key = parsed.sku.casefold()

        if sku_key in seen_skus:
            message = (
                f"Row {line_number}: duplicate SKU '{parsed.sku}'."
            )
            errors.append(message)
            row_errors.append(
                CatalogCSVRowError(
                    row_number=line_number,
                    field="sku",
                    error_code="DUPLICATE_SKU_IN_FILE",
                    message=message,
                )
            )
            continue

        seen_skus.add(sku_key)
        valid_rows.append(parsed)
        valid_row_numbers.append(line_number)

    return CatalogCSVResult(
        total_rows=total_rows,
        valid_rows=valid_rows,
        errors=errors,
        row_errors=row_errors,
        valid_row_numbers=valid_row_numbers,
    )
