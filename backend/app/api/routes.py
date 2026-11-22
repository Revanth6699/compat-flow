import csv
import json
import re
from datetime import datetime
from collections import Counter

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.auth import AuthenticatedUser, resolve_import_limits, require_demo_or_paid_access, require_permission, require_plan_feature
from app.core.database import get_db
from app.models import InventorySnapshot, Product, ProductIdentifier, ProductVariant, Supplier, SupplierOffer, ValidationProfile, ValidationRule
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
    ValidationProfileCreateRequest, ValidationProfileResponse,
    ValidationRuleCreateRequest, ValidationRuleUpdateRequest, ValidationRuleResponse,
)
from app.services.ingestion_adapters import IngestionParseError, parse_source
from app.services.record_import import RecordMappingError, validate_parsed_records
from app.services.catalog_ingestion import persist_validated_import
from app.services.dataset_rules import profile_dataset_rules
from app.services.custom_validation import CustomRuleError, validate_rule_config
from app.services.industry_catalog import IndustryCSVError, validate_industry_records
from app.services.catalog_csv import (
    CatalogCSVValidationError,
    CATALOG_PROFILES,
    parse_catalog_csv,
)

router = APIRouter()

@router.get("/validation/profiles", response_model=list[ValidationProfileResponse])
def list_validation_profiles(
    current: AuthenticatedUser = Depends(require_permission("catalog:read")),
    _plan: AuthenticatedUser = Depends(require_plan_feature("custom_rules")),
    db: Session = Depends(get_db),
):
    return list(db.scalars(
        select(ValidationProfile)
        .where(ValidationProfile.organization_id == current.profile.organization_id)
        .order_by(ValidationProfile.name.asc())
    ).all())


@router.post("/validation/profiles", response_model=ValidationProfileResponse, status_code=201)
def create_validation_profile(
    payload: ValidationProfileCreateRequest,
    current: AuthenticatedUser = Depends(require_permission("catalog:write")),
    _plan: AuthenticatedUser = Depends(require_plan_feature("custom_rules")),
    db: Session = Depends(get_db),
):
    profile = ValidationProfile(
        organization_id=current.profile.organization_id,
        created_by_user_id=current.profile.id,
        name=payload.name.strip(),
        dataset_type=payload.dataset_type.strip().casefold(),
        description=payload.description.strip() if payload.description else None,
    )
    db.add(profile)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A validation profile with this name already exists in your organization.") from None
    db.refresh(profile)
    return profile


@router.get("/validation/profiles/{profile_id}/rules", response_model=list[ValidationRuleResponse])
def list_validation_profile_rules(
    profile_id: UUID,
    current: AuthenticatedUser = Depends(require_permission("catalog:read")),
    _plan: AuthenticatedUser = Depends(require_plan_feature("custom_rules")),
    db: Session = Depends(get_db),
):
    profile = db.scalar(select(ValidationProfile.id).where(
        ValidationProfile.id == profile_id,
        ValidationProfile.organization_id == current.profile.organization_id,
    ))
    if profile is None:
        raise HTTPException(status_code=404, detail="Validation profile not found.")
    return list(db.scalars(
        select(ValidationRule)
        .where(
            ValidationRule.profile_id == profile_id,
            ValidationRule.organization_id == current.profile.organization_id,
        )
        .order_by(ValidationRule.created_at.asc())
    ).all())


@router.post("/validation/profiles/{profile_id}/rules", response_model=ValidationRuleResponse, status_code=201)
def create_validation_rule(
    profile_id: UUID,
    payload: ValidationRuleCreateRequest,
    current: AuthenticatedUser = Depends(require_permission("catalog:write")),
    _plan: AuthenticatedUser = Depends(require_plan_feature("custom_rules")),
    db: Session = Depends(get_db),
):
    profile = db.scalar(select(ValidationProfile.id).where(
        ValidationProfile.id == profile_id,
        ValidationProfile.organization_id == current.profile.organization_id,
        ValidationProfile.is_active.is_(True),
    ))
    if profile is None:
        raise HTTPException(status_code=404, detail="Active validation profile not found.")
    try:
        config = validate_rule_config(payload.rule_type, payload.config)
    except CustomRuleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    rule = ValidationRule(
        organization_id=current.profile.organization_id,
        profile_id=profile_id,
        code=payload.code,
        name=payload.name.strip(),
        field_name=payload.field_name.strip(),
        rule_type=payload.rule_type,
        config=config,
        severity=payload.severity,
        enabled=payload.enabled,
    )
    db.add(rule)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A rule with this code already exists in the selected profile.") from None
    db.refresh(rule)
    return rule


@router.patch("/validation/profiles/{profile_id}/rules/{rule_id}", response_model=ValidationRuleResponse)
def update_validation_rule(
    profile_id: UUID,
    rule_id: UUID,
    payload: ValidationRuleUpdateRequest,
    current: AuthenticatedUser = Depends(require_permission("catalog:write")),
    _plan: AuthenticatedUser = Depends(require_plan_feature("custom_rules")),
    db: Session = Depends(get_db),
):
    rule = db.scalar(select(ValidationRule).where(
        ValidationRule.id == rule_id,
        ValidationRule.profile_id == profile_id,
        ValidationRule.organization_id == current.profile.organization_id,
    ))
    if rule is None:
        raise HTTPException(status_code=404, detail="Validation rule not found.")
    changes = payload.model_dump(exclude_unset=True)
    if "config" in changes:
        try:
            changes["config"] = validate_rule_config(rule.rule_type, changes["config"])
        except CustomRuleError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
    for key, value in changes.items():
        setattr(rule, key, value.strip() if key in {"name", "field_name"} and value is not None else value)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/validation/profiles/{profile_id}/rules/{rule_id}", status_code=204)
def delete_validation_rule(
    profile_id: UUID,
    rule_id: UUID,
    current: AuthenticatedUser = Depends(require_permission("catalog:write")),
    _plan: AuthenticatedUser = Depends(require_plan_feature("custom_rules")),
    db: Session = Depends(get_db),
):
    rule = db.scalar(select(ValidationRule).where(
        ValidationRule.id == rule_id,
        ValidationRule.profile_id == profile_id,
        ValidationRule.organization_id == current.profile.organization_id,
    ))
    if rule is None:
        raise HTTPException(status_code=404, detail="Validation rule not found.")
    db.delete(rule)
    db.commit()
    return None




@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", service="compatflow-api")


async def _validate_catalog_csv(file: UploadFile, profile_id: str = "general", column_mapping=None, max_bytes: int | None = settings.import_max_upload_bytes, max_rows: int | None = 10_000) -> ImportPreviewResponse:
    filename = (file.filename or "").strip()
    if not filename.lower().endswith(".csv"):
        await file.close()
        raise HTTPException(status_code=415, detail="Only CSV files are supported.")
    if len(filename) > 255:
        await file.close()
        raise HTTPException(status_code=400, detail="Filename must not exceed 255 characters.")

    upload_limit = max_bytes
    try:
        raw = await file.read(upload_limit + 1) if upload_limit is not None else await file.read()
    finally:
        await file.close()

    if upload_limit is not None and len(raw) > upload_limit:
        raise HTTPException(status_code=413, detail="File exceeds the configured upload limit.")
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded CSV is empty.")
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded.") from None

    try:
        result = parse_catalog_csv(content, max_rows=max_rows, profile_id=profile_id, column_mapping=column_mapping, allow_incomplete_mapping=column_mapping is None)
        if not result.column_mappings:
            raise CatalogCSVValidationError(
                "This file does not appear to contain product catalog columns. "
                "No SKU, product name, manufacturer, part number or category columns were recognized. "
                "The uploaded file may describe sellers, customers or another record type. "
                "Upload a product catalog or map at least one product field."
            )
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


@router.post("/catalog/import/profile")
async def profile_public_dataset(
    file: UploadFile = File(...),
    _access: AuthenticatedUser = Depends(require_demo_or_paid_access()),
    db: Session = Depends(get_db),
):
    """Create a stateless, evidence-based profile for non-catalog datasets."""
    limits = resolve_import_limits(_access, db)
    filename = (file.filename or "").strip()
    if not filename or len(filename) > 255:
        await file.close()
        raise HTTPException(status_code=400, detail="A valid filename is required.")
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in {"csv", "xls", "xlsx", "json", "xml"}:
        await file.close()
        raise HTTPException(status_code=415, detail="Supported dataset profile formats: CSV, XLS, XLSX, JSON and XML.")
    limit = limits["max_upload_bytes"]
    try:
        raw = await file.read(limit + 1) if limit is not None else await file.read()
    finally:
        await file.close()
    if limit is not None and len(raw) > limit:
        raise HTTPException(status_code=413, detail="File exceeds the configured upload limit.")
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded dataset is empty.")
    try:
        parsed = parse_source(raw, filename, max_records=limits["max_records"])
    except IngestionParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    rows = [record.values for record in parsed.records]
    total = len(rows)
    headers = parsed.headers
    columns = []
    total_cells = total * len(headers)
    populated_cells = 0
    duplicate_keys = Counter()
    complete_records = 0
    for row in rows:
        key = json.dumps(row, sort_keys=True, default=str, separators=(",", ":"))
        duplicate_keys[key] += 1
        if all(row.get(header) is not None and str(row.get(header)).strip() != "" for header in headers):
            complete_records += 1
    duplicate_rows = sum(count - 1 for count in duplicate_keys.values() if count > 1)
    categorical = []
    date_columns = []
    numeric_columns = []
    for header in headers:
        values = [row.get(header) for row in rows]
        present = [value for value in values if value is not None and str(value).strip() != ""]
        populated_cells += len(present)
        numeric = []
        for value in present:
            try:
                numeric.append(float(str(value).replace(",", "")))
            except (TypeError, ValueError):
                numeric = []
                break
        parsed_dates = []
        if present and not numeric:
            for value in present:
                try:
                    parsed_dates.append(datetime.fromisoformat(str(value).strip().replace("Z", "+00:00")))
                except (TypeError, ValueError):
                    parsed_dates = []
                    break
        if not present:
            inferred = "empty"
        elif numeric and len(numeric) == len(present):
            inferred = "numeric"
            numeric_columns.append(header)
        elif parsed_dates and len(parsed_dates) == len(present):
            inferred = "datetime"
            date_columns.append(header)
        elif all(str(value).strip().casefold() in {"true", "false", "yes", "no", "0", "1"} for value in present):
            inferred = "boolean"
        else:
            inferred = "categorical" if len({str(value) for value in present}) <= min(50, max(8, int(len(present) * 0.2))) else "text"
        distinct = len({str(value) for value in present})
        top_values = []
        if inferred == "categorical":
            counts = Counter(str(value) for value in present)
            top_values = [{"value": value, "count": count, "pct": round(count / len(present) * 100, 2)} for value, count in counts.most_common(8)]
            categorical.append({"name": header, "values": top_values})
        columns.append({
            "name": header,
            "populated": len(present),
            "missing": total - len(present),
            "completeness_pct": round((len(present) / total * 100) if total else 0, 2),
            "distinct_values": distinct,
            "inferred_type": inferred,
            "minimum": min(numeric) if numeric else (min(parsed_dates).isoformat() if parsed_dates else None),
            "maximum": max(numeric) if numeric else (max(parsed_dates).isoformat() if parsed_dates else None),
            "average": round(sum(numeric) / len(numeric), 4) if numeric else None,
            "top_values": top_values,
        })
    normalized = {re.sub(r"[^a-z0-9]+", "_", header.casefold()).strip("_") for header in headers}
    product_headers = {"sku", "product_sku", "item_sku", "product_code", "product_name", "item_name", "manufacturer", "manufacturer_name", "part_number", "mpn", "category", "product_category"}
    domain_profile = profile_dataset_rules(headers, rows)
    dataset_type = domain_profile["dataset_type"]

    relationship_checks = []
    purchase_header = next((h for h in headers if re.sub(r"[^a-z0-9]+", "_", h.casefold()).strip("_") in {"order_purchase_timestamp", "purchase_date", "created_at", "order_date"}), None)
    delivery_header = next((h for h in headers if re.sub(r"[^a-z0-9]+", "_", h.casefold()).strip("_") in {"order_delivered_customer_date", "delivered_at", "delivery_date", "delivered_date"}), None)
    if purchase_header and delivery_header:
        durations = []
        reversed_dates = 0
        for row in rows:
            try:
                purchased = datetime.fromisoformat(str(row.get(purchase_header)).strip().replace("Z", "+00:00"))
                delivered = datetime.fromisoformat(str(row.get(delivery_header)).strip().replace("Z", "+00:00"))
                days = (delivered - purchased).total_seconds() / 86400
                if days < 0:
                    reversed_dates += 1
                else:
                    durations.append(days)
            except (TypeError, ValueError):
                continue
        relationship_checks.append({
            "name": "Purchase-to-delivery duration",
            "from_column": purchase_header,
            "to_column": delivery_header,
            "matched_records": len(durations) + reversed_dates,
            "average_days": round(sum(durations) / len(durations), 2) if durations else None,
            "minimum_days": round(min(durations), 2) if durations else None,
            "maximum_days": round(max(durations), 2) if durations else None,
            "negative_duration_records": reversed_dates,
        })

    completeness = round((populated_cells / total_cells * 100) if total_cells else 0, 2)
    missing_cells = total_cells - populated_cells
    findings = []
    if missing_cells:
        findings.append({"severity": "warning", "title": "Missing values detected", "detail": f"{missing_cells:,} cells are empty ({round(missing_cells / total_cells * 100, 2) if total_cells else 0}% of the dataset)."})
    if duplicate_rows:
        findings.append({"severity": "warning", "title": "Duplicate records detected", "detail": f"{duplicate_rows:,} rows repeat an earlier complete row."})
    if any(column["completeness_pct"] < 80 for column in columns):
        low = sorted((column for column in columns if column["completeness_pct"] < 80), key=lambda c: c["completeness_pct"])
        findings.append({"severity": "warning", "title": "Low-completeness columns", "detail": ", ".join(f"{c['name']} ({c['completeness_pct']}%)" for c in low[:5])})
    for issue in domain_profile["domain_issues"]:
        findings.append({
            "severity": issue["severity"],
            "title": issue["title"],
            "detail": f'{issue["detail"]} Recommended action: {issue["recommendation"]}',
        })
    if not findings:
        findings.append({"severity": "info", "title": "No structural red flags detected", "detail": "No missing cells or exact duplicate rows were found in the uploaded sample."})

    return {
        "filename": filename,
        "format": parsed.format,
        "dataset_type": dataset_type,
        "total_records": total,
        "total_columns": len(headers),
        "total_cells": total_cells,
        "populated_cells": populated_cells,
        "missing_cells": missing_cells,
        "completeness_pct": completeness,
        "complete_records": complete_records,
        "incomplete_records": total - complete_records,
        "complete_records_pct": round(complete_records / total * 100, 2) if total else 0,
        "duplicate_rows": duplicate_rows,
        "duplicate_rate_pct": round(duplicate_rows / total * 100, 2) if total else 0,
        "columns": columns,
        "categorical_distributions": categorical,
        "date_columns": date_columns,
        "numeric_columns": numeric_columns,
        "relationship_checks": relationship_checks,
        "domain_checks": domain_profile["domain_checks"],
        "validation_rules": domain_profile["validation_rules"],
        "findings": findings,
        "preview": rows[:10],
        "is_product_catalog": bool(normalized & product_headers),
        "persisted": False,
        "profile_scope": "structural_completeness_exact_duplicates_inferred_types_numeric_and_date_ranges_categorical_distributions_and_supported_date_relationships",
        "quality_score": None,
    }


async def _validate_industry_upload(
    file: UploadFile, profile_id: str | None, max_bytes: int | None, *, max_records: int | None = 10_000
):
    filename = (file.filename or "").strip()
    if not filename or len(filename) > 255:
        await file.close()
        raise HTTPException(status_code=400, detail="A valid filename is required.")
    try:
        raw = await file.read(max_bytes + 1) if max_bytes is not None else await file.read()
    finally:
        await file.close()
    if max_bytes is not None and len(raw) > max_bytes:
        raise HTTPException(status_code=413, detail="File exceeds the configured upload limit.")
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    try:
        parsed = parse_source(raw, filename, max_records=max_records)
        if not parsed.records:
            raise HTTPException(status_code=422, detail="No data rows were found in the uploaded file.")
        result = validate_industry_records(
            parsed.headers, [record.values for record in parsed.records], profile_id=profile_id
        )
    except IngestionParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except (IndustryCSVError, csv.Error) as exc:
        message = str(exc)
        raise HTTPException(status_code=413 if "row limit" in message else 422, detail=message) from None
    return {"filename": filename, "format": parsed.format, **result}


@router.post("/catalog/import/validate-industry")
async def validate_industry_catalog_import(
    file: UploadFile = File(...),
    profile_id: str | None = Form(None),
    _plan: AuthenticatedUser = Depends(require_plan_feature("csv_validation")),
    db: Session = Depends(get_db),
):
    """Authenticated industry-aware validation using the active plan's upload limits."""
    limits = resolve_import_limits(_plan, db)
    return await _validate_industry_upload(
        file, profile_id, limits["max_upload_bytes"], max_records=limits["max_records"]
    )


@router.post("/catalog/import/preview-industry")
async def preview_industry_catalog_import(
    file: UploadFile = File(...),
    profile_id: str | None = Form(None),
    _access: AuthenticatedUser = Depends(require_demo_or_paid_access()),
    db: Session = Depends(get_db),
):
    """Stateless industry-aware preview using demo or active subscription limits."""
    limits = resolve_import_limits(_access, db)
    return await _validate_industry_upload(
        file, profile_id, limits["max_upload_bytes"], max_records=limits["max_records"]
    )


@router.post("/catalog/import/validate", response_model=ImportPreviewResponse)
async def validate_paid_catalog_import(
    file: UploadFile = File(...),
    profile_id: str = Form("general"),
    column_mapping_json: str | None = Form(None),
    _plan: AuthenticatedUser = Depends(require_plan_feature("csv_validation")),
    db: Session = Depends(get_db),
):
    """Authenticated, subscription-gated validation. Files are not persisted."""
    limits = resolve_import_limits(_plan, db)
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
    return await _validate_catalog_csv(file, profile_id, mapping, max_bytes=limits["max_upload_bytes"], max_rows=limits["max_records"])


@router.post("/catalog/import/preview", response_model=ImportPreviewResponse)
async def preview_catalog_import(
    file: UploadFile = File(...),
    profile_id: str = Form("general"),
    column_mapping_json: str | None = Form(None),
    _access: AuthenticatedUser = Depends(require_demo_or_paid_access()),
    db: Session = Depends(get_db),
):
    """Approved-demo or subscribed stateless validation. Files are not persisted."""
    limits = resolve_import_limits(_access, db)
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
    return await _validate_catalog_csv(file, profile_id, mapping, max_bytes=limits["max_upload_bytes"], max_rows=limits["max_records"])



@router.post("/catalog/import/preview-records")
async def preview_public_spreadsheet(
    file: UploadFile = File(...),
    _access: AuthenticatedUser = Depends(require_demo_or_paid_access()),
    db: Session = Depends(get_db),
):
    """Stateless XLS/XLSX product validation using the authenticated account's limits."""
    limits = resolve_import_limits(_access, db)
    filename = (file.filename or "").strip()
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in {"xlsx", "xls"}:
        await file.close()
        raise HTTPException(status_code=415, detail="The public spreadsheet demo accepts XLSX and XLS files only.")
    if not filename or len(filename) > 255:
        await file.close()
        raise HTTPException(status_code=400, detail="A valid filename is required.")
    upload_limit = limits["max_upload_bytes"]
    try:
        raw = await file.read(upload_limit + 1) if upload_limit is not None else await file.read()
    finally:
        await file.close()
    if upload_limit is not None and len(raw) > upload_limit:
        raise HTTPException(status_code=413, detail="File exceeds the configured upload limit.")
    try:
        parsed = parse_source(raw, filename, max_records=limits["max_records"])
        result = validate_parsed_records(parsed, "products", None)
        if not result.mappings:
            raise RecordMappingError(
                "This file does not appear to contain product catalog columns. "
                "No SKU, product name, manufacturer, part number or category columns were recognized. "
                "Upload a product catalog instead of a seller, customer or other record dataset."
            )
    except (IngestionParseError, RecordMappingError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return {
        "filename": filename,
        "format": parsed.format,
        "record_type": "products",
        "total_records": result.total_records,
        "valid_records": len(result.valid_records),
        "invalid_records": result.invalid_records,
        "mappings": result.mappings,
        "unmapped_headers": result.unmapped_headers,
        "field_completeness": result.field_completeness,
        "errors": result.errors[:50],
        "preview": result.valid_records[:10],
        "persisted": False,
        "validation_scope": "schema_and_in_file_duplicates",
        "referential_checks": "not_run",
    }


@router.post("/catalog/import/validate-records")
async def validate_multiformat_records(
    file: UploadFile = File(...),
    record_type: str = Form(...),
    column_mapping_json: str | None = Form(None),
    sheet_name: str | None = Form(None),
    header_row: int = Form(1, ge=1, le=1000),
    json_record_path: str | None = Form(None),
    xml_record_tag: str | None = Form(None),
    _current: AuthenticatedUser = Depends(require_permission("catalog:read")),
    _plan: AuthenticatedUser = Depends(require_plan_feature("supplier_catalogs")),
    db: Session = Depends(get_db),
):
    """Parse and deterministically validate one selected catalog record type; never persists."""
    limits = resolve_import_limits(_plan, db)
    filename = (file.filename or "").strip()
    if not filename or len(filename) > 255:
        await file.close()
        raise HTTPException(status_code=400, detail="A valid filename is required.")
    try:
        raw = await file.read(limits["max_upload_bytes"] + 1) if limits["max_upload_bytes"] is not None else await file.read()
    finally:
        await file.close()
    if limits["max_upload_bytes"] is not None and len(raw) > limits["max_upload_bytes"]:
        raise HTTPException(status_code=413, detail="File exceeds the configured upload limit.")
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    try:
        mapping = json.loads(column_mapping_json) if column_mapping_json else None
        if mapping is not None and (
            not isinstance(mapping, dict)
            or not all(isinstance(key, str) and isinstance(value, str) for key, value in mapping.items())
        ):
            raise ValueError
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="Manual mapping must be a JSON object of canonical fields to source headers.") from None
    try:
        parsed = parse_source(
            raw, filename, sheet_name=sheet_name, max_records=limits["max_records"], header_row=header_row,
            json_record_path=json_record_path, xml_record_tag=xml_record_tag,
        )
        result = validate_parsed_records(parsed, record_type, mapping)
    except (IngestionParseError, RecordMappingError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return {
        "filename": filename,
        "format": parsed.format,
        "record_type": result.record_type,
        "total_records": result.total_records,
        "valid_records": len(result.valid_records),
        "invalid_records": result.invalid_records,
        "mappings": result.mappings,
        "unmapped_headers": result.unmapped_headers,
        "field_completeness": result.field_completeness,
        "errors": result.errors[:50],
        "preview": result.valid_records[:10],
        "persisted": False,
        "validation_scope": "schema_and_in_file_duplicates",
        "referential_checks": "not_run",
    }



@router.post("/catalog/import/commit", status_code=201)
async def commit_multiformat_import(
    file: UploadFile = File(...),
    record_type: str = Form(...),
    column_mapping_json: str | None = Form(None),
    sheet_name: str | None = Form(None),
    header_row: int = Form(1, ge=1, le=1000),
    json_record_path: str | None = Form(None),
    xml_record_tag: str | None = Form(None),
    current: AuthenticatedUser = Depends(require_permission("catalog:write")),
    _plan: AuthenticatedUser = Depends(require_plan_feature("supplier_catalogs")),
    db: Session = Depends(get_db),
):
    """Persist a reviewed multi-format import with row-level errors and lineage."""
    limits = resolve_import_limits(_plan, db)
    filename = (file.filename or "").strip()
    if not filename or len(filename) > 255:
        await file.close()
        raise HTTPException(status_code=400, detail="A valid filename is required.")
    try:
        raw = await file.read(limits["max_upload_bytes"] + 1) if limits["max_upload_bytes"] is not None else await file.read()
    finally:
        await file.close()
    if limits["max_upload_bytes"] is not None and len(raw) > limits["max_upload_bytes"]:
        raise HTTPException(status_code=413, detail="File exceeds the configured upload limit.")
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    try:
        mapping = json.loads(column_mapping_json) if column_mapping_json else None
        if mapping is not None and (
            not isinstance(mapping, dict)
            or not all(isinstance(key, str) and isinstance(value, str) for key, value in mapping.items())
        ):
            raise ValueError
        parsed = parse_source(
            raw, filename, sheet_name=sheet_name, max_records=limits["max_records"], header_row=header_row,
            json_record_path=json_record_path, xml_record_tag=xml_record_tag,
        )
        result = validate_parsed_records(parsed, record_type, mapping)
    except (IngestionParseError, RecordMappingError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return persist_validated_import(
        db=db, organization_id=current.profile.organization_id,
        filename=filename, parsed=parsed, result=result,
    )


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
