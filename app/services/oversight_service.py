"""
Oversight Service — the human oversight toggle chokepoint.

Resolution logic:
  1. If stage is ALWAYS_HUMAN → PAUSE (cannot be overridden)
  2. Look up stage-level config override
  3. If no override, fall back to system-level config
  4. If mode == FULL_AUTOMATION and confidence >= threshold → PROCEED
  5. If mode == FULL_AUTOMATION and confidence < threshold → PAUSE (low confidence)
  6. If mode == HUMAN_OVERSIGHT → PAUSE
"""
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.oversight_config import OversightConfig, OversightMode
from app.models.daca_request import DacaRequestStatus


class GateDecision(str, Enum):
    PROCEED = "PROCEED"
    PAUSE = "PAUSE"


async def check_gate(
    db: AsyncSession,
    stage: str,
    confidence: float = 1.0,
) -> tuple[GateDecision, str]:
    """
    Returns (decision, reason).
    reason explains why the decision was made — logged to audit trail.
    """
    # Step 1: Always-human gates cannot be toggled off
    if stage in DacaRequestStatus.ALWAYS_HUMAN:
        return GateDecision.PAUSE, f"Stage '{stage}' always requires human approval"

    # Step 2: Check for stage-level override
    result = await db.execute(
        select(OversightConfig)
        .where(OversightConfig.scope == "STAGE", OversightConfig.stage == stage, OversightConfig.enabled == True)  # noqa: E712
    )
    stage_config: OversightConfig | None = result.scalar_one_or_none()

    # Step 3: Fall back to system-level config
    config: OversightConfig | None = stage_config
    if config is None:
        result = await db.execute(
            select(OversightConfig)
            .where(OversightConfig.scope == "SYSTEM", OversightConfig.enabled == True)  # noqa: E712
        )
        config = result.scalar_one_or_none()

    # If no config found, default to HUMAN_OVERSIGHT (safe default)
    if config is None:
        return GateDecision.PAUSE, "No oversight config found — defaulting to human oversight"

    if config.mode == OversightMode.HUMAN_OVERSIGHT:
        scope_label = f"stage '{stage}'" if stage_config else "system"
        return GateDecision.PAUSE, f"Human oversight enabled ({scope_label})"

    # mode == FULL_AUTOMATION
    if confidence < config.confidence_threshold:
        return (
            GateDecision.PAUSE,
            f"Agent confidence {confidence:.2f} below threshold {config.confidence_threshold:.2f}",
        )

    return GateDecision.PROCEED, f"Full automation approved (confidence {confidence:.2f})"


async def get_all_configs(db: AsyncSession) -> list[OversightConfig]:
    result = await db.execute(select(OversightConfig).order_by(OversightConfig.scope, OversightConfig.stage))
    return list(result.scalars().all())


async def upsert_system_config(
    db: AsyncSession,
    *,
    mode: str,
    confidence_threshold: float = 0.85,
    updated_by: str | None = None,
) -> OversightConfig:
    result = await db.execute(
        select(OversightConfig).where(OversightConfig.scope == "SYSTEM")
    )
    config = result.scalar_one_or_none()
    if config is None:
        config = OversightConfig(scope="SYSTEM", stage=None)
        db.add(config)
    config.mode = mode
    config.confidence_threshold = confidence_threshold
    config.updated_by = updated_by
    await db.flush()
    return config


async def upsert_stage_config(
    db: AsyncSession,
    *,
    stage: str,
    mode: str,
    confidence_threshold: float = 0.85,
    updated_by: str | None = None,
) -> OversightConfig:
    result = await db.execute(
        select(OversightConfig).where(
            OversightConfig.scope == "STAGE", OversightConfig.stage == stage
        )
    )
    config = result.scalar_one_or_none()
    if config is None:
        config = OversightConfig(scope="STAGE", stage=stage)
        db.add(config)
    config.mode = mode
    config.confidence_threshold = confidence_threshold
    config.updated_by = updated_by
    await db.flush()
    return config
