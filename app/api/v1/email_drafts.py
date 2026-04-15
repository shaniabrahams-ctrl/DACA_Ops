"""
Email Drafts API — AI-drafted emails awaiting operator review and send.

Emails are NEVER auto-sent. An operator must explicitly trigger sending
via the dashboard or one of the supported send methods.
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Query, HTTPException, Request
from sqlalchemy import select

from app.dependencies import SessionDep, ActorDep
from app.models.email_draft import EmailDraft
from app.models.audit_log import ActorType
from app.schemas.email_draft import EmailDraftCreate, EmailDraftUpdate, EmailDraftOut
from app.services import audit_service

router = APIRouter()


@router.post("", response_model=EmailDraftOut, status_code=201)
async def create_email_draft(
    body: EmailDraftCreate,
    db: SessionDep,
    actor: ActorDep,
):
    draft = EmailDraft(**body.model_dump())
    db.add(draft)
    await db.flush()
    return draft


@router.get("", response_model=list[EmailDraftOut])
async def list_email_drafts(
    db: SessionDep,
    daca_request_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    q = select(EmailDraft)
    if daca_request_id:
        q = q.where(EmailDraft.daca_request_id == daca_request_id)
    if status:
        q = q.where(EmailDraft.status == status)
    q = q.order_by(EmailDraft.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


@router.get("/{draft_id}", response_model=EmailDraftOut)
async def get_email_draft(draft_id: uuid.UUID, db: SessionDep):
    result = await db.execute(select(EmailDraft).where(EmailDraft.id == draft_id))
    draft = result.scalar_one_or_none()
    if draft is None:
        raise HTTPException(status_code=404, detail="Email draft not found")
    return draft


@router.patch("/{draft_id}", response_model=EmailDraftOut)
async def update_email_draft(
    draft_id: uuid.UUID,
    body: EmailDraftUpdate,
    db: SessionDep,
    actor: ActorDep,
):
    result = await db.execute(select(EmailDraft).where(EmailDraft.id == draft_id))
    draft = result.scalar_one_or_none()
    if draft is None:
        raise HTTPException(status_code=404, detail="Email draft not found")
    if draft.status == "SENT":
        raise HTTPException(status_code=422, detail="Cannot edit a sent draft")

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(draft, field, value)
    await db.flush()
    return draft


@router.post("/{draft_id}/send", response_model=EmailDraftOut)
async def send_email_draft(
    draft_id: uuid.UUID,
    db: SessionDep,
    actor: ActorDep,
    request: Request,
):
    """
    Mark the draft as sent and dispatch via Gmail API (DASHBOARD_GMAIL_API method).
    For OPEN_IN_GMAIL or OPEN_IN_SUPERHUMAN, the client handles opening the link.
    """
    result = await db.execute(select(EmailDraft).where(EmailDraft.id == draft_id))
    draft = result.scalar_one_or_none()
    if draft is None:
        raise HTTPException(status_code=404, detail="Email draft not found")
    if draft.status == "SENT":
        raise HTTPException(status_code=422, detail="Draft already sent")

    if draft.send_method == "DASHBOARD_GMAIL_API":
        # TODO Sprint 3: call gmail integration to actually send
        pass

    draft.status = "SENT"
    draft.sent_at = datetime.now(timezone.utc)
    draft.reviewed_by = actor
    await db.flush()

    await audit_service.log_event(
        db,
        entity_type="EmailDraft",
        entity_id=draft.id,
        action="email_sent",
        actor_type=ActorType.HUMAN,
        actor_id=actor,
        daca_request_id=draft.daca_request_id,
        after_state={"status": "SENT", "send_method": draft.send_method},
        ip_address=request.client.host if request.client else None,
    )
    return draft
