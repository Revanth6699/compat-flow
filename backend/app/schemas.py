from pydantic import BaseModel, ConfigDict, Field
import uuid
from datetime import datetime
from decimal import Decimal


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
    severity: str = "critical"
    category: str = "data_integrity"
    recommendation: str = "Review the value and correct it at the source."


class ImportIssueCategoryResponse(BaseModel):
    category: str
    count: int


class ImportFieldMetricResponse(BaseModel):
    field: str
    populated: int
    missing: int
    completeness_pct: float


class ImportColumnMappingResponse(BaseModel):
    field: str
    source_header: str
    confidence: float


class ImportPreviewResponse(BaseModel):
    filename: str
    profile_id: str = "general"
    records_with_issues: int = 0
    duplicate_sku_count: int = 0
    duplicate_rate: float = 0.0
    issue_density: float = 0.0
    critical_record_rate: float = 0.0
    total_rows: int
    valid_rows: int
    invalid_rows: int
    validation_pass_rate: float
    data_quality_score: float
    total_issues: int
    critical_issues: int
    warning_issues: int
    errors: list[str]
    issue_categories: list[ImportIssueCategoryResponse]
    field_metrics: list[ImportFieldMetricResponse]
    column_mappings: list[ImportColumnMappingResponse]
    unmapped_headers: list[str]
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


class SupplierCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    feed_format: str = Field(default="csv", pattern="^(csv|xml|json)$")


class SupplierResponse(BaseModel):
    id: uuid.UUID
    name: str
    feed_format: str

    model_config = ConfigDict(from_attributes=True)


class ProductResponse(BaseModel):
    id: uuid.UUID
    sku: str
    name: str
    manufacturer: str
    part_number: str
    category: str
    replacement_sku: str | None

    model_config = ConfigDict(from_attributes=True)


class ProductCreateRequest(BaseModel):
    sku: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    manufacturer: str = Field(min_length=1, max_length=160)
    part_number: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=120)
    supplier_id: uuid.UUID | None = None
    replacement_sku: str | None = Field(default=None, max_length=100)


class ProductVariantCreateRequest(BaseModel):
    product_id: uuid.UUID
    variant_sku: str | None = Field(default=None, max_length=100)
    attributes: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    is_active: bool = True


class ProductVariantResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    variant_sku: str | None
    attributes: dict
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SupplierOfferCreateRequest(BaseModel):
    supplier_id: uuid.UUID
    product_id: uuid.UUID | None = None
    supplier_sku: str | None = Field(default=None, max_length=120)
    supplier_product_id: str | None = Field(default=None, max_length=160)
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    currency: str | None = Field(default=None, pattern="^[A-Z]{3}$")
    unit_of_measure: str | None = Field(default=None, max_length=40)
    minimum_order_quantity: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=4)
    lead_time_days: int | None = Field(default=None, ge=0)
    source_url: str | None = Field(default=None, max_length=2048)
    status: str = Field(default="active", pattern="^(active|inactive|discontinued|pending)$")


class SupplierOfferResponse(BaseModel):
    id: uuid.UUID
    supplier_id: uuid.UUID
    product_id: uuid.UUID | None
    supplier_sku: str | None
    supplier_product_id: str | None
    unit_price: Decimal | None
    currency: str | None
    unit_of_measure: str | None
    minimum_order_quantity: Decimal | None
    lead_time_days: int | None
    source_url: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InventorySnapshotCreateRequest(BaseModel):
    product_id: uuid.UUID
    supplier_offer_id: uuid.UUID | None = None
    warehouse_code: str = Field(min_length=1, max_length=120)
    quantity_on_hand: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    quantity_reserved: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    quantity_available: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    snapshot_at: datetime | None = None
    source_reference: str | None = Field(default=None, max_length=255)


class InventorySnapshotResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    supplier_offer_id: uuid.UUID | None
    warehouse_code: str
    quantity_on_hand: Decimal | None
    quantity_reserved: Decimal | None
    quantity_available: Decimal | None
    snapshot_at: datetime
    source_reference: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
