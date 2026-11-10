from pydantic import BaseModel, ConfigDict, Field

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

class ImportPreviewResponse(BaseModel):
    filename: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    errors: list[str]
    preview: list[ImportPreviewRow]
