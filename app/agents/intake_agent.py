"""
IntakeAgent — polls Gmail and classifies incoming emails.

Trigger: Celery beat every 60 seconds
Actions:
  1. Poll daca@rho.co inbox for unread messages
  2. Classify each email as DACA-related or not
  3. For DACA emails: create DacaRequest, link EmailThread, send Slack alert
  4. For non-DACA: mark read and skip
"""
import uuid
import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.agents.base_agent import BaseAgent, AgentResult
from app.models.daca_request import DacaRequestStatus
from app.models.email_thread import EmailThread

logger = logging.getLogger(__name__)


CLASSIFICATION_SYSTEM = """You are a DACA operations assistant at Rho, a fintech company.
You classify incoming emails to daca@rho.co as DACA-related or not.

A DACA (Deposit Account Control Agreement) email is DACA-related if it:
- Requests a new DACA setup
- References an existing DACA request or agreement
- Is from a lender requesting account control (springing trigger)
- Is a compliance or document request related to a DACA

Respond with JSON only:
{
  "is_daca_related": true/false,
  "confidence": 0.0-1.0,
  "classification": "NEW_REQUEST|TRIGGER_EVENT|COMPLIANCE|GENERAL_INQUIRY|UNKNOWN",
  "summary": "one-sentence summary",
  "priority": "NORMAL|HIGH|URGENT"
}
"""


class IntakeAgent(BaseAgent):
    name = "IntakeAgent"

    async def run(
        self,
        db: AsyncSession,
        daca_request_id: uuid.UUID,
        input_payload: dict[str, Any],
    ) -> AgentResult:
        """
        Classifies a single email message.
        input_payload: {message_id, thread_id, subject, sender, snippet, gmail_url}
        """
        subject = input_payload.get("subject", "")
        sender = input_payload.get("sender", "")
        snippet = input_payload.get("snippet", "")

        prompt = f"""Classify this email:
Subject: {subject}
From: {sender}
Preview: {snippet}"""

        response_text = await self.call_claude(prompt, system=CLASSIFICATION_SYSTEM)

        try:
            # Extract JSON from response
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            classification = json.loads(response_text[start:end])
        except (ValueError, KeyError) as exc:
            logger.warning("Failed to parse classification response: %s", exc)
            classification = {
                "is_daca_related": False,
                "confidence": 0.0,
                "classification": "UNKNOWN",
                "summary": "Failed to classify",
                "priority": "NORMAL",
            }

        return AgentResult(
            success=True,
            output=classification,
            confidence=classification.get("confidence", 0.0),
            recommendation=classification.get("summary"),
            next_status=None,  # IntakeAgent creates new requests, doesn't transition
        )

    async def process_inbox(self, db: AsyncSession) -> list[dict[str, Any]]:
        """
        Poll inbox, classify emails, create DACA requests for relevant ones.
        Called by Celery task.
        """
        from app.integrations import gmail as gmail_integration
        from app.integrations import slack as slack_integration
        from app.services import daca_request_service, notification_service
        from app.config import settings

        messages = await gmail_integration.poll_inbox(max_results=20)
        processed = []

        for msg in messages:
            thread_id = msg["thread_id"]

            # Check if thread already tracked
            existing = await db.execute(
                select(EmailThread).where(EmailThread.gmail_thread_id == thread_id)
            )
            if existing.scalar_one_or_none() is not None:
                # Thread already tracked — update last_message info
                await gmail_integration.mark_as_read(msg["message_id"])
                continue

            # Classify the email
            result = await self.run(
                db,
                daca_request_id=uuid.uuid4(),  # Placeholder — no DACA request yet
                input_payload=msg,
            )

            is_daca = result.output.get("is_daca_related", False)
            await gmail_integration.mark_as_read(msg["message_id"])

            if is_daca:
                # Create a new DACA request
                daca_req = await daca_request_service.create(
                    db,
                    actor_id=self.name,
                    source_channel="EMAIL",
                    source_reference=msg.get("gmail_url"),
                    priority=result.output.get("priority", "NORMAL"),
                )

                # Create email thread record
                thread = EmailThread(
                    daca_request_id=daca_req.id,
                    gmail_thread_id=thread_id,
                    subject=msg.get("subject"),
                    last_sender=msg.get("sender"),
                    awaiting_response=False,  # We haven't replied yet
                    gmail_url=msg.get("gmail_url"),
                )
                db.add(thread)
                await db.flush()

                # Notify #daca-ops
                await notification_service.send_email_alert(
                    db,
                    subject=msg.get("subject", ""),
                    sender=msg.get("sender", ""),
                    snippet=msg.get("snippet", ""),
                    thread_url=msg.get("gmail_url"),
                    external_ref=daca_req.external_ref,
                )

                processed.append({"external_ref": daca_req.external_ref, "thread_id": thread_id})

        return processed
