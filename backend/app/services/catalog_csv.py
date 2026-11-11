
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


@dataclass
class CatalogCSVResult:
    total_rows: int
    valid_rows: list[ImportPreviewRow]
    errors: list[str]

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
    errors = []
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
            errors.append(
                f"Row {line_number}: expected "
                f"{len(normalized_headers)} columns, "
                f"received {len(values)}."
            )
            continue

        row = {
            header: value.strip()
            for header, value in zip(normalized_headers, values)
        }

        try:
            parsed = ImportPreviewRow.model_validate(row)
        except ValidationError:
            errors.append(
                f"Row {line_number}: invalid or missing required value."
            )
            continue

        sku_key = parsed.sku.casefold()

        if sku_key in seen_skus:
            errors.append(
                f"Row {line_number}: duplicate SKU '{parsed.sku}'."
            )
            continue

        seen_skus.add(sku_key)
        valid_rows.append(parsed)

    return CatalogCSVResult(
        total_rows=total_rows,
        valid_rows=valid_rows,
        errors=errors,
    )
