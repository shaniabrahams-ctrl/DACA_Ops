"""
Trigger Events API — Springing DACA trigger processing.
ALL trigger events are always human-gated.
"""
import uuid
from fastapi import APIRouter, Query, Request
from sqlalchemy import select

from app.dependencies import SessionDep, ActorDep
from app.models.trigger_event import TriggerEvent
from app.models.audit_log import ActorType
from app.schemas.trigger_event import TriggerEventCreate, TriggerEventUpdate, TriggerEventOut
from app.services import audit_service

router = APIRouter()


@router.post("", response_model=TriggerEventOut, status_code=201)
async def create_trigger_event(
    body: TriggerEventCreate,
    db: SessionDep,
    actor: ActorDep,
    request: Request,
):
    event = TriggerEvent(**body.model_dump())
    db.add(event)
    await db.flush()
    await audit_service.log_event(
        db,
        entity_type="TriggerEvent",
        entity_id=event.id,
        action="trigger_event_created",
        actor_type=ActorType.HUMAN,
        actor_id=actor,
        daca_request_id=event.daca_request_id,
        after_state={"event_type": event.event_type, "requested_by": event.requested_by_email},
        rationale="Springing trigger event initiated — human verification required",
        ip_address=request.client.host if request.client else None,
    )
    return event


@router.get("", response_model=list[TriggerEventOut])
async def list_trigger_events(
    db: SessionDep,
    daca_request_id: uuid.UUID | None = Query(default=None),
    verification_status: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    q = select(TriggerEvent)
    if daca_request_id:
        q = q.where(TriggerEvent.daca_request_id == daca_request_id)
    if verification_status:
        q = q.where(TriggerEvent.verification_status == verification_status)
    q = q.order_by(TriggerEvent.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


@router.get("/{event_id}", response_model=TriggerEventOut)
async def get_trigger_event(event_id: uuid.UUID, db: SessionDep):
    from fastapi import HTTPException
    result = await db.execute(select(TriggerEvent).where(TriggerEvent.id == event_id))
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Trigger event not found")
    return event


@router.patch("/{event_id}", response_model=TriggerEventOut)
async def update_trigger_event(
    event_id: uuid.UUID,
    body: TriggerEventUpdate,
    db: SessionDep,
    actor: ActorDep,
    request: Request,
):
    from fastapi import HTTPException
    result = await db.execute(select(TriggerEvent).where(TriggerEvent.id == event_id))
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Trigger event not found")

    updates = body.model_dump(exclude_unset=True)
    before = {k: getattr(event, k, None) for k in updates}
    for field, value in updates.items():
        setattr(event, field, value)
    await db.flush()
    await audit_service.log_event(
        db,
        entity_type="TriggerEvent",
        entity_id=event.id,
        action="trigger_event_updated",
        actor_type=ActorType.HUMAN,
        actor_id=actor,
        daca_request_id=event.daca_request_id,
        before_state=before,
        after_state=updates,
        ip_address=request.client.host if request.client else None,
    )
    return event
