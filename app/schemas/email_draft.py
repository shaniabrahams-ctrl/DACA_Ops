"""
Pydantic schemas for EmailDraft.
"""
import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel


class EmailDraftCreate(BaseModel):
    daca_request_id: uuid.UUID
    email_thread_id: uuid.UUID | None = None
    draft_type: str  # INTRO_KICKOFF | TEMPLATE_DISTRIBUTION | etc.
    to_addresses: list[str]
    cc_addresses: list[str] | None = None
    subject: str
    body_html: str
    body_text: str | None = None
    send_method: str = "DASHBOARD_GMAIL_API"
    attachments: list[dict[str, Any]] | None = None


class EmailDraftUpdate(BaseModel):
    subject: str | None = None
    body_html: str | None = None
    body_text: str | None = None
    to_addresses: list[str] | None = None
    cc_addresses: list[str] | None = None
    send_method: str | None = None


class EmailDraftOut(BaseModel):
    id: uuid.UUID
    daca_request_id: uuid.UUID
    email_thread_id: uuid.UUID | None
    draft_type: str
    to_addresses: list | None
    cc_addresses: list | None
    subject: str
    body_html: str
    body_text: str | None
    send_method: str
    status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    sent_at: datetime | None
    gmail_message_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
