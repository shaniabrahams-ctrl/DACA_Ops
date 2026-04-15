"""
Lender — the client's secured creditor (the 'Secured Party' in the DACA agreement).
"""
import uuid
from sqlalchemy import String, Integer, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.mixins import TimestampMixin


class Lender(Base, TimestampMixin):
    __tablename__ = "lenders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # From Typeform: "Your lender's legal entity name"
    institution_name: Mapped[str] = mapped_column(String(500), nullable=False)

    # From Typeform: "Your lender's business address"
    business_address: Mapped[str | None] = mapped_column(Text, nullable=True)

    # From Typeform: "How many lender representatives will have access?"
    rep_count: Mapped[int] = mapped_column(Integer, default=1)

    # Up to 3 lender representatives from Typeform
    # Each: {name, phone, email}
    representatives: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Primary contact (first rep, used for DocuSign + verification)
    primary_contact_email: Mapped[str | None] = mapped_column(String(300), nullable=True, index=True)
    primary_contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Only SPRINGING supported per Rho policy
    daca_type: Mapped[str] = mapped_column(String(50), default="SPRINGING")

    # Relationships
    daca_requests: Mapped[list["DacaRequest"]] = relationship(  # type: ignore[name-defined]
        "DacaRequest", back_populates="lender", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Lender: {self.institution_name}>"
