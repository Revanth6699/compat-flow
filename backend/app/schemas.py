from pydantic import BaseModel, ConfigDict, Field
import uuid
from datetime import datetime

class HealthResponse(BaseModel):
    status: str
    service: str

class ImportPreviewRow(BaseModel):
    sku: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    manufacturer: str = Field(min_length=1, max_length=160)
    part_number: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=120)
    compatibility: str | None = None
    replacement_sku: str | None = None

    model_config = ConfigDict(str_strip_whitespace=True)

class ImportPreviewRowErrorResponse(BaseModel):
    row_number: int
    field: str | None
    error_code: str
    message: str

class ImportPreviewResponse(BaseModel):
    filename: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    errors: list[str]
    preview: list[ImportPreviewRow]
    row_errors: list[ImportPreviewRowErrorResponse]

class ImportJobCreatedResponse(BaseModel):
    id: uuid.UUID
    filename: str
    status: str
    created_at: datetime

class ImportRowErrorResponse(BaseModel):
    row_number: int
    field: str | None
    error_code: str
    message: str
    created_at: datetime

class ImportJobStatusResponse(BaseModel):
    id: uuid.UUID
    filename: str
    status: str
    import_type: str
    row_count: int
    valid_rows: int
    invalid_rows: int
    processed_rows: int
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    error_total: int
    error_limit: int
    error_offset: int
    row_errors: list[ImportRowErrorResponse]
