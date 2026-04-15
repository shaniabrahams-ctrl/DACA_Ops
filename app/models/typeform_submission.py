"""
TypeformSubmission — raw data from the DACA request application Typeform.
Sheet: 1Oog92OTZ5w4Lss-CSVJ-jos8d4Or3K8qu6EQe0EuvtE (gid: 1055296310)

IMPORTANT: Do NOT refer to this form as a "survey" or "questionnaire".
Always use the term "DACA request application".
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.db.mixins import TimestampMixin


class TypeformSubmission(Base, TimestampMixin):
    __tablename__ = "typeform_submissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Typeform metadata
    token: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Linked to DacaRequest once processed
    daca_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("daca_requests.id"), nullable=True, index=True
    )
    processed: Mapped[bool] = mapped_column(Boolean, default=False)

    # ---- Lender Information ----
    # "Your lender's legal entity name"
    lender_legal_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # "Your lender's business address"
    lender_business_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "How many lender representatives will have access to your Rho account?"
    lender_rep_count: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Lender Representative 1
    lender_rep_1_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    lender_rep_1_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    lender_rep_1_email: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # Lender Representative 2
    lender_rep_2_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    lender_rep_2_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    lender_rep_2_email: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # Lender Representative 3
    lender_rep_3_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    lender_rep_3_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    lender_rep_3_email: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # ---- Borrower Information ----
    # "Does the Borrower have an account with Rho?"
    borrower_has_rho_account: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # "Legal business name"
    borrower_legal_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # "Business address"
    borrower_business_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "Business contact name"
    borrower_contact_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # "Business contact email"
    borrower_contact_email: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # ---- Deal Details ----
    # "Please upload your loan agreement" — file upload URL
    loan_agreement_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "Did someone refer you?"
    referral_source: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # "Are government receivables involved?"
    government_receivables_involved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # "Is there more than one deposit account involved?"
    multiple_accounts_involved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # "Select your preferred transfer method"
    preferred_transfer_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # WIRE | ACH
    # "Is there any additional information you'd like to share?"
    additional_info: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<TypeformSubmission token={self.token} processed={self.processed}>"
