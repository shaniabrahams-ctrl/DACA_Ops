"""
HumanReviewItem — queue for human approval gates.
Created when the oversight gate returns PAUSE.
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Float, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.mixins import TimestampMixin


class HumanReviewItem(Base, TimestampMixin):
    __tablename__ = "human_review_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    daca_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("daca_requests.id"), nullable=False, index=True
    )

    # Which stage this review is blocking
    stage: Mapped[str] = mapped_column(String(100), nullable=False)
    # One of DacaRequestStatus values

    review_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # GATE_APPROVAL | EXCEPTION | ESCALATION | QA_CHECK

    # What the agent produced for human review
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # What the agent would have done (and why) if it could proceed automatically
    agent_recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 0.0 – 1.0; displayed to reviewer so they can see AI certainty level
    agent_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Review outcome
    status: Mapped[str] = mapped_column(String(50), default="PENDING", index=True)
    # PENDING | APPROVED | REJECTED | RETURNED_FOR_REVISION

    assigned_to: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # SLA for review itself
    sla_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationship
    daca_request: Mapped["DacaRequest"] = relationship(  # type: ignore[name-defined]
        "DacaRequest", back_populates="human_reviews"
    )

    def __repr__(self) -> str:
        return f"<HumanReviewItem {self.stage}: {self.status}>"
