"""
EmailDraft — AI-generated email drafts queued for operator review.
Drafts are NEVER auto-sent. Operator must review and approve before sending.
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.mixins import TimestampMixin


class DraftType:
    """The 5 standard email macros from the Notion SOP + ad-hoc replies."""
    INTRO_KICKOFF = "INTRO_KICKOFF"                    # "DACA Intro/Process Kick-off"
    TEMPLATE_DISTRIBUTION = "TEMPLATE_DISTRIBUTION"    # "Distribution of Springing DACA Standard Template"
    DOCUSIGN_SENT = "DOCUSIGN_SENT"                    # "DocuSign Sent Communication"
    ACCOUNT_OPERATIONAL = "ACCOUNT_OPERATIONAL"        # Account fully executed and open
    FOLLOW_UP = "FOLLOW_UP"                            # Follow-up for missing docs (3+ days)
    AD_HOC_REPLY = "AD_HOC_REPLY"                      # Operator-triggered reply to specific thread


class EmailDraft(Base, TimestampMixin):
    __tablename__ = "email_drafts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    daca_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("daca_requests.id"), nullable=True, index=True
    )
    email_thread_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_threads.id"), nullable=True, index=True
    )

    draft_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # See DraftType constants above

    # What triggered this draft to be created
    trigger_event: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # e.g. "status_changed_to_DOCUSIGN_SENT" | "operator_clicked_draft_reply" | "3_days_no_docs"

    # Email fields
    to_addresses: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    cc_addresses: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # daca@rho.co is ALWAYS included in CC
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # AI metadata
    ai_model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    context_used: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # What context the agent gathered: thread history, request status, SOP version, etc.

    # Review and send workflow
    status: Mapped[str] = mapped_column(String(50), default="PENDING_REVIEW")
    # PENDING_REVIEW | APPROVED | SENT | DISCARDED

    reviewed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Send method (operator chooses)
    send_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # DASHBOARD_GMAIL_API (primary) | OPEN_IN_GMAIL | OPEN_IN_SUPERHUMAN

    # Gmail tracking after send
    gmail_message_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Relationships
    daca_request: Mapped["DacaRequest | None"] = relationship(  # type: ignore[name-defined]
        "DacaRequest", back_populates="email_drafts"
    )
    email_thread: Mapped["EmailThread | None"] = relationship(  # type: ignore[name-defined]
        "EmailThread", back_populates="email_drafts"
    )

    def __repr__(self) -> str:
        return f"<EmailDraft {self.draft_type}: {self.status}>"
