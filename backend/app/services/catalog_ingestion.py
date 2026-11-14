"""Transactional persistence and source-to-catalog lineage for imports."""
from __future__ import annotations
import re
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.models import ImportJob, ImportRowError, ImportRecordLineage, Product, ProductVariant, SupplierOffer, InventorySnapshot, ProductIdentifier, Supplier
from app.schemas import ProductCreateRequest, ProductVariantCreateRequest, SupplierOfferCreateRequest, InventorySnapshotCreateRequest, ProductIdentifierCreateRequest

MODEL_BY_TYPE = {
    "products": (Product, ProductCreateRequest),
    "product_variants": (ProductVariant, ProductVariantCreateRequest),
    "supplier_offers": (SupplierOffer, SupplierOfferCreateRequest),
    "inventory_snapshots": (InventorySnapshot, InventorySnapshotCreateRequest),
    "product_identifiers": (ProductIdentifier, ProductIdentifierCreateRequest),
}

def _row_number(location: str) -> int:
    match = re.search(r"(?:row:|!row:)(\d+)", location)
    return int(match.group(1)) if match else 1

def _reference_error(db: Session, org_id: UUID, record_type: str, row: dict) -> str | None:
    refs = []
    if record_type == "products" and row.get("supplier_id"):
        refs.append((Supplier, row["supplier_id"], "Supplier"))
    if record_type in {"product_variants", "inventory_snapshots", "product_identifiers"}:
        refs.append((Product, row["product_id"], "Product"))
    if record_type == "supplier_offers":
        refs.append((Supplier, row["supplier_id"], "Supplier"))
        if row.get("product_id"):
            refs.append((Product, row["product_id"], "Product"))
    if record_type == "inventory_snapshots" and row.get("supplier_offer_id"):
        refs.append((SupplierOffer, row["supplier_offer_id"], "Supplier offer"))
    for model, value, label in refs:
        if db.scalar(select(model.id).where(model.id == value, model.organization_id == org_id)) is None:
            return f"{label} reference does not exist in this organization."
    return None

def persist_validated_import(*, db: Session, organization_id: UUID, filename: str, parsed, result):
    if result.record_type not in MODEL_BY_TYPE:
        raise HTTPException(status_code=422, detail="Unsupported catalog record type.")
    model, schema = MODEL_BY_TYPE[result.record_type]
    job = ImportJob(
        organization_id=organization_id, filename=filename,
        import_type=result.record_type, status="processing",
        row_count=result.total_records, valid_rows=0,
        invalid_rows=result.invalid_records, processed_rows=0,
    )
    db.add(job)
    db.flush()
    errors = list(result.errors)
    imported = 0
    for row, location, source_key in zip(result.valid_records, result.valid_source_locations, result.valid_source_keys):
        payload = schema.model_validate(row).model_dump(mode="python")
        ref_error = _reference_error(db, organization_id, result.record_type, payload)
        if ref_error:
            errors.append({"source_location": location, "field": None, "error_code": "REFERENCE_NOT_FOUND", "message": ref_error})
            continue
        entity = model(organization_id=organization_id, **payload)
        try:
            with db.begin_nested():
                db.add(entity)
                db.flush()
                db.add(ImportRecordLineage(
                    job_id=job.id, organization_id=organization_id,
                    record_type=result.record_type, source_location=location,
                    source_key=source_key, target_record_id=entity.id,
                ))
                db.flush()
            imported += 1
        except IntegrityError:
            errors.append({"source_location": location, "field": None, "error_code": "PERSISTENCE_CONFLICT",
                           "message": "The record conflicts with an existing catalog constraint; no record was written."})
    for error in errors[:1000]:
        location = str(error.get("source_location") or "unknown")
        db.add(ImportRowError(
            job_id=job.id, row_number=_row_number(location), field=error.get("field"),
            error_code=str(error.get("error_code", "INVALID_RECORD"))[:80],
            message=str(error.get("message", "Invalid record."))[:4000],
            source_location=location[:512],
        ))
    rejected = result.total_records - imported
    job.valid_rows = imported
    job.invalid_rows = rejected
    job.processed_rows = result.total_records
    job.status = "completed" if rejected == 0 else ("partial" if imported else "failed")
    job.error_message = None if rejected == 0 else f"{rejected} of {result.total_records} records were not imported."
    db.commit()
    db.refresh(job)
    return {
        "import_id": str(job.id), "filename": filename, "record_type": result.record_type,
        "format": parsed.format, "status": job.status, "total_records": result.total_records,
        "imported_records": imported, "rejected_records": rejected, "lineage_records": imported,
        "mappings": result.mappings, "unmapped_headers": result.unmapped_headers,
        "errors": errors[:100], "error_count": len(errors),
    }
