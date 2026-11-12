import uuid
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert

from app.core.database import SessionLocal
from app.models import ImportJob, ImportRowError, Product
from app.services.catalog_csv import parse_catalog_csv
from app.services.file_storage import get_storage_path
from app.workers.celery_app import celery_app


@celery_app.task(name="compatflow.health_check")
def health_check_task() -> str:
    return "worker-ok"


@celery_app.task(name="compatflow.process_catalog_import")
def process_catalog_import(job_id: str) -> dict:
    db = SessionLocal()

    try:
        job = db.get(ImportJob, uuid.UUID(job_id))

        if job is None:
            return {"status": "not_found", "job_id": job_id}

        if job.status in {"completed", "completed_with_errors"}:
            return {"status": job.status, "job_id": job_id}

        job.status = "processing"
        job.started_at = job.started_at or datetime.now(timezone.utc)
        job.error_message = None
        db.commit()

        if not job.storage_key:
            raise ValueError("Import job has no storage key.")

        file_path = get_storage_path(job.storage_key)
        raw = file_path.read_bytes()
        content = raw.decode("utf-8-sig")

        result = parse_catalog_csv(content)

        for error in result.row_errors:
            db.add(
                ImportRowError(
                    job_id=job.id,
                    row_number=error.row_number,
                    field=error.field,
                    error_code=error.error_code,
                    message=error.message,
                )
            )

        inserted_count = 0

        for row, row_number in zip(
            result.valid_rows,
            result.valid_row_numbers,
        ):
            statement = (
                insert(Product)
                .values(
                    organization_id=job.organization_id,
                    supplier_id=job.supplier_id,
                    sku=row.sku,
                    name=row.name,
                    manufacturer=row.manufacturer,
                    part_number=row.part_number,
                    category=row.category,
                    replacement_sku=row.replacement_sku or None,
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        Product.organization_id,
                        Product.sku,
                    ]
                )
                .returning(Product.id)
            )
            inserted = db.execute(statement)

            if inserted.scalar_one_or_none() is not None:
                inserted_count += 1
            else:
                db.add(
                    ImportRowError(
                        job_id=job.id,
                        row_number=row_number,
                        field="sku",
                        error_code="PRODUCT_SKU_ALREADY_EXISTS",
                        message=(
                            f"SKU '{row.sku}' already exists "
                            "in this organization's catalog."
                        ),
                    )
                )

        job.row_count = result.total_rows
        job.valid_rows = inserted_count
        job.invalid_rows = result.total_rows - inserted_count
        job.processed_rows = result.total_rows
        job.status = (
            "completed"
            if job.invalid_rows == 0
            else "completed_with_errors"
        )
        job.completed_at = datetime.now(timezone.utc)

        db.commit()

        return {
            "job_id": job_id,
            "status": job.status,
            "total_rows": job.row_count,
            "valid_rows": job.valid_rows,
            "invalid_rows": job.invalid_rows,
        }

    except Exception as exc:
        db.rollback()

        try:
            job = db.get(ImportJob, uuid.UUID(job_id))

            if job is not None:
                job.status = "failed"
                job.error_message = str(exc)[:2000]
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            db.rollback()

        raise

    finally:
        db.close()
