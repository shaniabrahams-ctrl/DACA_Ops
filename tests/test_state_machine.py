"""
Tests for the state machine transitions and oversight gate integration.
"""
import uuid
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.models.daca_request import DacaRequest, DacaRequestStatus
from app.models.oversight_config import OversightConfig, OversightMode
from app.models.audit_log import AuditLog
from app.services import state_machine, oversight_service
from app.models.audit_log import ActorType


async def _create_request(db: AsyncSession, status: str = DacaRequestStatus.FRAUD_INITIAL_REVIEW) -> DacaRequest:
    """Create a minimal DacaRequest for testing."""
    req = DacaRequest(
        external_ref=f"DACA-2026-{uuid.uuid4().hex[:4].upper()}",
        status=status,
    )
    db.add(req)
    await db.flush()
    return req


async def _set_system_mode(db: AsyncSession, mode: str) -> None:
    """Set the system oversight config."""
    await oversight_service.upsert_system_config(db, mode=mode, updated_by="test")


class TestStateMachineTransitions:
    @pytest.mark.asyncio
    async def test_valid_transition_proceeds_with_full_automation(self, db: AsyncSession):
        """Valid transition + FULL_AUTOMATION mode should update status."""
        await _set_system_mode(db, OversightMode.FULL_AUTOMATION)
        req = await _create_request(db)

        result = await state_machine.transition(
            db,
            daca_request_id=req.id,
            target_status=DacaRequestStatus.TYPEFORM_SENT,
            actor_type=ActorType.HUMAN,
            actor_id="local_operator",
        )

        assert result.status == DacaRequestStatus.TYPEFORM_SENT
        assert result.previous_status == DacaRequestStatus.FRAUD_INITIAL_REVIEW

    @pytest.mark.asyncio
    async def test_always_human_gate_pauses_even_in_full_automation(self, db: AsyncSession):
        """ALWAYS_HUMAN stages cannot be toggled off — should always pause."""
        await _set_system_mode(db, OversightMode.FULL_AUTOMATION)
        # FRAUD_INITIAL_REVIEW is always-human, so we cannot auto-transition INTO it
        # Test: transitioning INTO TRIGGERED from DONE (TRIGGERED is always-human)
        req = await _create_request(db, status=DacaRequestStatus.DONE)

        result = await state_machine.transition(
            db,
            daca_request_id=req.id,
            target_status=DacaRequestStatus.TRIGGERED,
            actor_type=ActorType.AGENT,
            actor_id="TestAgent",
            confidence=1.0,
        )

        # Status should be UNCHANGED — paused for human review
        assert result.status == DacaRequestStatus.DONE

    @pytest.mark.asyncio
    async def test_human_oversight_mode_pauses_all_transitions(self, db: AsyncSession):
        """HUMAN_OVERSIGHT mode should pause all automated transitions."""
        await _set_system_mode(db, OversightMode.HUMAN_OVERSIGHT)
        req = await _create_request(db)

        result = await state_machine.transition(
            db,
            daca_request_id=req.id,
            target_status=DacaRequestStatus.TYPEFORM_SENT,
            actor_type=ActorType.AGENT,
            actor_id="IntakeAgent",
            confidence=0.95,
        )

        # Should be paused — status unchanged
        assert result.status == DacaRequestStatus.FRAUD_INITIAL_REVIEW

    @pytest.mark.asyncio
    async def test_low_confidence_pauses_even_in_full_automation(self, db: AsyncSession):
        """Confidence below threshold should pause even in FULL_AUTOMATION."""
        await _set_system_mode(db, OversightMode.FULL_AUTOMATION)
        req = await _create_request(db)

        result = await state_machine.transition(
            db,
            daca_request_id=req.id,
            target_status=DacaRequestStatus.TYPEFORM_SENT,
            actor_type=ActorType.AGENT,
            actor_id="IntakeAgent",
            confidence=0.50,  # Below default threshold of 0.85
        )

        # Should pause due to low confidence
        assert result.status == DacaRequestStatus.FRAUD_INITIAL_REVIEW

    @pytest.mark.asyncio
    async def test_invalid_transition_raises_422(self, db: AsyncSession):
        """Transitioning to a non-allowed status should raise HTTP 422."""
        await _set_system_mode(db, OversightMode.FULL_AUTOMATION)
        req = await _create_request(db)

        with pytest.raises(HTTPException) as exc_info:
            await state_machine.transition(
                db,
                daca_request_id=req.id,
                target_status=DacaRequestStatus.DONE,  # Not allowed from FRAUD_INITIAL_REVIEW
                actor_type=ActorType.HUMAN,
                actor_id="local_operator",
            )
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_transition_creates_audit_log(self, db: AsyncSession):
        """Every successful transition should create an AuditLog entry."""
        from sqlalchemy import select
        await _set_system_mode(db, OversightMode.FULL_AUTOMATION)
        req = await _create_request(db)

        await state_machine.transition(
            db,
            daca_request_id=req.id,
            target_status=DacaRequestStatus.TYPEFORM_SENT,
            actor_type=ActorType.HUMAN,
            actor_id="local_operator",
        )

        logs = await db.execute(
            select(AuditLog).where(
                AuditLog.daca_request_id == req.id,
                AuditLog.action == "status_change",
            )
        )
        log_list = logs.scalars().all()
        assert len(log_list) >= 1
        assert log_list[0].before_state == {"status": DacaRequestStatus.FRAUD_INITIAL_REVIEW}
        assert log_list[0].after_state == {"status": DacaRequestStatus.TYPEFORM_SENT}

    @pytest.mark.asyncio
    async def test_transition_sets_sla_deadline(self, db: AsyncSession):
        """Transitioning to a status with SLA should set sla_deadline."""
        await _set_system_mode(db, OversightMode.FULL_AUTOMATION)
        req = await _create_request(db)

        result = await state_machine.transition(
            db,
            daca_request_id=req.id,
            target_status=DacaRequestStatus.TYPEFORM_SENT,
            actor_type=ActorType.HUMAN,
            actor_id="local_operator",
        )

        assert result.sla_deadline is not None
