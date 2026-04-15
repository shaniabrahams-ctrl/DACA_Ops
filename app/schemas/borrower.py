"""
Pydantic schemas for Borrower.
"""
import uuid
from typing import Any
from datetime import datetime
from pydantic import BaseModel, EmailStr


class BorrowerCreate(BaseModel):
    legal_name: str
    dba_name: str | None = None
    entity_type: str | None = None
    state_of_formation: str | None = None
    rho_id: str | None = None
    address: dict[str, Any] | None = None
    primary_contact_name: str | None = None
    primary_contact_email: EmailStr | None = None
    primary_contact_phone: str | None = None
    salesforce_account_id: str | None = None
    has_rho_account: bool = False


class BorrowerUpdate(BaseModel):
    legal_name: str | None = None
    dba_name: str | None = None
    entity_type: str | None = None
    state_of_formation: str | None = None
    rho_id: str | None = None
    address: dict[str, Any] | None = None
    primary_contact_name: str | None = None
    primary_contact_email: EmailStr | None = None
    primary_contact_phone: str | None = None
    salesforce_account_id: str | None = None
    has_rho_account: bool | None = None
    kyb_status: str | None = None
    middesk_report_url: str | None = None
    alloy_report_url: str | None = None


class BorrowerOut(BaseModel):
    id: uuid.UUID
    rho_id: str | None
    legal_name: str
    dba_name: str | None
    entity_type: str | None
    state_of_formation: str | None
    address: dict[str, Any] | None
    primary_contact_name: str | None
    primary_contact_email: str | None
    primary_contact_phone: str | None
    salesforce_account_id: str | None
    has_rho_account: bool
    kyb_status: str
    middesk_report_url: str | None
    alloy_report_url: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
