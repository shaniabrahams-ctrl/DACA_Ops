"""
Tests for the human oversight toggle logic.
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daca_request import DacaRequestStatus
from app.models.oversight_config import OversightMode
from app.services import oversight_service
from app.services.oversight_service import GateDecision


class TestOversightGate:
    @pytest.mark.asyncio
    async def test_always_human_always_pauses(self, db: AsyncSession):
        """ALWAYS_HUMAN stages return PAUSE regardless of config."""
        await oversight_service.upsert_system_config(
            db, mode=OversightMode.FULL_AUTOMATION, updated_by="test"
        )
        for stage in DacaRequestStatus.ALWAYS_HUMAN:
            decision, reason = await oversight_service.check_gate(db, stage=stage, confidence=1.0)
            assert decision == GateDecision.PAUSE, f"{stage} should always pause"
            assert "always requires human" in reason

    @pytest.mark.asyncio
    async def test_full_automation_with_high_confidence_proceeds(self, db: AsyncSession):
        """FULL_AUTOMATION + confidence >= threshold should PROCEED."""
        await oversight_service.upsert_system_config(
            db, mode=OversightMode.FULL_AUTOMATION, confidence_threshold=0.85, updated_by="test"
        )
        decision, reason = await oversight_service.check_gate(
            db, stage=DacaRequestStatus.TYPEFORM_SENT, confidence=0.90
        )
        assert decision == GateDecision.PROCEED

    @pytest.mark.asyncio
    async def test_full_automation_low_confidence_pauses(self, db: AsyncSession):
        """FULL_AUTOMATION + confidence < threshold should PAUSE."""
        await oversight_service.upsert_system_config(
            db, mode=OversightMode.FULL_AUTOMATION, confidence_threshold=0.85, updated_by="test"
        )
        decision, reason = await oversight_service.check_gate(
            db, stage=DacaRequestStatus.TYPEFORM_SENT, confidence=0.70
        )
        assert decision == GateDecision.PAUSE
        assert "confidence" in reason.lower()

    @pytest.mark.asyncio
    async def test_human_oversight_mode_always_pauses(self, db: AsyncSession):
        """HUMAN_OVERSIGHT mode should pause all non-terminal stages."""
        await oversight_service.upsert_system_config(
            db, mode=OversightMode.HUMAN_OVERSIGHT, updated_by="test"
        )
        decision, reason = await oversight_service.check_gate(
            db, stage=DacaRequestStatus.TYPEFORM_SENT, confidence=1.0
        )
        assert decision == GateDecision.PAUSE
        assert "human oversight" in reason.lower()

    @pytest.mark.asyncio
    async def test_stage_config_overrides_system_config(self, db: AsyncSession):
        """Stage-level config should override system-level config."""
        # System: HUMAN_OVERSIGHT
        await oversight_service.upsert_system_config(
            db, mode=OversightMode.HUMAN_OVERSIGHT, updated_by="test"
        )
        # Stage override: FULL_AUTOMATION for TYPEFORM_SENT
        await oversight_service.upsert_stage_config(
            db,
            stage=DacaRequestStatus.TYPEFORM_SENT,
            mode=OversightMode.FULL_AUTOMATION,
            confidence_threshold=0.80,
            updated_by="test",
        )

        decision, reason = await oversight_service.check_gate(
            db, stage=DacaRequestStatus.TYPEFORM_SENT, confidence=0.90
        )
        assert decision == GateDecision.PROCEED

    @pytest.mark.asyncio
    async def test_no_config_defaults_to_pause(self, db: AsyncSession):
        """When no config exists, should default to PAUSE (safe default)."""
        decision, reason = await oversight_service.check_gate(
            db, stage=DacaRequestStatus.TYPEFORM_SENT, confidence=1.0
        )
        assert decision == GateDecision.PAUSE

    @pytest.mark.asyncio
    async def test_cannot_automate_always_human_via_stage_config(self, db: AsyncSession):
        """Stage config for always-human stages should be rejected at API level."""
        # The check_gate always returns PAUSE for always-human stages
        # regardless of what's in the DB
        await oversight_service.upsert_stage_config(
            db,
            stage=DacaRequestStatus.TRIGGERED,
            mode=OversightMode.FULL_AUTOMATION,
            updated_by="test",
        )
        decision, _ = await oversight_service.check_gate(
            db, stage=DacaRequestStatus.TRIGGERED, confidence=1.0
        )
        assert decision == GateDecision.PAUSE
