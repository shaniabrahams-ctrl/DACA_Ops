"""
SLA and reporting Celery tasks.
"""
import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="app.tasks.sla_tasks.run_sla_check")
def run_sla_check():
    """Run SLA check across all active DACA requests."""
    async def _run():
        from app.db.session import AsyncSessionLocal
        from app.agents.monitoring_sla_agent import MonitoringSLAAgent

        agent = MonitoringSLAAgent()
        async with AsyncSessionLocal() as db:
            try:
                result = await agent.scan_all_active(db)
                await db.commit()
                return result
            except Exception as exc:
                await db.rollback()
                logger.exception("SLA check failed: %s", exc)
                raise

    return _run_async(_run())


@celery_app.task(name="app.tasks.sla_tasks.send_weekly_status_update")
def send_weekly_status_update():
    """Send Tuesday 10AM ET weekly DACA status update to #daca-ops."""
    async def _run():
        from app.db.session import AsyncSessionLocal
        from app.db.session import AsyncSessionLocal
        from app.models.daca_request import DacaRequest, DacaRequestStatus
        from app.models.borrower import Borrower
        from app.models.lender import Lender
        from app.models.notification_channel import NotificationType, NotificationChannel
        from app.integrations import slack as slack_integration
        from app.services.sla_service import calculate_sla_status, SLAStatus
        from app.config import settings
        from datetime import datetime, timezone
        from sqlalchemy import select

        terminal = {DacaRequestStatus.DONE, DacaRequestStatus.TERMINATED, DacaRequestStatus.CANCELLED}
        active_statuses = [s for s in DacaRequestStatus.ALL_STATUSES if s not in terminal]

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(DacaRequest)
                .where(DacaRequest.status.in_(active_statuses))
                .order_by(DacaRequest.priority.desc(), DacaRequest.created_at.asc())
            )
            requests = list(result.scalars().all())

            updates = []
            now = datetime.now(timezone.utc)

            for req in requests:
                sla = calculate_sla_status(req.sla_deadline, req.created_at, now)

                # Traffic light emoji based on SLA
                if sla["status"] == SLAStatus.CRITICAL:
                    emoji = ":red_circle:"
                elif sla["status"] == SLAStatus.WARNING:
                    emoji = ":yellow_circle:"
                else:
                    emoji = ":large_green_circle:"

                # Resolve borrower/lender names
                borrower_name = ""
                lender_name = ""
                if req.borrower_id:
                    b = await db.get(Borrower, req.borrower_id)
                    borrower_name = b.legal_name if b else ""
                if req.lender_id:
                    l = await db.get(Lender, req.lender_id)
                    lender_name = l.institution_name if l else ""

                updates.append({
                    "external_ref": req.external_ref,
                    "borrower": borrower_name,
                    "lender": lender_name,
                    "status": req.status,
                    "emoji": emoji,
                    "note": f"SLA: {sla['hours_remaining']:.1f}h remaining" if sla["hours_remaining"] else "",
                })

            # Get enabled channels for WEEKLY_UPDATE
            ch_result = await db.execute(
                select(NotificationChannel).where(
                    NotificationChannel.notification_type == NotificationType.WEEKLY_UPDATE,
                    NotificationChannel.enabled == True,  # noqa: E712
                )
            )
            channels = [nc.channel_id for nc in ch_result.scalars().all()]
            if not channels:
                channels = [settings.slack_daca_ops_channel_id]

            for channel_id in channels:
                try:
                    await slack_integration.send_weekly_update(channel_id=channel_id, updates=updates)
                except Exception as exc:
                    logger.warning("Weekly update failed for channel %s: %s", channel_id, exc)

            await db.commit()
            return {"updates_sent": len(updates), "channels": channels}

    return _run_async(_run())
