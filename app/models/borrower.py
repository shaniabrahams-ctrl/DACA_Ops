"""
Borrower — the Rho client that is borrowing funds from the lender.
Maps to the 'Debtor' in the DACA agreement.
"""
import uuid
from sqlalchemy import String, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.mixins import TimestampMixin


class Borrower(Base, TimestampMixin):
    __tablename__ = "borrowers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Rho-assigned ID (e.g. "1046" as seen in Webster reports)
    rho_id: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True, index=True)

    # Legal entity details
    legal_name: Mapped[str] = mapped_column(String(500), nullable=False)
    dba_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)  # LLC, CORP, LP, etc.
    state_of_formation: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # EIN stored encrypted — use utils/encryption.py for read/write
    ein_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Address (from Typeform: "Business address")
    address: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # e.g. {"street": "...", "city": "...", "state": "...", "zip": "...", "country": "US"}

    # Primary contact (from Typeform)
    primary_contact_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    primary_contact_email: Mapped[str | None] = mapped_column(String(300), nullable=True, index=True)
    primary_contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Rho system references
    salesforce_account_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    has_rho_account: Mapped[bool] = mapped_column(Boolean, default=False)

    # KYB / compliance status
    kyb_status: Mapped[str] = mapped_column(String(50), default="PENDING")
    # PENDING | VERIFIED | FAILED

    # External compliance tool URLs/references
    middesk_report_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    alloy_report_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    daca_requests: Mapped[list["DacaRequest"]] = relationship(  # type: ignore[name-defined]
        "DacaRequest", back_populates="borrower", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Borrower {self.rho_id}: {self.legal_name}>"
