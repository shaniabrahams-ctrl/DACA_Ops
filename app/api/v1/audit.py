"""
Audit Log API — read-only access to the immutable event ledger.
"""
import uuid
from fastapi import APIRouter, Query

from app.dependencies import SessionDep
from app.schemas.audit import AuditLogOut
from app.models.audit_log import AuditLog
from sqlalchemy import select

router = APIRouter()


@router.get("", response_model=list[AuditLogOut])
async def list_audit_logs(
    db: SessionDep,
    entity_type: str | None = Query(default=None),
    action: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    q = select(AuditLog)
    if entity_type:
        q = q.where(AuditLog.entity_type == entity_type)
    if action:
        q = q.where(AuditLog.action == action)
    if actor_id:
        q = q.where(AuditLog.actor_id == actor_id)
    q = q.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(q)
    logs = result.scalars().all()
    return [AuditLogOut.model_validate(log) for log in logs]


@router.get("/{log_id}", response_model=AuditLogOut)
async def get_audit_log(log_id: uuid.UUID, db: SessionDep):
    from fastapi import HTTPException
    result = await db.execute(select(AuditLog).where(AuditLog.id == log_id))
    log = result.scalar_one_or_none()
    if log is None:
        raise HTTPException(status_code=404, detail="Audit log not found")
    return AuditLogOut.model_validate(log)
