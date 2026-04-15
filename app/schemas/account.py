"""
Pydantic schemas for Account.
"""
import uuid
from datetime import datetime
from pydantic import BaseModel


class AccountCreate(BaseModel):
    daca_request_id: uuid.UUID
    account_type: str = "CHECKING"
    is_new_account: bool = True
    rho_tenet_account_id: str | None = None
    rap_account_ref: str | None = None
    eng_ticket_key: str | None = None
    routing_number: str | None = None


class AccountUpdate(BaseModel):
    account_status: str | None = None
    control_status: str | None = None
    rho_tenet_account_id: str | None = None
    rap_account_ref: str | None = None
    eng_ticket_key: str | None = None
    routing_number: str | None = None
    lender_ach_routing: str | None = None
    lender_wire_routing: str | None = None
    sweep_cadence: str | None = None
    deactivated_at: datetime | None = None
    reactivated_at: datetime | None = None
    activated_at: datetime | None = None


class AccountOut(BaseModel):
    id: uuid.UUID
    daca_request_id: uuid.UUID
    account_type: str
    routing_number: str | None
    rho_tenet_account_id: str | None
    rap_account_ref: str | None
    is_new_account: bool
    eng_ticket_key: str | None
    account_status: str
    control_status: str
    deactivated_at: datetime | None
    reactivated_at: datetime | None
    activated_at: datetime | None
    lender_ach_routing: str | None
    lender_wire_routing: str | None
    sweep_cadence: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
