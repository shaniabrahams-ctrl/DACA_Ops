"""
DACA Request Service — CRUD and business logic for DacaRequest.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException

from app.models.daca_request import DacaRequest, DacaRequestStatus
from app.models.compliance_package import CompliancePackage
from app.models.agreement import Agreement
from app.models.audit_log import ActorType
from app.services import audit_service


def _next_external_ref(year: int, sequence: int) -> str:
    return f"DACA-{year}-{sequence:04d}"


async def create(
    db: AsyncSession,
    *,
    actor_id: str,
    borrower_id: uuid.UUID | None = None,
    lender_id: uuid.UUID | None = None,
    source_channel: str = "EMAIL",
    source_reference: str | None = None,
    typeform_token: str | None = None,
    priority: str = "NORMAL",
    account_type_requested: str | None = None,
    assigned_to: str | None = None,
    metadata: dict | None = None,
    ip_address: str | None = None,
) -> DacaRequest:
    # Generate external_ref — count existing requests this year
    year = datetime.now(timezone.utc).year
    count_result = await db.execute(
        select(func.count(DacaRequest.id)).where(
            DacaRequest.external_ref.like(f"DACA-{year}-%")
        )
    )
    count = (count_result.scalar() or 0) + 1
    external_ref = _next_external_ref(year, count)

    request = DacaRequest(
        external_ref=external_ref,
        borrower_id=borrower_id,
        lender_id=lender_id,
        source_channel=source_channel,
        source_reference=source_reference,
        typeform_token=typeform_token,
        priority=priority,
        account_type_requested=account_type_requested,
        assigned_to=assigned_to,
        metadata_=metadata,
        status=DacaRequestStatus.FRAUD_INITIAL_REVIEW,
    )
    db.add(request)
    await db.flush()

    # Create empty compliance package and agreement shells
    compliance = CompliancePackage(daca_request_id=request.id)
    agreement = Agreement(daca_request_id=request.id)
    db.add(compliance)
    db.add(agreement)
    await db.flush()

    await audit_service.log_event(
        db,
        entity_type="DacaRequest",
        entity_id=request.id,
        action="created",
        actor_type=ActorType.HUMAN,
        actor_id=actor_id,
        daca_request_id=request.id,
        after_state={"external_ref": external_ref, "status": request.status},
        ip_address=ip_address,
    )
    return request


async def get_by_id(db: AsyncSession, request_id: uuid.UUID) -> DacaRequest:
    result = await db.execute(select(DacaRequest).where(DacaRequest.id == request_id))
    request = result.scalar_one_or_none()
    if request is None:
        raise HTTPException(status_code=404, detail="DACA request not found")
    return request


async def get_by_external_ref(db: AsyncSession, external_ref: str) -> DacaRequest:
    result = await db.execute(
        select(DacaRequest).where(DacaRequest.external_ref == external_ref)
    )
    request = result.scalar_one_or_none()
    if request is None:
        raise HTTPException(status_code=404, detail=f"DACA request '{external_ref}' not found")
    return request


async def list_requests(
    db: AsyncSession,
    *,
    status: str | None = None,
    priority: str | None = None,
    assigned_to: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[DacaRequest]:
    q = select(DacaRequest)
    if status:
        q = q.where(DacaRequest.status == status)
    if priority:
        q = q.where(DacaRequest.priority == priority)
    if assigned_to:
        q = q.where(DacaRequest.assigned_to == assigned_to)
    q = q.order_by(DacaRequest.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


async def update(
    db: AsyncSession,
    *,
    request_id: uuid.UUID,
    actor_id: str,
    updates: dict,
    ip_address: str | None = None,
) -> DacaRequest:
    request = await get_by_id(db, request_id)
    before = {k: getattr(request, k, None) for k in updates}

    for field, value in updates.items():
        setattr(request, field, value)
    await db.flush()

    await audit_service.log_event(
        db,
        entity_type="DacaRequest",
        entity_id=request.id,
        action="updated",
        actor_type=ActorType.HUMAN,
        actor_id=actor_id,
        daca_request_id=request.id,
        before_state=before,
        after_state=updates,
        ip_address=ip_address,
    )
    return request
