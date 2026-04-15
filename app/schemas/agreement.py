"""
Pydantic schemas for Agreement.
"""
import uuid
from datetime import date, datetime
from pydantic import BaseModel


class AgreementCreate(BaseModel):
    daca_request_id: uuid.UUID
    agreement_type: str = "ORIGINAL"
    template_version: str = "10.24.25"
    has_redlines: bool = False


class AgreementUpdate(BaseModel):
    docusign_envelope_id: str | None = None
    signing_status: str | None = None
    borrower_signed_at: datetime | None = None
    lender_signed_at: datetime | None = None
    rho_signed_at: datetime | None = None
    webster_signed_at: datetime | None = None
    effective_date: date | None = None
    generated_document_drive_url: str | None = None
    generated_document_drive_id: str | None = None
    executed_document_drive_url: str | None = None
    has_redlines: bool | None = None
    redlines_approved_by_legal: bool | None = None
    redlines_approved_by_webster: bool | None = None
    redlines_notes: str | None = None


class AgreementOut(BaseModel):
    id: uuid.UUID
    daca_request_id: uuid.UUID
    template_version: str
    agreement_type: str
    generated_document_drive_url: str | None
    generated_document_drive_id: str | None
    docusign_envelope_id: str | None
    signing_status: str
    borrower_signed_at: datetime | None
    lender_signed_at: datetime | None
    rho_signed_at: datetime | None
    webster_signed_at: datetime | None
    effective_date: date | None
    has_redlines: bool
    redlines_approved_by_legal: bool
    redlines_approved_by_webster: bool
    redlines_notes: str | None
    executed_document_drive_url: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
