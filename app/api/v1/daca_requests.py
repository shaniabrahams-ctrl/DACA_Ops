"""
DACA Requests API — CRUD + state transitions.
"""
import uuid
from fastapi import APIRouter, HTTPException, Query, Request

from app.dependencies import SessionDep, ActorDep
from app.schemas.daca_request import (
    DacaRequestCreate,
    DacaRequestUpdate,
    DacaRequestOut,
    DacaRequestListItem,
    StatusTransitionRequest,
)
from app.services import daca_request_service, state_machine, audit_service

router = APIRouter()


@router.post("", response_model=DacaRequestOut, status_code=201)
async def create_daca_request(
    body: DacaRequestCreate,
    db: SessionDep,
    actor: ActorDep,
    request: Request,
):
    req = await daca_request_service.create(
        db,
        actor_id=actor,
        borrower_id=body.borrower_id,
        lender_id=body.lender_id,
        source_channel=body.source_channel,
        source_reference=body.source_reference,
        typeform_token=body.typeform_token,
        priority=body.priority,
        account_type_requested=body.account_type_requested,
        assigned_to=body.assigned_to,
        metadata=body.metadata_,
        ip_address=request.client.host if request.client else None,
    )
    return req


@router.get("", response_model=list[DacaRequestListItem])
async def list_daca_requests(
    db: SessionDep,
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    assigned_to: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    return await daca_request_service.list_requests(
        db, status=status, priority=priority, assigned_to=assigned_to,
        limit=limit, offset=offset,
    )


@router.get("/{request_id}", response_model=DacaRequestOut)
async def get_daca_request(request_id: uuid.UUID, db: SessionDep):
    return await daca_request_service.get_by_id(db, request_id)


@router.patch("/{request_id}", response_model=DacaRequestOut)
async def update_daca_request(
    request_id: uuid.UUID,
    body: DacaRequestUpdate,
    db: SessionDep,
    actor: ActorDep,
    request: Request,
):
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    return await daca_request_service.update(
        db,
        request_id=request_id,
        actor_id=actor,
        updates=updates,
        ip_address=request.client.host if request.client else None,
    )


@router.post("/{request_id}/transition", response_model=DacaRequestOut)
async def transition_status(
    request_id: uuid.UUID,
    body: StatusTransitionRequest,
    db: SessionDep,
    actor: ActorDep,
    request: Request,
):
    """
    Attempt a status transition. If oversight gate pauses it,
    a HumanReviewItem is created and the current status is returned unchanged.
    """
    from app.models.audit_log import ActorType
    req = await state_machine.transition(
        db,
        daca_request_id=request_id,
        target_status=body.target_status,
        actor_type=ActorType.HUMAN,
        actor_id=actor,
        rationale=body.rationale,
        confidence=body.confidence,
        ip_address=request.client.host if request.client else None,
    )
    return req


@router.get("/{request_id}/timeline")
async def get_timeline(
    request_id: uuid.UUID,
    db: SessionDep,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
):
    """Full chronological audit timeline for a single DACA request."""
    from app.schemas.audit import AuditLogOut
    logs = await audit_service.get_timeline(db, request_id, limit=limit, offset=offset)
    return [AuditLogOut.model_validate(log) for log in logs]
