"""
SLA Service — tracks deadline breaches and calculates urgency levels.

SLA thresholds:
  - WARNING: 80% of SLA elapsed
  - CRITICAL: 100% (at or past deadline)

Special case: TriggerEvent SLA = 2 business hours (8am-5pm ET).
"""
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.daca_request import DacaRequest, DacaRequestStatus


class SLAStatus:
    ON_TRACK = "ON_TRACK"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    NO_SLA = "NO_SLA"


def calculate_sla_status(
    sla_deadline: datetime | None,
    created_at: datetime,
    now: datetime | None = None,
) -> dict:
    """
    Returns {status, pct_elapsed, hours_remaining, deadline}.
    """
    if sla_deadline is None:
        return {"status": SLAStatus.NO_SLA, "pct_elapsed": None, "hours_remaining": None, "deadline": None}

    now = now or datetime.now(timezone.utc)
    total_hours = (sla_deadline - created_at).total_seconds() / 3600
    elapsed_hours = (now - created_at).total_seconds() / 3600

    if total_hours <= 0:
        pct = 100.0
    else:
        pct = min((elapsed_hours / total_hours) * 100, 100.0)

    hours_remaining = (sla_deadline - now).total_seconds() / 3600

    if hours_remaining <= 0:
        status = SLAStatus.CRITICAL
    elif pct >= 80:
        status = SLAStatus.WARNING
    else:
        status = SLAStatus.ON_TRACK

    return {
        "status": status,
        "pct_elapsed": round(pct, 1),
        "hours_remaining": round(hours_remaining, 1),
        "deadline": sla_deadline.isoformat(),
    }


async def get_sla_report(db: AsyncSession) -> dict:
    """Returns SLA compliance summary across active requests."""
    active_statuses = [
        s for s in DacaRequestStatus.ALL_STATUSES
        if s not in {DacaRequestStatus.DONE, DacaRequestStatus.TERMINATED, DacaRequestStatus.CANCELLED}
    ]
    result = await db.execute(
        select(DacaRequest).where(DacaRequest.status.in_(active_statuses))
    )
    requests = list(result.scalars().all())

    now = datetime.now(timezone.utc)
    on_track = warning = critical = no_sla = 0
    breaches = []

    for req in requests:
        sla = calculate_sla_status(req.sla_deadline, req.created_at, now)
        if sla["status"] == SLAStatus.ON_TRACK:
            on_track += 1
        elif sla["status"] == SLAStatus.WARNING:
            warning += 1
        elif sla["status"] == SLAStatus.CRITICAL:
            critical += 1
            breaches.append({
                "external_ref": req.external_ref,
                "status": req.status,
                "deadline": sla["deadline"],
                "hours_overdue": abs(sla["hours_remaining"]),
            })
        else:
            no_sla += 1

    total = len(requests)
    compliant = on_track + warning
    return {
        "total_active": total,
        "on_track": on_track,
        "warning": warning,
        "critical": critical,
        "no_sla": no_sla,
        "compliance_pct": round((compliant / total * 100) if total > 0 else 100.0, 1),
        "breaches": breaches,
    }
