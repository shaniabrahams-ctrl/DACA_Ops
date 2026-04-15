"""
DacaRequest — the central entity tracking the full DACA lifecycle.
Status enum maps 1:1 to the Rho JIRA board statuses.
"""
import uuid
from sqlalchemy import String, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.mixins import TimestampMixin


class DacaRequestStatus:
    """
    Maps to exact JIRA board statuses on the CS team board.
    Order reflects the process flow from the Notion SOP.
    """
    FRAUD_INITIAL_REVIEW = "Fraud Initial Review"
    TYPEFORM_SENT = "Typeform Sent"
    LEGAL_REDLINE_REVIEW = "Legal Redline Review"
    TEMPLATES_AGREEMENTS_SENT = "Templates/Agreements Sent"
    PENDING_COMPLIANCE_ASSEMBLY = "Pending Compliance Package Assembly"
    PRE_WEBSTER_REVIEW = "Pre-Webster Review"          # Internal gate (Shani review)
    DOCUSIGN_SENT = "Docusign Sent"
    PENDING_FINAL_SETUP = "Pending Final Setup"
    DONE = "Done"
    TRIGGERED = "Triggered"                            # Springing trigger event
    TERMINATED = "Terminated"
    CANCELLED = "Cancelled"
    ON_HOLD = "On Hold"

    ALL_STATUSES = [
        FRAUD_INITIAL_REVIEW, TYPEFORM_SENT, LEGAL_REDLINE_REVIEW,
        TEMPLATES_AGREEMENTS_SENT, PENDING_COMPLIANCE_ASSEMBLY,
        PRE_WEBSTER_REVIEW, DOCUSIGN_SENT, PENDING_FINAL_SETUP,
        DONE, TRIGGERED, TERMINATED, CANCELLED, ON_HOLD,
    ]

    # Stages that ALWAYS require human approval — cannot be toggled off
    ALWAYS_HUMAN = {
        FRAUD_INITIAL_REVIEW,
        LEGAL_REDLINE_REVIEW,
        PRE_WEBSTER_REVIEW,
        TRIGGERED,
    }


class DacaRequest(Base, TimestampMixin):
    __tablename__ = "daca_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Human-readable reference (e.g. "DACA-2026-0042")
    external_ref: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    # Foreign keys
    borrower_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("borrowers.id"), nullable=True, index=True
    )
    lender_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lenders.id"), nullable=True, index=True
    )

    # Status — matches exact JIRA status strings
    status: Mapped[str] = mapped_column(
        String(100), nullable=False, default=DacaRequestStatus.FRAUD_INITIAL_REVIEW, index=True
    )
    previous_status: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Priority
    priority: Mapped[str] = mapped_column(String(20), default="NORMAL")
    # NORMAL | HIGH (VIP/premium clients) | URGENT

    # Source
    source_channel: Mapped[str] = mapped_column(String(50), default="EMAIL")
    # EMAIL | TYPEFORM | MANUAL
    source_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    typeform_token: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)

    # Jira
    jira_ticket_key: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    jira_status: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Assignment
    assigned_to: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # SLA tracking
    sla_deadline: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Account setup type
    account_type_requested: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # NEW_ACCOUNT | CONVERT_EXISTING

    # DocuSign envelope ID (pasted in manually during MVP phase)
    docusign_envelope_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Agreement prep
    has_redlines: Mapped[bool] = mapped_column(Boolean, default=False)
    redlines_approved_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    redlines_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Salesforce fields — tracked as manual checklist until API access
    # {field_name: {value, completed_by, completed_at}}
    salesforce_checklist: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Flexible metadata
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    # Relationships
    borrower: Mapped["Borrower"] = relationship("Borrower", back_populates="daca_requests")  # type: ignore[name-defined]
    lender: Mapped["Lender"] = relationship("Lender", back_populates="daca_requests")  # type: ignore[name-defined]
    agreement: Mapped["Agreement | None"] = relationship(  # type: ignore[name-defined]
        "Agreement", back_populates="daca_request", uselist=False
    )
    compliance_package: Mapped["CompliancePackage | None"] = relationship(  # type: ignore[name-defined]
        "CompliancePackage", back_populates="daca_request", uselist=False
    )
    accounts: Mapped[list["Account"]] = relationship("Account", back_populates="daca_request")  # type: ignore[name-defined]
    trigger_events: Mapped[list["TriggerEvent"]] = relationship(  # type: ignore[name-defined]
        "TriggerEvent", back_populates="daca_request"
    )
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="daca_request")  # type: ignore[name-defined]
    documents: Mapped[list["Document"]] = relationship("Document", back_populates="daca_request")  # type: ignore[name-defined]
    email_threads: Mapped[list["EmailThread"]] = relationship(  # type: ignore[name-defined]
        "EmailThread", back_populates="daca_request"
    )
    email_drafts: Mapped[list["EmailDraft"]] = relationship(  # type: ignore[name-defined]
        "EmailDraft", back_populates="daca_request"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(  # type: ignore[name-defined]
        "AuditLog", back_populates="daca_request"
    )
    human_reviews: Mapped[list["HumanReviewItem"]] = relationship(  # type: ignore[name-defined]
        "HumanReviewItem", back_populates="daca_request"
    )

    def __repr__(self) -> str:
        return f"<DacaRequest {self.external_ref}: {self.status}>"
