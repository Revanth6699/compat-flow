import csv

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.auth import AuthenticatedUser, require_permission
from app.core.database import get_db
from app.models import Product, Supplier
from app.core.config import settings
from app.schemas import (
    HealthResponse,
    ImportPreviewResponse,
    ImportPreviewRowErrorResponse,
    ProductResponse,
    SupplierCreateRequest,
    SupplierResponse,
)
from app.services.catalog_csv import (
    CatalogCSVValidationError,
    parse_catalog_csv,
)

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", service="compatflow-api")


@router.post(
    "/catalog/import/preview",
    response_model=ImportPreviewResponse,
)
async def preview_catalog_import(file: UploadFile = File(...)):
    """Validate an uploaded CSV in memory; never persist or import visitor data."""
    filename = (file.filename or "").strip()

    if not filename.lower().endswith(".csv"):
        await file.close()
        raise HTTPException(
            status_code=415,
            detail="Only CSV files are supported in this preview.",
        )

    if len(filename) > 255:
        await file.close()
        raise HTTPException(
            status_code=400,
            detail="Filename must not exceed 255 characters.",
        )

    try:
       raw = await file.read(settings.import_max_upload_bytes + 1)
    finally:
        await file.close()

    if len(raw) > settings.import_max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail="File exceeds the 5 MB limit.",
        )

    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded CSV is empty.")

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
        status_code = 413 if "row limit" in message else 422
        raise HTTPException(status_code=status_code, detail=message) from None
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
        row_errors=[
            ImportPreviewRowErrorResponse(
                row_number=error.row_number,
                field=error.field,
                error_code=error.error_code,
                message=error.message,
            )
            for error in result.row_errors[:50]
        ],
    )


@router.post("/catalog/import")
def public_demo_import_disabled():
    """Persistent imports remain unavailable until authentication and tenant isolation exist."""
    raise HTTPException(
        status_code=403,
        detail=(
            "Persistent catalog imports are disabled in this public demo. "
            "You can validate and preview your CSV without saving it."
        ),
    )



@router.get("/suppliers", response_model=list[SupplierResponse])
def list_suppliers(
    current: AuthenticatedUser = Depends(require_permission("supplier:read")),
    db: Session = Depends(get_db),
):
    return list(
        db.scalars(
            select(Supplier)
            .where(Supplier.organization_id == current.profile.organization_id)
            .order_by(Supplier.name.asc())
        ).all()
    )


@router.post("/suppliers", response_model=SupplierResponse, status_code=201)
def create_supplier(
    payload: SupplierCreateRequest,
    current: AuthenticatedUser = Depends(require_permission("supplier:write")),
    db: Session = Depends(get_db),
):
    supplier = Supplier(
        organization_id=current.profile.organization_id,
        name=payload.name,
        feed_format=payload.feed_format,
    )
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.get("/products", response_model=list[ProductResponse])
def list_products(
    current: AuthenticatedUser = Depends(require_permission("catalog:read")),
    db: Session = Depends(get_db),
):
    return list(
        db.scalars(
            select(Product)
            .where(Product.organization_id == current.profile.organization_id)
            .order_by(Product.sku.asc())
            .limit(500)
        ).all()
    )


@router.get("/products/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: UUID,
    current: AuthenticatedUser = Depends(require_permission("catalog:read")),
    db: Session = Depends(get_db),
):
    product = db.scalar(
        select(Product).where(
            Product.id == product_id,
            Product.organization_id == current.profile.organization_id,
        )
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")
    return product
