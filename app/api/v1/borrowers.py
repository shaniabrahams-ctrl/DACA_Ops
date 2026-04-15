"""
Borrowers API.
"""
import uuid
from fastapi import APIRouter, Query, Request
from sqlalchemy import select

from app.dependencies import SessionDep, ActorDep
from app.models.borrower import Borrower
from app.models.audit_log import ActorType
from app.schemas.borrower import BorrowerCreate, BorrowerUpdate, BorrowerOut
from app.services import audit_service

router = APIRouter()


@router.post("", response_model=BorrowerOut, status_code=201)
async def create_borrower(
    body: BorrowerCreate,
    db: SessionDep,
    actor: ActorDep,
    request: Request,
):
    borrower = Borrower(**body.model_dump())
    db.add(borrower)
    await db.flush()
    await audit_service.log_event(
        db,
        entity_type="Borrower",
        entity_id=borrower.id,
        action="created",
        actor_type=ActorType.HUMAN,
        actor_id=actor,
        after_state={"legal_name": borrower.legal_name},
        ip_address=request.client.host if request.client else None,
    )
    return borrower


@router.get("", response_model=list[BorrowerOut])
async def list_borrowers(
    db: SessionDep,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    result = await db.execute(
        select(Borrower).order_by(Borrower.legal_name).offset(offset).limit(limit)
    )
    return list(result.scalars().all())


@router.get("/{borrower_id}", response_model=BorrowerOut)
async def get_borrower(borrower_id: uuid.UUID, db: SessionDep):
    from fastapi import HTTPException
    result = await db.execute(select(Borrower).where(Borrower.id == borrower_id))
    borrower = result.scalar_one_or_none()
    if borrower is None:
        raise HTTPException(status_code=404, detail="Borrower not found")
    return borrower


@router.patch("/{borrower_id}", response_model=BorrowerOut)
async def update_borrower(
    borrower_id: uuid.UUID,
    body: BorrowerUpdate,
    db: SessionDep,
    actor: ActorDep,
    request: Request,
):
    from fastapi import HTTPException
    result = await db.execute(select(Borrower).where(Borrower.id == borrower_id))
    borrower = result.scalar_one_or_none()
    if borrower is None:
        raise HTTPException(status_code=404, detail="Borrower not found")

    updates = body.model_dump(exclude_unset=True)
    before = {k: getattr(borrower, k, None) for k in updates}
    for field, value in updates.items():
        setattr(borrower, field, value)
    await db.flush()
    await audit_service.log_event(
        db,
        entity_type="Borrower",
        entity_id=borrower.id,
        action="updated",
        actor_type=ActorType.HUMAN,
        actor_id=actor,
        before_state=before,
        after_state=updates,
        ip_address=request.client.host if request.client else None,
    )
    return borrower
