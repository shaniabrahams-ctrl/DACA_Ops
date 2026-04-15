"""
MonitoringSLAAgent — checks SLA status every 15 minutes.

- Warning at 80% SLA elapsed → Slack alert to #daca-ops
- Critical at 100% (deadline reached) → Slack @here + note to assigned_to
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.agents.base_agent import BaseAgent, AgentResult
from app.models.daca_request import DacaRequest, DacaRequestStatus
from app.services.sla_service import calculate_sla_status, SLAStatus
from app.services import notification_service

logger = logging.getLogger(__name__)


class MonitoringSLAAgent(BaseAgent):
    name = "MonitoringSLAAgent"

    async def run(
        self,
        db: AsyncSession,
        daca_request_id: uuid.UUID,
        input_payload: dict[str, Any],
    ) -> AgentResult:
        """Check SLA for a single request. Called by the batch scan below."""
        result = await db.execute(
            select(DacaRequest).where(DacaRequest.id == daca_request_id)
        )
        request = result.scalar_one_or_none()
        if request is None:
            return AgentResult(success=False, output={}, confidence=1.0)

        now = datetime.now(timezone.utc)
        sla = calculate_sla_status(request.sla_deadline, request.created_at, now)

        if sla["status"] in {SLAStatus.WARNING, SLAStatus.CRITICAL}:
            await notification_service.send_sla_alert(
                db,
                external_ref=request.external_ref,
                status=request.status,
                severity=sla["status"],
                hours_remaining=sla["hours_remaining"],
                assigned_to=request.assigned_to,
            )

        return AgentResult(
            success=True,
            output=sla,
            confidence=1.0,
            recommendation=f"SLA status: {sla['status']}",
        )

    async def scan_all_active(self, db: AsyncSession) -> dict[str, Any]:
        """
        Scan all active DACA requests and send SLA alerts as needed.
        Called by Celery beat every 15 minutes.
        """
        terminal = {DacaRequestStatus.DONE, DacaRequestStatus.TERMINATED, DacaRequestStatus.CANCELLED}
        active_statuses = [s for s in DacaRequestStatus.ALL_STATUSES if s not in terminal]

        result = await db.execute(
            select(DacaRequest)
            .where(DacaRequest.status.in_(active_statuses))
            .where(DacaRequest.sla_deadline.is_not(None))
        )
        requests = list(result.scalars().all())

        now = datetime.now(timezone.utc)
        alerts_sent = 0

        for req in requests:
            sla = calculate_sla_status(req.sla_deadline, req.created_at, now)
            if sla["status"] in {SLAStatus.WARNING, SLAStatus.CRITICAL}:
                await notification_service.send_sla_alert(
                    db,
                    external_ref=req.external_ref,
                    status=req.status,
                    severity=sla["status"],
                    hours_remaining=sla["hours_remaining"],
                    assigned_to=req.assigned_to,
                )
                alerts_sent += 1

        logger.info("SLA scan: %d active requests, %d alerts sent", len(requests), alerts_sent)
        return {"scanned": len(requests), "alerts_sent": alerts_sent}
