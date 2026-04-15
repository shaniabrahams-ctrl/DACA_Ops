"""
Audit Service — creates immutable AuditLog entries.

Every action in the system (human or automated) must produce an audit entry.
Entries are never updated or deleted.
"""
import uuid
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.audit_log import AuditLog, ActorType
from app.models.ops_manual_version import OpsManualVersion


async def _get_current_ops_manual_version(db: AsyncSession) -> str | None:
    """Returns the version_label of the currently active ops manual."""
    result = await db.execute(
        select(OpsManualVersion)
        .where(OpsManualVersion.is_current == True)  # noqa: E712
        .order_by(OpsManualVersion.fetched_at.desc())
        .limit(1)
    )
    version = result.scalar_one_or_none()
    return version.version_label if version else None


async def log_event(
    db: AsyncSession,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    actor_type: str,
    actor_id: str,
    daca_request_id: uuid.UUID | None = None,
    before_state: dict[str, Any] | None = None,
    after_state: dict[str, Any] | None = None,
    rationale: str | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
    include_ops_manual_version: bool = True,
) -> AuditLog:
    """
    Create an immutable audit log entry. Flush (but don't commit) so callers
    can wrap multiple operations in a single transaction.
    """
    ops_manual_version: str | None = None
    if include_ops_manual_version:
        ops_manual_version = await _get_current_ops_manual_version(db)

    entry = AuditLog(
        daca_request_id=daca_request_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_type=actor_type,
        actor_id=actor_id,
        before_state=before_state,
        after_state=after_state,
        rationale=rationale,
        ops_manual_version=ops_manual_version,
        metadata_=metadata,
        ip_address=ip_address,
    )
    db.add(entry)
    await db.flush()
    return entry


async def log_status_change(
    db: AsyncSession,
    *,
    daca_request_id: uuid.UUID,
    from_status: str,
    to_status: str,
    actor_type: str,
    actor_id: str,
    rationale: str | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """Convenience wrapper for status transitions."""
    return await log_event(
        db,
        entity_type="DacaRequest",
        entity_id=daca_request_id,
        action="status_change",
        actor_type=actor_type,
        actor_id=actor_id,
        daca_request_id=daca_request_id,
        before_state={"status": from_status},
        after_state={"status": to_status},
        rationale=rationale,
        ip_address=ip_address,
    )


async def get_timeline(
    db: AsyncSession,
    daca_request_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLog]:
    """Fetch all audit events for a DACA request in chronological order."""
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.daca_request_id == daca_request_id)
        .order_by(AuditLog.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())
