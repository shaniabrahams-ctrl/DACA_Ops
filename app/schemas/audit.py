"""
Pydantic schemas for AuditLog.
"""
import uuid
from typing import Any
from datetime import datetime
from pydantic import BaseModel


class AuditLogCreate(BaseModel):
    daca_request_id: uuid.UUID | None = None
    entity_type: str
    entity_id: uuid.UUID
    action: str
    actor_type: str
    actor_id: str
    before_state: dict[str, Any] | None = None
    after_state: dict[str, Any] | None = None
    rationale: str | None = None
    ops_manual_version: str | None = None
    metadata_: dict[str, Any] | None = None
    ip_address: str | None = None


class AuditLogOut(BaseModel):
    id: uuid.UUID
    daca_request_id: uuid.UUID | None
    entity_type: str
    entity_id: uuid.UUID
    action: str
    actor_type: str
    actor_id: str
    before_state: dict[str, Any] | None
    after_state: dict[str, Any] | None
    rationale: str | None
    ops_manual_version: str | None
    metadata_: dict[str, Any] | None
    ip_address: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
