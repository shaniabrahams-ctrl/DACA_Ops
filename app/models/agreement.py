"""
Agreement — the DACA document itself.
Template: "10.24.25 Springing DACA" (Drive file: 1yzdpW6V-jSC_R-CBl2wev7QlDXCUAWzI)
Only this template is approved for use per the Legal Department memo (Feb 27, 2026).
"""
import uuid
from datetime import date, datetime
from sqlalchemy import String, Boolean, Date, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.mixins import TimestampMixin


class Agreement(Base, TimestampMixin):
    __tablename__ = "agreements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    daca_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("daca_requests.id"), nullable=False, unique=True, index=True
    )

    # Template version — must be "10.24.25" per legal policy
    template_version: Mapped[str] = mapped_column(String(50), default="10.24.25")
    agreement_type: Mapped[str] = mapped_column(String(50), default="ORIGINAL")
    # ORIGINAL | AMENDMENT | TERMINATION

    # Google Drive location of generated document
    generated_document_drive_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_document_drive_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # DocuSign tracking
    # During MVP: operator manually creates envelope and pastes ID here
    docusign_envelope_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    signing_status: Mapped[str] = mapped_column(String(50), default="DRAFT")
    # DRAFT | SENT | PARTIALLY_SIGNED | COMPLETED | VOIDED

    # Individual signing timestamps (enforced order: Borrower → Lender → Rho → Webster)
    borrower_signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lender_signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rho_signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Rho signer: Mike Szarowicz (mike.szarowicz@rho.co)
    webster_signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Webster signer: Melissa Santos (mesantos@websterbank.com)

    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Redline tracking
    has_redlines: Mapped[bool] = mapped_column(Boolean, default=False)
    redlines_approved_by_legal: Mapped[bool] = mapped_column(Boolean, default=False)
    redlines_approved_by_webster: Mapped[bool] = mapped_column(Boolean, default=False)
    redlines_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Note: Webster approval for one client does NOT set precedent for future clients

    # Google Drive URL of fully executed (signed) agreement
    executed_document_drive_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationship
    daca_request: Mapped["DacaRequest"] = relationship(  # type: ignore[name-defined]
        "DacaRequest", back_populates="agreement"
    )

    def __repr__(self) -> str:
        return f"<Agreement {self.daca_request_id}: {self.signing_status}>"
