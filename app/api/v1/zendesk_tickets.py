"""
Zendesk Tickets API — list and view DACA-related tickets pulled from Zendesk.
"""
import uuid
from datetime import datetime
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.dependencies import SessionDep
from app.models.zendesk_ticket import ZendeskTicket

router = APIRouter()


class ZendeskTicketOut(BaseModel):
    id: uuid.UUID
    zendesk_ticket_id: int
    daca_request_id: uuid.UUID | None
    subject: str | None
    description: str | None
    status: str | None
    priority: str | None
    ticket_type: str | None
    requester_email: str | None
    requester_name: str | None
    assignee_email: str | None
    tags: list | None
    match_reason: str
    matched_daca_ref: str | None
    web_url: str | None
    zendesk_created_at: datetime | None
    zendesk_updated_at: datetime | None
    last_synced_at: datetime | None
    slack_notification_sent: bool
    last_comment_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=list[ZendeskTicketOut])
async def list_zendesk_tickets(
    db: SessionDep,
    status: str | None = Query(default=None),
    daca_request_id: uuid.UUID | None = Query(default=None),
    match_reason: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    q = select(ZendeskTicket)
    if status:
        q = q.where(ZendeskTicket.status == status)
    if daca_request_id:
        q = q.where(ZendeskTicket.daca_request_id == daca_request_id)
    if match_reason:
        q = q.where(ZendeskTicket.match_reason == match_reason)
    q = q.order_by(ZendeskTicket.zendesk_updated_at.desc().nulls_last()).offset(offset).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


@router.get("/{ticket_id}", response_model=ZendeskTicketOut)
async def get_zendesk_ticket(ticket_id: uuid.UUID, db: SessionDep):
    result = await db.execute(select(ZendeskTicket).where(ZendeskTicket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Zendesk ticket not found")
    return ticket
