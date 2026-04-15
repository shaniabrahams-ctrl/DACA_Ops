"""
Pydantic schemas for EmailThread.
"""
import uuid
from datetime import datetime
from pydantic import BaseModel


class EmailThreadCreate(BaseModel):
    daca_request_id: uuid.UUID
    gmail_thread_id: str
    subject: str | None = None
    participants: list[str] | None = None


class EmailThreadOut(BaseModel):
    id: uuid.UUID
    daca_request_id: uuid.UUID
    gmail_thread_id: str
    subject: str | None
    participants: list | None
    last_message_at: datetime | None
    last_sender: str | None
    last_snippet: str | None
    awaiting_response: bool
    slack_notification_sent: bool
    thread_status: str
    gmail_url: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
