"""
OversightConfig — human oversight toggle.
Two levels: SYSTEM (default for all) and STAGE (per-stage override).
"""
import uuid
from sqlalchemy import String, Float, Boolean, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.db.mixins import TimestampMixin


class OversightMode:
    FULL_AUTOMATION = "FULL_AUTOMATION"
    HUMAN_OVERSIGHT = "HUMAN_OVERSIGHT"


class OversightConfig(Base, TimestampMixin):
    __tablename__ = "oversight_configs"
    __table_args__ = (UniqueConstraint("scope", "stage", name="uq_oversight_scope_stage"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    # SYSTEM | STAGE

    # Only set when scope=STAGE; matches DacaRequestStatus values
    stage: Mapped[str | None] = mapped_column(String(100), nullable=True)

    mode: Mapped[str] = mapped_column(String(30), nullable=False, default=OversightMode.HUMAN_OVERSIGHT)
    # OversightMode.FULL_AUTOMATION | OversightMode.HUMAN_OVERSIGHT

    # When mode=FULL_AUTOMATION: if agent confidence < threshold, still pause for review
    confidence_threshold: Mapped[float] = mapped_column(Float, default=0.85)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    updated_by: Mapped[str | None] = mapped_column(String(200), nullable=True)

    def __repr__(self) -> str:
        stage_label = f":{self.stage}" if self.stage else ""
        return f"<OversightConfig {self.scope}{stage_label}: {self.mode}>"
