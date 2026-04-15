"""
Pydantic schemas for OversightConfig.
"""
import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class OversightConfigUpdate(BaseModel):
    mode: str  # FULL_AUTOMATION | HUMAN_OVERSIGHT
    confidence_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    updated_by: str | None = None


class OversightBulkUpdate(BaseModel):
    """Bulk update multiple stage configs in one call."""
    updates: list[dict]  # [{stage, mode, confidence_threshold}]
    updated_by: str | None = None


class OversightConfigOut(BaseModel):
    id: uuid.UUID
    scope: str
    stage: str | None
    mode: str
    confidence_threshold: float
    enabled: bool
    updated_by: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
