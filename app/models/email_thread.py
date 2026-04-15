"""
EmailThread — tracks every email thread involving daca@rho.co (TO or CC).
Powers the email tracking view in the client sub-dashboard.
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.mixins import TimestampMixin


class EmailThread(Base, TimestampMixin):
    __tablename__ = "email_threads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # May be null if email arrives before DacaRequest is created
    daca_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("daca_requests.id"), nullable=True, index=True
    )

    # Gmail thread and message tracking
    gmail_thread_id: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    gmail_message_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # Array of Gmail message IDs in this thread

    # Thread metadata
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    participants: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # All TO/CC/FROM email addresses across the thread

    # Last message details (for at-a-glance view in dashboard)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sender: Mapped[str | None] = mapped_column(String(300), nullable=True)
    last_snippet: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # 150-char preview of most recent message

    # Response tracking — key feature for the email view dashboard
    # True when the last sender was NOT a Rho address (i.e., we owe a reply)
    awaiting_response: Mapped[bool] = mapped_column(Boolean, default=False)
    response_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Slack notification sent to #daca-ops
    slack_notification_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    thread_status: Mapped[str] = mapped_column(String(50), default="ACTIVE")
    # ACTIVE | RESOLVED | ARCHIVED

    # Gmail web link
    gmail_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    daca_request: Mapped["DacaRequest | None"] = relationship(  # type: ignore[name-defined]
        "DacaRequest", back_populates="email_threads"
    )
    email_drafts: Mapped[list["EmailDraft"]] = relationship(  # type: ignore[name-defined]
        "EmailDraft", back_populates="email_thread"
    )

    def __repr__(self) -> str:
        return f"<EmailThread {self.gmail_thread_id}: {self.subject[:50] if self.subject else ''}>"
