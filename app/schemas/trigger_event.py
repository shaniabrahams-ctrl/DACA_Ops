"""
Pydantic schemas for TriggerEvent.
"""
import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr


class TriggerEventCreate(BaseModel):
    daca_request_id: uuid.UUID
    account_id: uuid.UUID | None = None
    event_type: str = "SPRINGING_TRIGGER"
    requested_by_email: EmailStr | None = None
    requested_by_name: str | None = None
    requested_at: datetime | None = None
    notes: str | None = None


class TriggerEventUpdate(BaseModel):
    lender_notified_webster: bool | None = None
    account_deactivated_at: datetime | None = None
    email_verified: bool | None = None
    email_verification_method: str | None = None
    lender_external_bank_details_provided: bool | None = None
    jira_ticket_key: str | None = None
    verification_status: str | None = None
    executed_at: datetime | None = None
    executed_by: str | None = None
    blocked_in_rap_at: datetime | None = None
    reactivated_after_block_at: datetime | None = None
    control_change_from: str | None = None
    control_change_to: str | None = None
    lender_notified_at: datetime | None = None
    reversal_requested: bool | None = None
    reversal_verified_at: datetime | None = None
    request_document_url: str | None = None
    notes: str | None = None


class TriggerEventOut(BaseModel):
    id: uuid.UUID
    daca_request_id: uuid.UUID
    account_id: uuid.UUID | None
    event_type: str
    requested_by_email: str | None
    requested_by_name: str | None
    requested_at: datetime | None
    lender_notified_webster: bool
    account_deactivated_at: datetime | None
    email_verified: bool | None
    email_verification_method: str | None
    lender_external_bank_details_provided: bool
    jira_ticket_key: str | None
    verification_status: str
    executed_at: datetime | None
    executed_by: str | None
    blocked_in_rap_at: datetime | None
    reactivated_after_block_at: datetime | None
    control_change_from: str | None
    control_change_to: str | None
    lender_notified_at: datetime | None
    reversal_requested: bool
    reversal_verified_at: datetime | None
    request_document_url: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
