"""
ZendeskTicket — pulled into our corpus whenever:
  1. daca@rho.co is in the requester / cc / collaborators
  2. The ticket subject or body mentions "DACA"

Used to surface DACA-related conversations in Zendesk inside the ops platform
and to fire Slack notifications when a new mention appears.
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Text, ForeignKey, Integer, BigInteger
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.db.mixins import TimestampMixin


class MatchReason:
    DACA_EMAIL_IN_THREAD = "DACA_EMAIL_IN_THREAD"   # daca@rho.co in requester/cc/collaborators
    DACA_KEYWORD = "DACA_KEYWORD"                   # "DACA" appears in subject or body
    DACA_REF_MATCH = "DACA_REF_MATCH"               # subject contains DACA-YYYY-NNNN


class ZendeskTicket(Base, TimestampMixin):
    __tablename__ = "zendesk_tickets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Zendesk's own integer ticket ID — unique
    zendesk_ticket_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)

    # Linked DACA request (if subject/body matches a known external_ref)
    daca_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("daca_requests.id"), nullable=True, index=True
    )

    # Ticket fields
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    # new | open | pending | hold | solved | closed
    priority: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # urgent | high | normal | low
    ticket_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # question | incident | problem | task

    # Requester / participants
    requester_email: Mapped[str | None] = mapped_column(String(300), nullable=True, index=True)
    requester_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    assignee_email: Mapped[str | None] = mapped_column(String(300), nullable=True)
    cc_emails: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    collaborator_emails: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Why we pulled this in (helps explain to operator)
    match_reason: Mapped[str] = mapped_column(String(50), nullable=False)
    # MatchReason constants
    matched_daca_ref: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Web URL to view in Zendesk
    web_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Zendesk timestamps
    zendesk_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    zendesk_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Sync tracking
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    slack_notification_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    last_comment_count: Mapped[int] = mapped_column(Integer, default=0)
    # If next sync sees more comments, fire another Slack alert

    def __repr__(self) -> str:
        return f"<ZendeskTicket #{self.zendesk_ticket_id}: {self.subject[:50] if self.subject else ''}>"
