"""
AuditLog — immutable event ledger. Never updated after creation.
Every action by every actor (human, agent, system) produces a row here.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class ActorType:
    HUMAN = "HUMAN"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"


class AuditLog(Base):
    """No TimestampMixin — created_at is immutable, no updated_at."""
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # What was affected
    daca_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("daca_requests.id"), nullable=True, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # e.g. "DacaRequest", "Agreement", "CompliancePackage", "TriggerEvent"
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # What happened
    action: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    # e.g. "status_change", "email_sent", "draft_approved", "document_uploaded",
    # "review_approved", "oversight_toggle", "sf_field_updated", "trigger_event_executed"

    # Who did it
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # ActorType.HUMAN | AGENT | SYSTEM
    actor_id: Mapped[str] = mapped_column(String(200), nullable=False)
    # Human: email address (e.g. "shani.abrahams@rho.co") or "local_operator" when auth=NONE
    # Agent: agent class name (e.g. "IntakeAgent")
    # System: "system"

    # What changed
    before_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Why (required for all AI agent actions)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Which SOP version governed this decision
    ops_manual_version: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Additional context
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Immutable timestamp — set once, never changed
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Relationship
    daca_request: Mapped["DacaRequest | None"] = relationship(  # type: ignore[name-defined]
        "DacaRequest", back_populates="audit_logs"
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by {self.actor_id} at {self.created_at}>"
