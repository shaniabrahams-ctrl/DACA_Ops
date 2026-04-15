"""
Accounts API.
"""
import uuid
from fastapi import APIRouter, Query, Request
from sqlalchemy import select

from app.dependencies import SessionDep, ActorDep
from app.models.account import Account
from app.models.audit_log import ActorType
from app.schemas.account import AccountCreate, AccountUpdate, AccountOut
from app.services import audit_service

router = APIRouter()


@router.post("", response_model=AccountOut, status_code=201)
async def create_account(
    body: AccountCreate,
    db: SessionDep,
    actor: ActorDep,
    request: Request,
):
    account = Account(**body.model_dump())
    db.add(account)
    await db.flush()
    await audit_service.log_event(
        db,
        entity_type="Account",
        entity_id=account.id,
        action="created",
        actor_type=ActorType.HUMAN,
        actor_id=actor,
        daca_request_id=account.daca_request_id,
        ip_address=request.client.host if request.client else None,
    )
    return account


@router.get("", response_model=list[AccountOut])
async def list_accounts(
    db: SessionDep,
    daca_request_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    q = select(Account)
    if daca_request_id:
        q = q.where(Account.daca_request_id == daca_request_id)
    q = q.order_by(Account.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


@router.get("/{account_id}", response_model=AccountOut)
async def get_account(account_id: uuid.UUID, db: SessionDep):
    from fastapi import HTTPException
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.patch("/{account_id}", response_model=AccountOut)
async def update_account(
    account_id: uuid.UUID,
    body: AccountUpdate,
    db: SessionDep,
    actor: ActorDep,
    request: Request,
):
    from fastapi import HTTPException
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    updates = body.model_dump(exclude_unset=True)
    before = {k: getattr(account, k, None) for k in updates}
    for field, value in updates.items():
        setattr(account, field, value)
    await db.flush()
    await audit_service.log_event(
        db,
        entity_type="Account",
        entity_id=account.id,
        action="updated",
        actor_type=ActorType.HUMAN,
        actor_id=actor,
        daca_request_id=account.daca_request_id,
        before_state=before,
        after_state=updates,
        ip_address=request.client.host if request.client else None,
    )
    return account
