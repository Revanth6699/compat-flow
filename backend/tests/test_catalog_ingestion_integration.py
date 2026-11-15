import csv
import io
import json
import os
import xml.etree.ElementTree as ET
from uuid import UUID, uuid4

import pytest
from openpyxl import Workbook
import xlwt
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import (
    ImportJob,
    ImportRecordLineage,
    ImportRowError,
    Organization,
    Product,
    ProductVariant,
    Supplier,
    SupplierOffer,
    InventorySnapshot,
    ProductIdentifier,
)
from app.services.catalog_ingestion import persist_validated_import
from app.services.ingestion_adapters import parse_source
from app.services.record_import import validate_parsed_records


FORMATS = ("csv", "xlsx", "xls", "json", "xml")
RECORD_TYPES = (
    "products",
    "product_variants",
    "supplier_offers",
    "inventory_snapshots",
    "product_identifiers",
)


@pytest.fixture
def db_session():
    if not os.getenv("DATABASE_URL"):
        pytest.skip("PostgreSQL integration tests require DATABASE_URL.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def _record(record_type, suffix, product_id, supplier_id):
    if record_type == "products":
        return {
            "sku": f"CF-{suffix}",
            "name": "Widget",
            "manufacturer": "Acme",
            "part_number": f"MPN-{suffix}",
            "category": "Parts",
        }
    if record_type == "product_variants":
        return {
            "product_id": str(product_id),
            "variant_sku": f"VAR-{suffix}",
            "attributes": {"color": "blue", "pack": 2},
            "is_active": True,
        }
    if record_type == "supplier_offers":
        return {
            "supplier_id": str(supplier_id),
            "product_id": str(product_id),
            "supplier_sku": f"SUP-{suffix}",
            "unit_price": "12.50",
            "currency": "USD",
        }
    if record_type == "inventory_snapshots":
        return {
            "product_id": str(product_id),
            "warehouse_code": f"WH-{suffix}",
            "quantity_on_hand": "25",
        }
    return {
        "product_id": str(product_id),
        "identifier_type": "other",
        "namespace": "integration-test",
        "value": f"ID-{suffix}",
    }


def _scalar(value):
    return json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value


def _serialize(extension, record):
    if extension == "json":
        return json.dumps([record], ensure_ascii=False).encode()
    if extension == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(record))
        writer.writeheader()
        writer.writerow({key: _scalar(value) for key, value in record.items()})
        return output.getvalue().encode()
    if extension == "xml":
        root = ET.Element("Records")
        element = ET.SubElement(root, "Record")
        for key, value in record.items():
            child = ET.SubElement(element, key)
            child.text = str(_scalar(value))
        return ET.tostring(root, encoding="utf-8")
    if extension == "xlsx":
        output = io.BytesIO()
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(list(record))
        sheet.append([_scalar(value) for value in record.values()])
        workbook.save(output)
        return output.getvalue()
    if extension == "xls":
        output = io.BytesIO()
        workbook = xlwt.Workbook()
        sheet = workbook.add_sheet("Records")
        for column, key in enumerate(record):
            sheet.write(0, column, key)
            sheet.write(1, column, _scalar(record[key]))
        workbook.save(output)
        return output.getvalue()
    raise AssertionError(f"Unsupported fixture format: {extension}")


def _seed_tenant(db, suffix):
    organization = Organization(id=uuid4(), name=f"Ingestion integration {suffix}")
    supplier = Supplier(
        id=uuid4(), organization_id=organization.id, name=f"Supplier {suffix}"
    )
    product = Product(
        id=uuid4(),
        organization_id=organization.id,
        sku=f"BASE-{suffix}",
        name="Base product",
        manufacturer="Acme",
        part_number=f"BASE-MPN-{suffix}",
        category="Parts",
    )
    db.add_all([organization, supplier, product])
    db.commit()
    return organization, supplier, product


def test_all_five_file_formats_persist_all_five_record_types_with_lineage(db_session):
    suffix = uuid4().hex[:10]
    organization, supplier, product = _seed_tenant(db_session, suffix)
    try:
        for record_type in RECORD_TYPES:
            for extension in FORMATS:
                unique = f"{suffix}-{record_type[:3]}-{extension}"
                record = _record(record_type, unique, product.id, supplier.id)
                filename = f"{record_type}-{unique}.{extension}"
                parsed = parse_source(_serialize(extension, record), filename)
                result = validate_parsed_records(parsed, record_type)
                assert result.total_records == 1, (record_type, extension, result.errors)
                assert result.invalid_records == 0, (record_type, extension, result.errors)

                committed = persist_validated_import(
                    db=db_session,
                    organization_id=organization.id,
                    filename=filename,
                    parsed=parsed,
                    result=result,
                    source_type="file",
                    source_descriptor=filename,
                    source_metadata=parsed.metadata,
                )
                assert committed["status"] == "completed", (record_type, extension, committed)
                assert committed["imported_records"] == 1
                job = db_session.get(ImportJob, UUID(committed["import_id"]))
                assert job is not None
                assert job.source_type == "file"
                assert job.source_descriptor == filename
                assert job.source_metadata == parsed.metadata
                lineage = db_session.scalars(
                    select(ImportRecordLineage).where(
                        ImportRecordLineage.job_id == job.id,
                        ImportRecordLineage.organization_id == organization.id,
                    )
                ).all()
                assert len(lineage) == 1
                assert lineage[0].record_type == record_type
                assert lineage[0].source_location == parsed.records[0].source_location
    finally:
        db_session.delete(organization)
        db_session.commit()


def test_partial_success_is_explicit_and_row_errors_are_persisted(db_session):
    suffix = uuid4().hex[:10]
    organization = Organization(id=uuid4(), name=f"Partial import {suffix}")
    db_session.add(organization)
    db_session.commit()
    try:
        records = [
            {
                "sku": f"PARTIAL-{suffix}",
                "name": "First",
                "manufacturer": "Acme",
                "part_number": "P-1",
                "category": "Parts",
            },
            {
                "sku": f"PARTIAL-{suffix}",
                "name": "Duplicate",
                "manufacturer": "Acme",
                "part_number": "P-2",
                "category": "Parts",
            },
        ]
        parsed = parse_source(json.dumps(records).encode(), "partial.json")
        result = validate_parsed_records(parsed, "products")
        committed = persist_validated_import(
            db=db_session,
            organization_id=organization.id,
            filename="partial.json",
            parsed=parsed,
            result=result,
        )
        assert committed["status"] == "partial"
        assert committed["imported_records"] == 1
        assert committed["rejected_records"] == 1
        job = db_session.get(ImportJob, committed["import_id"])
        errors = db_session.scalars(
            select(ImportRowError).where(ImportRowError.job_id == job.id)
        ).all()
        assert len(errors) == 1
        assert errors[0].error_code == "DUPLICATE_IN_FILE"
    finally:
        db_session.delete(organization)
        db_session.commit()


def test_commit_rejects_cross_tenant_product_references(db_session):
    suffix = uuid4().hex[:10]
    tenant_a, _, _ = _seed_tenant(db_session, f"A-{suffix}")
    tenant_b, _, foreign_product = _seed_tenant(db_session, f"B-{suffix}")
    try:
        record = {
            "product_id": str(foreign_product.id),
            "variant_sku": f"CROSS-{suffix}",
            "attributes": {"color": "red"},
        }
        parsed = parse_source(json.dumps([record]).encode(), "cross-tenant.json")
        result = validate_parsed_records(parsed, "product_variants")
        assert result.invalid_records == 0
        committed = persist_validated_import(
            db=db_session,
            organization_id=tenant_a.id,
            filename="cross-tenant.json",
            parsed=parsed,
            result=result,
        )
        assert committed["status"] == "failed"
        assert committed["imported_records"] == 0
        assert committed["rejected_records"] == 1
        assert db_session.scalar(
            select(ProductVariant.id).where(
                ProductVariant.organization_id == tenant_a.id,
                ProductVariant.variant_sku == f"CROSS-{suffix}",
            )
        ) is None
    finally:
        db_session.delete(tenant_a)
        db_session.delete(tenant_b)
        db_session.commit()
