"""
Pydantic schemas for DacaRequest.
"""
import uuid
from typing import Any
from datetime import datetime
from pydantic import BaseModel


class DacaRequestCreate(BaseModel):
    borrower_id: uuid.UUID | None = None
    lender_id: uuid.UUID | None = None
    source_channel: str = "EMAIL"
    source_reference: str | None = None
    typeform_token: str | None = None
    priority: str = "NORMAL"
    account_type_requested: str | None = None
    assigned_to: str | None = None
    metadata_: dict[str, Any] | None = None


class DacaRequestUpdate(BaseModel):
    borrower_id: uuid.UUID | None = None
    lender_id: uuid.UUID | None = None
    priority: str | None = None
    assigned_to: str | None = None
    jira_ticket_key: str | None = None
    jira_status: str | None = None
    sla_deadline: datetime | None = None
    account_type_requested: str | None = None
    docusign_envelope_id: str | None = None
    has_redlines: bool | None = None
    redlines_approved_by: str | None = None
    redlines_notes: str | None = None
    salesforce_checklist: dict[str, Any] | None = None
    metadata_: dict[str, Any] | None = None


class StatusTransitionRequest(BaseModel):
    target_status: str
    rationale: str | None = None
    confidence: float = 1.0


class DacaRequestOut(BaseModel):
    id: uuid.UUID
    external_ref: str
    borrower_id: uuid.UUID | None
    lender_id: uuid.UUID | None
    status: str
    previous_status: str | None
    priority: str
    source_channel: str
    source_reference: str | None
    typeform_token: str | None
    jira_ticket_key: str | None
    jira_status: str | None
    assigned_to: str | None
    sla_deadline: datetime | None
    account_type_requested: str | None
    docusign_envelope_id: str | None
    has_redlines: bool
    redlines_approved_by: str | None
    redlines_notes: str | None
    salesforce_checklist: dict[str, Any] | None
    metadata_: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DacaRequestListItem(BaseModel):
    """Lightweight representation for list views."""
    id: uuid.UUID
    external_ref: str
    status: str
    priority: str
    assigned_to: str | None
    sla_deadline: datetime | None
    jira_ticket_key: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
