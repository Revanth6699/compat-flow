"""Authenticated one-shot connector ingestion and tenant-scoped import history."""
from __future__ import annotations

import json
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, require_permission, require_plan_feature
from app.core.config import settings
from app.core.database import get_db
from app.models import ImportJob, ImportRowError, ImportRecordLineage
from app.services.catalog_ingestion import persist_validated_import
from app.services.ingestion_adapters import IngestionParseError, parse_source
from app.services.record_import import RecordMappingError, validate_parsed_records
from app.services.source_connectors import (
    SourceConnectorError,
    fetch_api_records,
    fetch_sftp_file,
    fetch_sql_server_rows,
)

router = APIRouter(prefix="/catalog/import", tags=["catalog-import-connectors"])


class ConnectorImportRequest(BaseModel):
    source_type: Literal["rest_api", "sftp", "sql_server"]
    record_type: Literal[
        "products", "product_variants", "supplier_offers",
        "inventory_snapshots", "product_identifiers",
    ]
    column_mapping: dict[str, str] | None = None

    # REST API: endpoint host must be in CONNECTOR_ALLOWED_HOSTS.
    api_url: str | None = None
    api_records_path: str | None = None
    api_headers: dict[str, str] = Field(default_factory=dict)

    # SFTP: host must be allowlisted and its key must exist in known_hosts.
    sftp_host: str | None = None
    sftp_port: int = Field(default=22, ge=1, le=65535)
    sftp_username: str | None = None
    sftp_password: str | None = None
    sftp_private_key: str | None = None
    sftp_remote_path: str | None = None
    sftp_filename: str | None = None

    # SQL Server: URL is transient; use a least-privilege read-only account.
    sql_server_url: str | None = None
    sql_schema: str | None = None
    sql_table: str | None = None
    sql_columns: list[str] = Field(default_factory=list)
    sql_row_limit: int = Field(default=10000, ge=1, le=10000)


def _allowed_hosts() -> set[str]:
    return {host.strip().casefold().rstrip(".") for host in settings.connector_allowed_hosts.split(",") if host.strip()}


def _require_allowed_host(host: str | None) -> str:
    allowed = _allowed_hosts()
    normalized = (host or "").casefold().rstrip(".")
    if not allowed or not normalized or normalized not in allowed:
        raise HTTPException(status_code=422, detail="Connector host is not in CONNECTOR_ALLOWED_HOSTS.")
    return normalized


async def _load_source(payload: ConnectorImportRequest) -> tuple[bytes, str]:
    allowed = _allowed_hosts()
    if payload.source_type == "rest_api":
        if not payload.api_url:
            raise HTTPException(status_code=422, detail="api_url is required.")
        host = urlsplit(payload.api_url).hostname
        _require_allowed_host(host)
        if len(payload.api_headers) > 10 or any(
            key.casefold() not in {"authorization", "x-api-key", "accept"}
            or len(key) > 64 or len(value) > 4096
            for key, value in payload.api_headers.items()
        ):
            raise HTTPException(status_code=422, detail="Only bounded Authorization, X-API-Key, and Accept headers are supported.")
        records = await fetch_api_records(
            payload.api_url, allowed_hosts=allowed,
            headers=payload.api_headers, records_key=payload.api_records_path,
            max_bytes=settings.import_max_upload_bytes,
        )
        return json.dumps(records, ensure_ascii=False, default=str).encode("utf-8"), "connector.json"

    if payload.source_type == "sftp":
        host = _require_allowed_host(payload.sftp_host)
        if not settings.sftp_known_hosts_path:
            raise HTTPException(status_code=503, detail="SFTP known-hosts configuration is not available.")
        if not payload.sftp_username or not payload.sftp_remote_path:
            raise HTTPException(status_code=422, detail="SFTP username and remote path are required.")
        if bool(payload.sftp_password) == bool(payload.sftp_private_key):
            raise HTTPException(status_code=422, detail="Provide exactly one SFTP authentication method.")
        filename = payload.sftp_filename or payload.sftp_remote_path.rsplit("/", 1)[-1]
        if not filename or len(filename) > 255:
            raise HTTPException(status_code=422, detail="A valid SFTP filename is required.")
        content = fetch_sftp_file(
            host=host, port=payload.sftp_port, username=payload.sftp_username,
            password=payload.sftp_password, private_key=payload.sftp_private_key,
            remote_path=payload.sftp_remote_path,
            known_hosts_path=settings.sftp_known_hosts_path,
            max_bytes=settings.import_max_upload_bytes,
        )
        return content, filename

    if not payload.sql_server_url or not payload.sql_schema or not payload.sql_table:
        raise HTTPException(status_code=422, detail="SQL Server URL, schema, and table are required.")
    from sqlalchemy.engine import make_url
    try:
        parsed_url = make_url(payload.sql_server_url)
    except Exception:
        raise HTTPException(status_code=422, detail="SQL Server connection URL is invalid.") from None
    _require_allowed_host(parsed_url.host)
    if not payload.sql_columns:
        raise HTTPException(status_code=422, detail="At least one SQL Server column must be selected.")
    rows = fetch_sql_server_rows(
        payload.sql_server_url, schema=payload.sql_schema, table=payload.sql_table,
        columns=payload.sql_columns, limit=payload.sql_row_limit,
        max_bytes=settings.import_max_upload_bytes,
    )
    return json.dumps(rows, ensure_ascii=False, default=str).encode("utf-8"), "connector.json"


def _prepare(payload: ConnectorImportRequest, raw: bytes, filename: str):
    parsed = parse_source(raw, filename)
    result = validate_parsed_records(parsed, payload.record_type, payload.column_mapping)
    return parsed, result


@router.post("/connectors/preview")
async def preview_connector_import(
    payload: ConnectorImportRequest,
    _current: AuthenticatedUser = Depends(require_permission("catalog:read")),
    _plan: AuthenticatedUser = Depends(require_plan_feature("supplier_catalogs")),
):
    try:
        raw, filename = await _load_source(payload)
        parsed, result = _prepare(payload, raw, filename)
    except (SourceConnectorError, IngestionParseError, RecordMappingError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return {
        "source_type": payload.source_type, "filename": filename,
        "format": parsed.format, "record_type": result.record_type,
        "total_records": result.total_records, "valid_records": len(result.valid_records),
        "invalid_records": result.invalid_records, "mappings": result.mappings,
        "unmapped_headers": result.unmapped_headers,
        "field_completeness": result.field_completeness,
        "errors": result.errors[:100], "preview": result.valid_records[:10],
        "persisted": False,
    }


@router.post("/connectors/commit", status_code=201)
async def commit_connector_import(
    payload: ConnectorImportRequest,
    current: AuthenticatedUser = Depends(require_permission("catalog:write")),
    _plan: AuthenticatedUser = Depends(require_plan_feature("supplier_catalogs")),
    db: Session = Depends(get_db),
):
    try:
        raw, filename = await _load_source(payload)
        parsed, result = _prepare(payload, raw, filename)
    except (SourceConnectorError, IngestionParseError, RecordMappingError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return persist_validated_import(
        db=db, organization_id=current.profile.organization_id,
        filename=filename, parsed=parsed, result=result,
    )


@router.get("/history")
def list_import_history(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current: AuthenticatedUser = Depends(require_permission("catalog:read")),
    _plan: AuthenticatedUser = Depends(require_plan_feature("supplier_catalogs")),
    db: Session = Depends(get_db),
):
    organization_id = current.profile.organization_id
    total = db.scalar(select(func.count()).select_from(ImportJob).where(
        ImportJob.organization_id == organization_id
    )) or 0
    jobs = db.scalars(
        select(ImportJob).where(ImportJob.organization_id == organization_id)
        .order_by(ImportJob.created_at.desc()).offset(offset).limit(limit)
    ).all()
    return {
        "total": total, "limit": limit, "offset": offset,
        "items": [{
            "id": str(job.id), "filename": job.filename, "record_type": job.import_type,
            "status": job.status, "total_records": job.row_count,
            "imported_records": job.valid_rows, "rejected_records": job.invalid_rows,
            "processed_records": job.processed_rows, "created_at": job.created_at,
            "completed_at": job.completed_at, "error_message": job.error_message,
        } for job in jobs],
    }


@router.get("/history/{import_id}")
def get_import_history_item(
    import_id: UUID,
    error_limit: int = Query(default=100, ge=1, le=500),
    error_offset: int = Query(default=0, ge=0),
    current: AuthenticatedUser = Depends(require_permission("catalog:read")),
    _plan: AuthenticatedUser = Depends(require_plan_feature("supplier_catalogs")),
    db: Session = Depends(get_db),
):
    job = db.scalar(select(ImportJob).where(
        ImportJob.id == import_id,
        ImportJob.organization_id == current.profile.organization_id,
    ))
    if job is None:
        raise HTTPException(status_code=404, detail="Import job not found.")
    errors_query = select(ImportRowError).where(ImportRowError.job_id == job.id)
    error_total = db.scalar(select(func.count()).select_from(ImportRowError).where(
        ImportRowError.job_id == job.id
    )) or 0
    errors = db.scalars(errors_query.order_by(ImportRowError.row_number.asc())
                        .offset(error_offset).limit(error_limit)).all()
    lineage_total = db.scalar(select(func.count()).select_from(ImportRecordLineage).where(
        ImportRecordLineage.job_id == job.id,
        ImportRecordLineage.organization_id == current.profile.organization_id,
    )) or 0
    lineage = db.scalars(
        select(ImportRecordLineage).where(
            ImportRecordLineage.job_id == job.id,
            ImportRecordLineage.organization_id == current.profile.organization_id,
        ).order_by(ImportRecordLineage.created_at.asc()).limit(500)
    ).all()
    return {
        "id": str(job.id), "filename": job.filename, "record_type": job.import_type,
        "status": job.status, "total_records": job.row_count,
        "imported_records": job.valid_rows, "rejected_records": job.invalid_rows,
        "processed_records": job.processed_rows, "created_at": job.created_at,
        "completed_at": job.completed_at, "error_message": job.error_message,
        "error_total": error_total, "error_limit": error_limit, "error_offset": error_offset,
        "lineage_total": lineage_total,
        "lineage": [{
            "record_type": item.record_type, "source_location": item.source_location,
            "source_key": item.source_key, "target_record_id": str(item.target_record_id),
        } for item in lineage],
        "lineage_truncated": lineage_total > len(lineage),
        "errors": [{
            "row_number": error.row_number, "source_location": error.source_location,
            "field": error.field, "error_code": error.error_code, "message": error.message,
        } for error in errors],
    }
