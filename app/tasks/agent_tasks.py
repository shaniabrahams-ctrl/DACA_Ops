"""
Agent Celery tasks — async task wrappers for AI agents.
"""
import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Helper to run async functions in Celery tasks."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    name="app.tasks.agent_tasks.run_intake_agent",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def run_intake_agent(self):
    """Poll Gmail and process new emails."""
    async def _run():
        from app.db.session import AsyncSessionLocal
        from app.agents.intake_agent import IntakeAgent

        agent = IntakeAgent()
        async with AsyncSessionLocal() as db:
            try:
                result = await agent.process_inbox(db)
                await db.commit()
                return result
            except Exception as exc:
                await db.rollback()
                logger.exception("IntakeAgent failed: %s", exc)
                raise

    try:
        return _run_async(_run())
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.agent_tasks.run_email_drafting_agent",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def run_email_drafting_agent(self, daca_request_id: str, draft_type: str, context: dict):
    """Generate an email draft for a DACA request."""
    import uuid as _uuid

    async def _run():
        from app.db.session import AsyncSessionLocal
        from app.agents.email_drafting_agent import EmailDraftingAgent

        agent = EmailDraftingAgent()
        async with AsyncSessionLocal() as db:
            try:
                result = await agent.execute(
                    db,
                    daca_request_id=_uuid.UUID(daca_request_id),
                    input_payload={"draft_type": draft_type, "context": context},
                )
                await db.commit()
                return result.output
            except Exception as exc:
                await db.rollback()
                raise

    try:
        return _run_async(_run())
    except Exception as exc:
        raise self.retry(exc=exc)
