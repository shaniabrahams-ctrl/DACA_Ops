"""
Pydantic schemas for CompliancePackage.
"""
import uuid
from datetime import datetime, date
from pydantic import BaseModel


class CompliancePackageUpdate(BaseModel):
    # Checklist items (from Notion SOP)
    typeform_pdf_attached: bool | None = None
    loan_agreement_uploaded: bool | None = None
    compliance_approved: bool | None = None
    middesk_report_uploaded: bool | None = None
    middesk_address_matches_rap: bool | None = None
    ein_tin_match_verified: bool | None = None
    alloy_report_verified: bool | None = None
    signatory_ubo_reports_verified: bool | None = None
    articles_of_incorporation_uploaded: bool | None = None
    name_change_docs_uploaded: bool | None = None
    division_of_corps_filing_uploaded: bool | None = None

    # Pre-Webster review
    pre_webster_reviewed_by: str | None = None
    pre_webster_reviewed_at: datetime | None = None
    pre_webster_notes: str | None = None

    # Webster submission
    webster_package_drive_id: str | None = None
    webster_package_drive_url: str | None = None
    webster_submission_date: date | None = None
    webster_approval_status: str | None = None
    webster_approved_at: datetime | None = None
    webster_revisions_notes: str | None = None


class CompliancePackageOut(BaseModel):
    id: uuid.UUID
    daca_request_id: uuid.UUID
    # Checklist
    typeform_pdf_attached: bool
    loan_agreement_uploaded: bool
    compliance_approved: bool
    middesk_report_uploaded: bool
    middesk_address_matches_rap: bool
    ein_tin_match_verified: bool
    alloy_report_verified: bool
    signatory_ubo_reports_verified: bool
    articles_of_incorporation_uploaded: bool
    name_change_docs_uploaded: bool
    division_of_corps_filing_uploaded: bool
    # Pre-Webster
    pre_webster_reviewed_by: str | None
    pre_webster_reviewed_at: datetime | None
    pre_webster_notes: str | None
    # Webster
    webster_package_drive_id: str | None
    webster_package_drive_url: str | None
    webster_submission_date: date | None
    webster_approval_status: str | None
    webster_approved_at: datetime | None
    webster_revisions_notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
