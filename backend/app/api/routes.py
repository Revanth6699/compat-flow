import csv
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.auth import AuthenticatedUser, require_permission, require_plan_feature
from app.core.database import get_db
from app.models import InventorySnapshot, Product, ProductIdentifier, ProductVariant, Supplier, SupplierOffer
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
    ProductVariantCreateRequest,
    ProductVariantResponse,
    SupplierOfferCreateRequest,
    SupplierOfferResponse,
    InventorySnapshotCreateRequest,
    InventorySnapshotResponse,
    ProductIdentifierCreateRequest,
    ProductIdentifierResponse,
)
from app.services.ingestion_adapters import IngestionParseError, parse_source\nfrom app.services.catalog_csv import (
    CatalogCSVValidationError,
    CATALOG_PROFILES,
    parse_catalog_csv,
)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", service="compatflow-api")


async def _validate_catalog_csv(file: UploadFile, profile_id: str = "general", column_mapping=None) -> ImportPreviewResponse:
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
        result = parse_catalog_csv(content, profile_id=profile_id, column_mapping=column_mapping, allow_incomplete_mapping=column_mapping is None)
    except CatalogCSVValidationError as exc:
        message = str(exc)
        status_code = 413 if "row limit" in message else 422
        raise HTTPException(status_code=status_code, detail=message) from None
    except csv.Error:
        raise HTTPException(status_code=400, detail="CSV could not be parsed. Check quoting and delimiters.") from None

    return ImportPreviewResponse(
        filename=filename,
        profile_id=result.profile_id,
        records_with_issues=result.records_with_issues,
        duplicate_sku_count=result.duplicate_sku_count,
        duplicate_rate=result.duplicate_rate,
        issue_density=result.issue_density,
        critical_record_rate=result.critical_record_rate,
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
    profile_id: str = Form("general"),
    column_mapping_json: str | None = Form(None),
    _plan: AuthenticatedUser = Depends(require_plan_feature("csv_validation")),
):
    """Authenticated, subscription-gated validation. Files are not persisted."""
    if profile_id not in CATALOG_PROFILES:
        await file.close()
        raise HTTPException(status_code=422, detail="Unknown catalog profile.")
    try:
        mapping = json.loads(column_mapping_json) if column_mapping_json else None
        if mapping is not None and (not isinstance(mapping, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in mapping.items())):
            raise ValueError
    except (ValueError, TypeError):
        await file.close()
        raise HTTPException(status_code=422, detail="Manual mapping must be a JSON object of canonical fields to source headers.") from None
    return await _validate_catalog_csv(file, profile_id, mapping)


@router.post("/catalog/import/preview", response_model=ImportPreviewResponse)
async def preview_catalog_import(
    file: UploadFile = File(...),
    profile_id: str = Form("general"),
    column_mapping_json: str | None = Form(None),
):
    """Public stateless demo validation. Files are not persisted."""
    if profile_id not in CATALOG_PROFILES:
        await file.close()
        raise HTTPException(status_code=422, detail="Unknown catalog profile.")
    try:
        mapping = json.loads(column_mapping_json) if column_mapping_json else None
        if mapping is not None and (not isinstance(mapping, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in mapping.items())):
            raise ValueError
    except (ValueError, TypeError):
        await file.close()
        raise HTTPException(status_code=422, detail="Manual mapping must be a JSON object of canonical fields to source headers.") from None
    return await _validate_catalog_csv(file, profile_id, mapping)


@router.post("/catalog/import")
def public_demo_import_disabled():
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


@router.get("/product-variants", response_model=list[ProductVariantResponse])
def list_product_variants(
    current: AuthenticatedUser = Depends(require_permission("catalog:read")),
    _plan: AuthenticatedUser = Depends(require_plan_feature("supplier_catalogs")),
    db: Session = Depends(get_db),
):
    return list(db.scalars(
        select(ProductVariant)
        .where(ProductVariant.organization_id == current.profile.organization_id)
        .order_by(ProductVariant.created_at.desc())
        .limit(500)
    ).all())


@router.post("/product-variants", response_model=ProductVariantResponse, status_code=201)
def create_product_variant(
    payload: ProductVariantCreateRequest,
    current: AuthenticatedUser = Depends(require_permission("catalog:write")),
    _plan: AuthenticatedUser = Depends(require_plan_feature("supplier_catalogs")),
    db: Session = Depends(get_db),
):
    organization_id = current.profile.organization_id
    product = db.scalar(select(Product.id).where(
        Product.id == payload.product_id,
        Product.organization_id == organization_id,
    ))
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")
    variant = ProductVariant(
        organization_id=organization_id,
        product_id=payload.product_id,
        variant_sku=payload.variant_sku.strip() if payload.variant_sku else None,
        attributes=payload.attributes,
        is_active=payload.is_active,
    )
    db.add(variant)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A variant with this SKU already exists in the organization.") from None
    db.refresh(variant)
    return variant


@router.get("/supplier-offers", response_model=list[SupplierOfferResponse])
def list_supplier_offers(
    current: AuthenticatedUser = Depends(require_permission("catalog:read")),
    _plan: AuthenticatedUser = Depends(require_plan_feature("supplier_catalogs")),
    db: Session = Depends(get_db),
):
    return list(db.scalars(
        select(SupplierOffer)
        .where(SupplierOffer.organization_id == current.profile.organization_id)
        .order_by(SupplierOffer.created_at.desc())
        .limit(500)
    ).all())


@router.post("/supplier-offers", response_model=SupplierOfferResponse, status_code=201)
def create_supplier_offer(
    payload: SupplierOfferCreateRequest,
    current: AuthenticatedUser = Depends(require_permission("catalog:write")),
    _plan: AuthenticatedUser = Depends(require_plan_feature("supplier_catalogs")),
    db: Session = Depends(get_db),
):
    organization_id = current.profile.organization_id
    supplier = db.scalar(select(Supplier.id).where(
        Supplier.id == payload.supplier_id,
        Supplier.organization_id == organization_id,
    ))
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found.")
    if payload.product_id is not None:
        product = db.scalar(select(Product.id).where(
            Product.id == payload.product_id,
            Product.organization_id == organization_id,
        ))
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found.")
    offer = SupplierOffer(
        organization_id=organization_id,
        supplier_id=payload.supplier_id,
        product_id=payload.product_id,
        supplier_sku=payload.supplier_sku.strip() if payload.supplier_sku else None,
        supplier_product_id=payload.supplier_product_id.strip() if payload.supplier_product_id else None,
        unit_price=payload.unit_price,
        currency=payload.currency,
        unit_of_measure=payload.unit_of_measure,
        minimum_order_quantity=payload.minimum_order_quantity,
        lead_time_days=payload.lead_time_days,
        source_url=payload.source_url,
        status=payload.status,
    )
    db.add(offer)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This supplier already has an offer with that supplier SKU.") from None
    db.refresh(offer)
    return offer


@router.get("/inventory-snapshots", response_model=list[InventorySnapshotResponse])
def list_inventory_snapshots(
    current: AuthenticatedUser = Depends(require_permission("catalog:read")),
    _plan: AuthenticatedUser = Depends(require_plan_feature("supplier_catalogs")),
    db: Session = Depends(get_db),
):
    return list(db.scalars(
        select(InventorySnapshot)
        .where(InventorySnapshot.organization_id == current.profile.organization_id)
        .order_by(InventorySnapshot.snapshot_at.desc())
        .limit(500)
    ).all())


@router.post("/inventory-snapshots", response_model=InventorySnapshotResponse, status_code=201)
def create_inventory_snapshot(
    payload: InventorySnapshotCreateRequest,
    current: AuthenticatedUser = Depends(require_permission("catalog:write")),
    _plan: AuthenticatedUser = Depends(require_plan_feature("supplier_catalogs")),
    db: Session = Depends(get_db),
):
    organization_id = current.profile.organization_id
    product = db.scalar(select(Product.id).where(
        Product.id == payload.product_id,
        Product.organization_id == organization_id,
    ))
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")
    if payload.supplier_offer_id is not None:
        offer = db.scalar(select(SupplierOffer.id).where(
            SupplierOffer.id == payload.supplier_offer_id,
            SupplierOffer.organization_id == organization_id,
            SupplierOffer.product_id == payload.product_id,
        ))
        if offer is None:
            raise HTTPException(status_code=404, detail="Supplier offer not found for this product.")
    snapshot = InventorySnapshot(
        organization_id=organization_id,
        product_id=payload.product_id,
        supplier_offer_id=payload.supplier_offer_id,
        warehouse_code=payload.warehouse_code.strip(),
        quantity_on_hand=payload.quantity_on_hand,
        quantity_reserved=payload.quantity_reserved,
        quantity_available=payload.quantity_available,
        source_reference=payload.source_reference,
        **({"snapshot_at": payload.snapshot_at} if payload.snapshot_at is not None else {}),
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


@router.get("/product-identifiers", response_model=list[ProductIdentifierResponse])
def list_product_identifiers(
    current: AuthenticatedUser = Depends(require_permission("catalog:read")),
    _plan: AuthenticatedUser = Depends(require_plan_feature("supplier_catalogs")),
    db: Session = Depends(get_db),
):
    return list(db.scalars(
        select(ProductIdentifier)
        .where(ProductIdentifier.organization_id == current.profile.organization_id)
        .order_by(ProductIdentifier.created_at.desc())
        .limit(500)
    ).all())


@router.post("/product-identifiers", response_model=ProductIdentifierResponse, status_code=201)
def create_product_identifier(
    payload: ProductIdentifierCreateRequest,
    current: AuthenticatedUser = Depends(require_permission("catalog:write")),
    _plan: AuthenticatedUser = Depends(require_plan_feature("supplier_catalogs")),
    db: Session = Depends(get_db),
):
    organization_id = current.profile.organization_id
    product = db.scalar(select(Product.id).where(
        Product.id == payload.product_id,
        Product.organization_id == organization_id,
    ))
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")
    identifier = ProductIdentifier(
        organization_id=organization_id,
        product_id=payload.product_id,
        identifier_type=payload.identifier_type,
        namespace=payload.namespace.strip(),
        value=payload.value.strip(),
        source_reference=payload.source_reference,
        is_primary=payload.is_primary,
    )
    db.add(identifier)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This identifier already exists in the organization and namespace.") from None
    db.refresh(identifier)
    return identifier
