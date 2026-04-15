import uuid
from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.mixins import TimestampMixin


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    daca_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("daca_requests.id"), nullable=False, index=True
    )

    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # TYPEFORM_PDF | LOAN_AGREEMENT | MIDDESK_REPORT | ALLOY_REPORT |
    # TRACER_REPORT | ARTICLES_OF_INC | NAME_CHANGE_DOCS |
    # DIVISION_OF_CORPS | SIGNED_AGREEMENT | COMPLIANCE_PACKAGE |
    # LENDER_NOTICE | OTHER

    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    google_drive_file_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    google_drive_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    uploaded_by: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # AI-extracted data from document intelligence agent
    ai_extracted_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    validation_status: Mapped[str] = mapped_column(String(50), default="PENDING")
    # PENDING | VALID | INVALID | NEEDS_REVIEW
    validation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    daca_request: Mapped["DacaRequest"] = relationship("DacaRequest", back_populates="documents")  # type: ignore[name-defined]
