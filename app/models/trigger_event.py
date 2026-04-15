"""
TriggerEvent — Springing DACA trigger (lender requests account control).
SLA: 2 hours during business hours (8am–5pm ET).
This stage is ALWAYS human-gated — no automation permitted.
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.mixins import TimestampMixin


class TriggerEvent(Base, TimestampMixin):
    __tablename__ = "trigger_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    daca_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("daca_requests.id"), nullable=False, index=True
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True, index=True
    )

    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # SPRINGING_TRIGGER | RELEASE | AMENDMENT | TERMINATION

    # Lender request details
    requested_by_email: Mapped[str | None] = mapped_column(String(300), nullable=True)
    requested_by_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Per SOP: lender must also email webster_rho_daca@websterbank.com
    lender_notified_webster: Mapped[bool] = mapped_column(Boolean, default=False)

    # Verification (2-hour SLA)
    # Step 1: Immediately deactivate DACA account in RAP
    account_deactivated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Step 2: Verify lender email against Salesforce + signed agreement
    email_verified: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    email_verification_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # SALESFORCE_MATCH | CALLED_PHONE
    # If email unverified: call lender's phone number on file

    # Did the lender provide external bank details? (required per SOP)
    lender_external_bank_details_provided: Mapped[bool] = mapped_column(Boolean, default=False)

    # Jira ticket (urgent, CC: Mike Szarowicz, Sam Davidson, Jeff P, Zorica Tasic)
    jira_ticket_key: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Ticket stays open until lender has full control

    verification_status: Mapped[str] = mapped_column(String(50), default="PENDING")
    # PENDING | VERIFIED | REJECTED

    # Execution (after verification)
    # Add lender external bank details to RAP → click "Block account" → reactivate
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    blocked_in_rap_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reactivated_after_block_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    control_change_from: Mapped[str | None] = mapped_column(String(50), nullable=True)
    control_change_to: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Rho notifies LENDER only — NOT the borrower
    # "If a Borrower contacts CS, we should direct them to speak with their Lending party."
    lender_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Reversal handling
    reversal_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    reversal_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    request_document_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    daca_request: Mapped["DacaRequest"] = relationship(  # type: ignore[name-defined]
        "DacaRequest", back_populates="trigger_events"
    )
    account: Mapped["Account | None"] = relationship(  # type: ignore[name-defined]
        "Account", back_populates="trigger_events"
    )

    def __repr__(self) -> str:
        return f"<TriggerEvent {self.event_type}: {self.verification_status}>"
