"""
CompliancePackage — KYC/KYB documents and Webster submission package.
Checklist items match the Notion SOP exactly.
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.mixins import TimestampMixin


class CompliancePackage(Base, TimestampMixin):
    __tablename__ = "compliance_packages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    daca_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("daca_requests.id"), nullable=False, unique=True, index=True
    )

    # ---- Compliance Checklist (per Notion SOP) ----

    # 1. DACA request application — downloaded from Typeform, formatted in Word, saved as PDF by CS
    typeform_pdf_attached: Mapped[bool] = mapped_column(Boolean, default=False)

    # 2. Loan agreement — optional but strongly recommended
    loan_agreement_uploaded: Mapped[bool] = mapped_column(Boolean, default=False)

    # 3. Compliance approval
    compliance_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    compliance_approved_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Typically Vladan
    compliance_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 4. Middesk report — current report for Borrower entity at submission time
    middesk_report_uploaded: Mapped[bool] = mapped_column(Boolean, default=False)
    middesk_report_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 5. Address verification — Middesk address must match RAP system and DACA Agreement
    middesk_address_matches_rap: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    address_discrepancy_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # If mismatch: request corporate address change form, official govt form, lease, or utility bill

    # 6. EIN/TIN match report — Middesk verification vs. system records
    ein_tin_match_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # 7. Alloy report — entity good standing verification (or Secretary of State doc if unavailable)
    alloy_report_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    alloy_report_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 8. Signatory/UBO reports — Alloy/Tracer reports
    # If signatory != UBO, separate reports required with: full name, title, SSN, DOB, signing authority proof
    signatory_ubo_reports_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    signatory_equals_ubo: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # 9. Articles of Incorporation
    articles_of_incorporation_uploaded: Mapped[bool] = mapped_column(Boolean, default=False)

    # 10. Name change documents (if applicable)
    name_change_docs_uploaded: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # 11. Division of Corporations filing (if applicable)
    division_of_corps_filing_uploaded: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # ---- Pre-Webster Review Gate ----
    # Shani Abrahams must approve before ANY submission to Webster
    daca_dri_review_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    daca_dri_review_approved_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    daca_dri_review_approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ---- Webster Submission ----
    # Submitted to: webster_rho_daca@websterbank.com, kjamison, shickey, stoliveira
    # CC: Mike Szarowicz, Jeff Pasquerella
    webster_package_drive_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    webster_package_drive_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    webster_submission_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    webster_approval_status: Mapped[str] = mapped_column(String(50), default="NOT_SUBMITTED")
    # NOT_SUBMITTED | PENDING | APPROVED | REJECTED | REVISIONS_REQUESTED

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationship
    daca_request: Mapped["DacaRequest"] = relationship(  # type: ignore[name-defined]
        "DacaRequest", back_populates="compliance_package"
    )

    @property
    def is_complete(self) -> bool:
        """Returns True when all required checklist items are satisfied."""
        required = [
            self.typeform_pdf_attached,
            self.compliance_approved,
            self.middesk_report_uploaded,
            self.ein_tin_match_verified,
            self.alloy_report_verified,
            self.signatory_ubo_reports_verified,
            self.articles_of_incorporation_uploaded,
        ]
        return all(required)

    def __repr__(self) -> str:
        return f"<CompliancePackage {self.daca_request_id}: {self.webster_approval_status}>"
