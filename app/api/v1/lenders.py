"""
Lenders API.
"""
import uuid
from fastapi import APIRouter, Query, Request
from sqlalchemy import select

from app.dependencies import SessionDep, ActorDep
from app.models.lender import Lender
from app.models.audit_log import ActorType
from app.schemas.lender import LenderCreate, LenderUpdate, LenderOut
from app.services import audit_service

router = APIRouter()


@router.post("", response_model=LenderOut, status_code=201)
async def create_lender(
    body: LenderCreate,
    db: SessionDep,
    actor: ActorDep,
    request: Request,
):
    data = body.model_dump()
    if data.get("representatives"):
        data["representatives"] = [r.model_dump() if hasattr(r, "model_dump") else r for r in body.representatives or []]
    lender = Lender(**data)
    db.add(lender)
    await db.flush()
    await audit_service.log_event(
        db,
        entity_type="Lender",
        entity_id=lender.id,
        action="created",
        actor_type=ActorType.HUMAN,
        actor_id=actor,
        after_state={"institution_name": lender.institution_name},
        ip_address=request.client.host if request.client else None,
    )
    return lender


@router.get("", response_model=list[LenderOut])
async def list_lenders(
    db: SessionDep,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    result = await db.execute(
        select(Lender).order_by(Lender.institution_name).offset(offset).limit(limit)
    )
    return list(result.scalars().all())


@router.get("/{lender_id}", response_model=LenderOut)
async def get_lender(lender_id: uuid.UUID, db: SessionDep):
    from fastapi import HTTPException
    result = await db.execute(select(Lender).where(Lender.id == lender_id))
    lender = result.scalar_one_or_none()
    if lender is None:
        raise HTTPException(status_code=404, detail="Lender not found")
    return lender


@router.patch("/{lender_id}", response_model=LenderOut)
async def update_lender(
    lender_id: uuid.UUID,
    body: LenderUpdate,
    db: SessionDep,
    actor: ActorDep,
    request: Request,
):
    from fastapi import HTTPException
    result = await db.execute(select(Lender).where(Lender.id == lender_id))
    lender = result.scalar_one_or_none()
    if lender is None:
        raise HTTPException(status_code=404, detail="Lender not found")

    updates = body.model_dump(exclude_unset=True)
    before = {k: getattr(lender, k, None) for k in updates}
    for field, value in updates.items():
        setattr(lender, field, value)
    await db.flush()
    await audit_service.log_event(
        db,
        entity_type="Lender",
        entity_id=lender.id,
        action="updated",
        actor_type=ActorType.HUMAN,
        actor_id=actor,
        before_state=before,
        after_state=updates,
        ip_address=request.client.host if request.client else None,
    )
    return lender
