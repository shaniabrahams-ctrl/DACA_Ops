"""
Email Threads API.
"""
import uuid
from fastapi import APIRouter, Query
from sqlalchemy import select

from app.dependencies import SessionDep
from app.models.email_thread import EmailThread
from app.schemas.email_thread import EmailThreadOut

router = APIRouter()


@router.get("", response_model=list[EmailThreadOut])
async def list_email_threads(
    db: SessionDep,
    daca_request_id: uuid.UUID | None = Query(default=None),
    awaiting_response: bool | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    q = select(EmailThread)
    if daca_request_id:
        q = q.where(EmailThread.daca_request_id == daca_request_id)
    if awaiting_response is not None:
        q = q.where(EmailThread.awaiting_response == awaiting_response)
    q = q.order_by(EmailThread.last_message_at.desc().nulls_last()).offset(offset).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


@router.get("/{thread_id}", response_model=EmailThreadOut)
async def get_email_thread(thread_id: uuid.UUID, db: SessionDep):
    from fastapi import HTTPException
    result = await db.execute(select(EmailThread).where(EmailThread.id == thread_id))
    thread = result.scalar_one_or_none()
    if thread is None:
        raise HTTPException(status_code=404, detail="Email thread not found")
    return thread
