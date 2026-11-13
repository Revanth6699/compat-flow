import csv

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.auth import AuthenticatedUser, require_permission, require_plan_feature
from app.core.database import get_db
from app.models import Product, Supplier
from app.core.config import settings
from app.schemas import (
    HealthResponse,
    ImportPreviewResponse,
    ImportPreviewRowErrorResponse,
    ImportIssueCategoryResponse,
    ImportFieldMetricResponse,
    ImportColumnMappingResponse,
    ProductResponse,
    ProductCreateRequest,
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


async def _validate_catalog_csv(file: UploadFile) -> ImportPreviewResponse:
    filename = (file.filename or "").strip()
    if not filename.lower().endswith(".csv"):
        await file.close()
        raise HTTPException(status_code=415, detail="Only CSV files are supported.")
    if len(filename) > 255:
        await file.close()
        raise HTTPException(status_code=400, detail="Filename must not exceed 255 characters.")

    try:
        raw = await file.read(settings.import_max_upload_bytes + 1)
    finally:
        await file.close()

    if len(raw) > settings.import_max_upload_bytes:
        raise HTTPException(status_code=413, detail="File exceeds the configured upload limit.")
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded CSV is empty.")
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded.") from None

    try:
        result = parse_catalog_csv(content)
    except CatalogCSVValidationError as exc:
        message = str(exc)
        status_code = 413 if "row limit" in message else 422
        raise HTTPException(status_code=status_code, detail=message) from None
    except csv.Error:
        raise HTTPException(status_code=400, detail="CSV could not be parsed. Check quoting and delimiters.") from None

    return ImportPreviewResponse(
        filename=filename,
        total_rows=result.total_rows,
        valid_rows=result.valid_count,
        invalid_rows=result.invalid_count,
        validation_pass_rate=result.validation_pass_rate,
        data_quality_score=result.data_quality_score,
        total_issues=result.critical_issues + result.warning_issues,
        critical_issues=result.critical_issues,
        warning_issues=result.warning_issues,
        errors=result.errors[:50],
        issue_categories=[
            ImportIssueCategoryResponse(category=category, count=count)
            for category, count in result.issue_categories
        ],
        field_metrics=[
            ImportFieldMetricResponse(
                field=metric.field,
                populated=metric.populated,
                missing=metric.missing,
                completeness_pct=metric.completeness_pct,
            )
            for metric in result.field_metrics
        ],
        column_mappings=[
            ImportColumnMappingResponse(
                field=mapping.field,
                source_header=mapping.source_header,
                confidence=mapping.confidence,
            )
            for mapping in result.column_mappings
        ],
        unmapped_headers=result.unmapped_headers,
        preview=result.preview,
        row_errors=[
            ImportPreviewRowErrorResponse(
                row_number=error.row_number,
                field=error.field,
                error_code=error.error_code,
                message=error.message,
                severity=error.severity,
                category=error.category,
                recommendation=error.recommendation,
            )
            for error in result.row_errors[:50]
        ],
    )


@router.post("/catalog/import/validate", response_model=ImportPreviewResponse)
async def validate_paid_catalog_import(
    file: UploadFile = File(...),
    _plan: AuthenticatedUser = Depends(require_plan_feature("csv_validation")),
):
    """Authenticated, subscription-gated validation. Files are not persisted."""
    return await _validate_catalog_csv(file)


@router.post("/catalog/import/preview", response_model=ImportPreviewResponse)
async def preview_catalog_import(file: UploadFile = File(...)):
    """Public stateless demo validation. Files are not persisted."""
    return await _validate_catalog_csv(file)


@router.post("/catalog/import")
def public_demo_import_disabled():
    raise HTTPException(
        status_code=403,
        detail=(
            "Persistent catalog imports are disabled in this demo. "
            "You can validate and preview your CSV without saving it."
        ),
    )


@router.get("/suppliers", response_model=list[SupplierResponse])
def list_suppliers(
    current: AuthenticatedUser = Depends(require_permission("supplier:read")),
    _plan: AuthenticatedUser = Depends(require_plan_feature("supplier_catalogs")),
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
    _plan: AuthenticatedUser = Depends(require_plan_feature("supplier_catalogs")),
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
    _plan: AuthenticatedUser = Depends(require_plan_feature("supplier_catalogs")),
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
    _plan: AuthenticatedUser = Depends(require_plan_feature("supplier_catalogs")),
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


@router.post("/products", response_model=ProductResponse, status_code=201)
def create_product(
    payload: ProductCreateRequest,
    current: AuthenticatedUser = Depends(require_permission("catalog:write")),
    _plan: AuthenticatedUser = Depends(require_plan_feature("supplier_catalogs")),
    db: Session = Depends(get_db),
):
    if payload.supplier_id is not None:
        supplier = db.scalar(
            select(Supplier).where(
                Supplier.id == payload.supplier_id,
                Supplier.organization_id == current.profile.organization_id,
            )
        )
        if supplier is None:
            raise HTTPException(status_code=404, detail="Supplier not found.")

    product = Product(
        organization_id=current.profile.organization_id,
        supplier_id=payload.supplier_id,
        sku=payload.sku.strip(),
        name=payload.name.strip(),
        manufacturer=payload.manufacturer.strip(),
        part_number=payload.part_number.strip(),
        category=payload.category.strip(),
        replacement_sku=payload.replacement_sku.strip() if payload.replacement_sku else None,
    )
    db.add(product)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if "uq_products_org_sku" in str(exc):
            raise HTTPException(status_code=409, detail="A product with this SKU already exists in the organization.") from None
        raise
    db.refresh(product)
    return product
