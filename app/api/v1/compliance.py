"""
Compliance Package API.
"""
import uuid
from fastapi import APIRouter, Request
from sqlalchemy import select

from app.dependencies import SessionDep, ActorDep
from app.models.compliance_package import CompliancePackage
from app.models.audit_log import ActorType
from app.schemas.compliance import CompliancePackageUpdate, CompliancePackageOut
from app.services import audit_service

router = APIRouter()


@router.get("/{daca_request_id}", response_model=CompliancePackageOut)
async def get_compliance_package(daca_request_id: uuid.UUID, db: SessionDep):
    from fastapi import HTTPException
    result = await db.execute(
        select(CompliancePackage).where(CompliancePackage.daca_request_id == daca_request_id)
    )
    pkg = result.scalar_one_or_none()
    if pkg is None:
        raise HTTPException(status_code=404, detail="Compliance package not found")
    return pkg


@router.patch("/{package_id}", response_model=CompliancePackageOut)
async def update_compliance_package(
    package_id: uuid.UUID,
    body: CompliancePackageUpdate,
    db: SessionDep,
    actor: ActorDep,
    request: Request,
):
    from fastapi import HTTPException
    result = await db.execute(
        select(CompliancePackage).where(CompliancePackage.id == package_id)
    )
    pkg = result.scalar_one_or_none()
    if pkg is None:
        raise HTTPException(status_code=404, detail="Compliance package not found")

    updates = body.model_dump(exclude_unset=True)
    before = {k: getattr(pkg, k, None) for k in updates}
    for field, value in updates.items():
        setattr(pkg, field, value)
    await db.flush()
    await audit_service.log_event(
        db,
        entity_type="CompliancePackage",
        entity_id=pkg.id,
        action="updated",
        actor_type=ActorType.HUMAN,
        actor_id=actor,
        daca_request_id=pkg.daca_request_id,
        before_state=before,
        after_state=updates,
        ip_address=request.client.host if request.client else None,
    )
    return pkg
