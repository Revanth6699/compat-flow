import csv
import io
from dataclasses import dataclass

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas import HealthResponse, ImportPreviewResponse
from app.services.catalog_csv import (
    CatalogCSVValidationError,
    parse_catalog_csv,
)

router = APIRouter()

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok",
        service="compatflow-api",
    )


@router.post(
    "/catalog/import/preview",
    response_model=ImportPreviewResponse,
)
async def preview_catalog_import(file: UploadFile = File(...)):
    filename = (file.filename or "").strip()

    if not filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=415,
            detail="Only CSV files are supported in this preview.",
        )

    raw = await file.read(MAX_UPLOAD_BYTES + 1)

    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail="File exceeds the 5 MB limit.",
        )

    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="CSV must be UTF-8 encoded.",
        ) from None

    try:
        result = parse_catalog_csv(content)

    except CatalogCSVValidationError as exc:
        message = str(exc)

        status_code = (
            413 if "row limit" in message else 422
        )

        raise HTTPException(
            status_code=status_code,
            detail=message,
        ) from None

    except csv.Error:
        raise HTTPException(
            status_code=400,
            detail="CSV could not be parsed.",
        ) from None

    return ImportPreviewResponse(
        filename=filename,
        total_rows=result.total_rows,
        valid_rows=result.valid_count,
        invalid_rows=result.invalid_count,
        errors=result.errors[:50],
        preview=result.preview,
    )
