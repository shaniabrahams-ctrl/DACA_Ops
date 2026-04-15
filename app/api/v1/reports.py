"""
Reports API — pipeline metrics, SLA compliance, agent performance.
"""
from fastapi import APIRouter, Query
from sqlalchemy import select, func

from app.dependencies import SessionDep
from app.models.daca_request import DacaRequest, DacaRequestStatus
from app.models.audit_log import AuditLog
from app.models.human_review import HumanReviewItem
from app.models.agent_execution import AgentExecution
from app.services.sla_service import get_sla_report

router = APIRouter()


@router.get("/pipeline")
async def pipeline_report(db: SessionDep):
    """Count of requests per status."""
    result = await db.execute(
        select(DacaRequest.status, func.count(DacaRequest.id))
        .group_by(DacaRequest.status)
    )
    rows = result.all()
    return {
        "by_status": [{"status": r[0], "count": r[1]} for r in rows],
        "total": sum(r[1] for r in rows),
    }


@router.get("/sla")
async def sla_report(db: SessionDep):
    """SLA compliance metrics and current breaches."""
    return await get_sla_report(db)


@router.get("/agent-performance")
async def agent_performance_report(db: SessionDep):
    """Per-agent execution stats."""
    result = await db.execute(
        select(
            AgentExecution.agent_name,
            func.count(AgentExecution.id).label("total_runs"),
            func.avg(AgentExecution.confidence_score).label("avg_confidence"),
            func.avg(AgentExecution.duration_ms).label("avg_duration_ms"),
        )
        .group_by(AgentExecution.agent_name)
        .order_by(func.count(AgentExecution.id).desc())
    )
    rows = result.all()
    return [
        {
            "agent_name": r.agent_name,
            "total_runs": r.total_runs,
            "avg_confidence": round(float(r.avg_confidence or 0), 3),
            "avg_duration_ms": round(float(r.avg_duration_ms or 0), 1),
        }
        for r in rows
    ]


@router.get("/human-review")
async def human_review_report(db: SessionDep):
    """Review queue stats."""
    total_result = await db.execute(select(func.count(HumanReviewItem.id)))
    total = total_result.scalar() or 0

    pending_result = await db.execute(
        select(func.count(HumanReviewItem.id)).where(HumanReviewItem.status == "PENDING")
    )
    pending = pending_result.scalar() or 0

    approved_result = await db.execute(
        select(func.count(HumanReviewItem.id)).where(HumanReviewItem.status == "APPROVED")
    )
    approved = approved_result.scalar() or 0

    return {
        "total": total,
        "pending": pending,
        "approved": approved,
        "rejected": total - pending - approved,
        "approval_rate": round((approved / (total - pending) * 100) if (total - pending) > 0 else 0.0, 1),
    }


@router.get("/volume")
async def volume_report(
    db: SessionDep,
    days: int = Query(default=30, ge=1, le=365),
):
    """Requests created over the last N days, grouped by day."""
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import cast, Date
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(
            cast(DacaRequest.created_at, Date).label("day"),
            func.count(DacaRequest.id).label("count"),
        )
        .where(DacaRequest.created_at >= since)
        .group_by(cast(DacaRequest.created_at, Date))
        .order_by(cast(DacaRequest.created_at, Date))
    )
    rows = result.all()
    return [{"day": str(r.day), "count": r.count} for r in rows]
