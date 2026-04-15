"""
Pydantic schemas for Document.
"""
import uuid
from typing import Any
from datetime import datetime
from pydantic import BaseModel


class DocumentCreate(BaseModel):
    daca_request_id: uuid.UUID
    document_type: str
    file_name: str
    google_drive_file_id: str | None = None
    google_drive_url: str | None = None


class DocumentUpdate(BaseModel):
    validation_status: str | None = None
    ai_extracted_data: dict[str, Any] | None = None
    google_drive_file_id: str | None = None
    google_drive_url: str | None = None


class DocumentOut(BaseModel):
    id: uuid.UUID
    daca_request_id: uuid.UUID
    document_type: str
    file_name: str
    google_drive_file_id: str | None
    google_drive_url: str | None
    validation_status: str | None
    ai_extracted_data: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
