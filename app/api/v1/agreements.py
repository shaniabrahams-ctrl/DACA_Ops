"""
Agreements API.
"""
import uuid
from fastapi import APIRouter, Request
from sqlalchemy import select

from app.dependencies import SessionDep, ActorDep
from app.models.agreement import Agreement
from app.models.audit_log import ActorType
from app.schemas.agreement import AgreementUpdate, AgreementOut
from app.services import audit_service

router = APIRouter()


@router.get("/{daca_request_id}", response_model=AgreementOut)
async def get_agreement(daca_request_id: uuid.UUID, db: SessionDep):
    from fastapi import HTTPException
    result = await db.execute(
        select(Agreement).where(Agreement.daca_request_id == daca_request_id)
    )
    agreement = result.scalar_one_or_none()
    if agreement is None:
        raise HTTPException(status_code=404, detail="Agreement not found")
    return agreement


@router.patch("/{agreement_id}", response_model=AgreementOut)
async def update_agreement(
    agreement_id: uuid.UUID,
    body: AgreementUpdate,
    db: SessionDep,
    actor: ActorDep,
    request: Request,
):
    from fastapi import HTTPException
    result = await db.execute(select(Agreement).where(Agreement.id == agreement_id))
    agreement = result.scalar_one_or_none()
    if agreement is None:
        raise HTTPException(status_code=404, detail="Agreement not found")

    updates = body.model_dump(exclude_unset=True)
    before = {k: getattr(agreement, k, None) for k in updates}
    for field, value in updates.items():
        setattr(agreement, field, value)
    await db.flush()
    await audit_service.log_event(
        db,
        entity_type="Agreement",
        entity_id=agreement.id,
        action="updated",
        actor_type=ActorType.HUMAN,
        actor_id=actor,
        daca_request_id=agreement.daca_request_id,
        before_state=before,
        after_state=updates,
        ip_address=request.client.host if request.client else None,
    )
    return agreement
