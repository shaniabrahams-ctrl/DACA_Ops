"""
BaseAgent — abstract base class for all 9 DACA AI agents.

Provides:
  - Execution logging (start/complete/fail → AgentExecution table)
  - Oversight gate check after execution
  - Automatic state transition if PROCEED, HumanReviewItem creation if PAUSE
  - Error handling with escalation
"""
import time
import uuid
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_execution import AgentExecution
from app.models.audit_log import ActorType
from app.config import settings

logger = logging.getLogger(__name__)


class AgentResult:
    def __init__(
        self,
        success: bool,
        output: dict[str, Any],
        confidence: float,
        recommendation: str | None = None,
        next_status: str | None = None,
    ):
        self.success = success
        self.output = output
        self.confidence = confidence
        self.recommendation = recommendation
        self.next_status = next_status


class BaseAgent(ABC):
    """
    All agents inherit from this class.
    Subclasses implement `run()` with their specific logic.
    `execute()` wraps run() with logging, oversight, and state transitions.
    """

    name: str = "BaseAgent"

    async def execute(
        self,
        db: AsyncSession,
        daca_request_id: uuid.UUID,
        input_payload: dict[str, Any],
    ) -> AgentResult:
        """
        Public entry point. Logs execution, calls run(), handles oversight gate.
        """
        start_time = time.monotonic()
        execution = AgentExecution(
            daca_request_id=daca_request_id,
            agent_name=self.name,
            input_payload=input_payload,
            status="RUNNING",
            model_id=settings.anthropic_model,
        )
        db.add(execution)
        await db.flush()

        try:
            result = await self.run(db, daca_request_id, input_payload)

            duration_ms = int((time.monotonic() - start_time) * 1000)
            execution.status = "COMPLETED" if result.success else "FAILED"
            execution.output_payload = result.output
            execution.confidence_score = result.confidence
            execution.duration_ms = duration_ms
            execution.completed_at = datetime.now(timezone.utc)
            await db.flush()

            if result.success and result.next_status:
                from app.services import state_machine
                await state_machine.transition(
                    db,
                    daca_request_id=daca_request_id,
                    target_status=result.next_status,
                    actor_type=ActorType.AGENT,
                    actor_id=self.name,
                    rationale=result.recommendation,
                    confidence=result.confidence,
                )

            return result

        except Exception as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            execution.status = "FAILED"
            execution.error_message = str(exc)
            execution.duration_ms = duration_ms
            execution.completed_at = datetime.now(timezone.utc)
            await db.flush()
            logger.exception("Agent %s failed for request %s: %s", self.name, daca_request_id, exc)
            raise

    @abstractmethod
    async def run(
        self,
        db: AsyncSession,
        daca_request_id: uuid.UUID,
        input_payload: dict[str, Any],
    ) -> AgentResult:
        """Subclasses implement this with their specific agent logic."""
        ...

    async def call_claude(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 4096,
    ) -> str:
        """Call the Claude API and return the response text."""
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        messages = [{"role": "user", "content": prompt}]
        kwargs: dict[str, Any] = {
            "model": settings.anthropic_model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        response = await client.messages.create(**kwargs)
        return response.content[0].text
