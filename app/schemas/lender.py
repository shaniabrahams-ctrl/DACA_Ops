"""
Pydantic schemas for Lender.
"""
import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr


class LenderRepresentative(BaseModel):
    name: str
    phone: str | None = None
    email: EmailStr | None = None


class LenderCreate(BaseModel):
    institution_name: str
    business_address: str | None = None
    rep_count: int = 1
    representatives: list[LenderRepresentative] | None = None
    primary_contact_email: EmailStr | None = None
    primary_contact_phone: str | None = None
    daca_type: str = "SPRINGING"


class LenderUpdate(BaseModel):
    institution_name: str | None = None
    business_address: str | None = None
    rep_count: int | None = None
    representatives: list[LenderRepresentative] | None = None
    primary_contact_email: EmailStr | None = None
    primary_contact_phone: str | None = None


class LenderOut(BaseModel):
    id: uuid.UUID
    institution_name: str
    business_address: str | None
    rep_count: int
    representatives: list | None
    primary_contact_email: str | None
    primary_contact_phone: str | None
    daca_type: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
