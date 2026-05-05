"""
ComplianceAssemblyAgent — validates compliance package completeness.

Checks the 11 checklist items on the CompliancePackage model,
flags missing items, and generates a readiness score.

If all items are complete → recommends transition to PRE_WEBSTER_REVIEW.
"""
import uuid
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.agents.base_agent import BaseAgent, AgentResult
from app.models.daca_request import DacaRequest, DacaRequestStatus
from app.models.compliance_package import CompliancePackage
from app.models.document import Document

logger = logging.getLogger(__name__)


# The 11 compliance checklist items per the Notion SOP.
# Each entry: (field_name, display_label, is_required)
#   - Required items must be True for the package to be complete.
#   - Conditional items (name_change_docs, division_of_corps) are only required
#     when their value is explicitly False (i.e., applicable but not yet uploaded).
CHECKLIST_ITEMS: list[tuple[str, str, bool]] = [
    ("typeform_pdf_attached", "1. Typeform PDF attached", True),
    ("loan_agreement_uploaded", "2. Loan agreement uploaded", False),
    ("compliance_approved", "3. Compliance approval", True),
    ("middesk_report_uploaded", "4. Middesk report uploaded", True),
    ("middesk_address_matches_rap", "5. Address verification (Middesk vs RAP)", True),
    ("ein_tin_match_verified", "6. EIN/TIN match verified", True),
    ("alloy_report_verified", "7. Alloy report verified", True),
    ("signatory_ubo_reports_verified", "8. Signatory/UBO reports verified", True),
    ("articles_of_incorporation_uploaded", "9. Articles of Incorporation uploaded", True),
    ("name_change_docs_uploaded", "10. Name change documents (if applicable)", False),
    ("division_of_corps_filing_uploaded", "11. Division of Corporations filing (if applicable)", False),
]


class ComplianceAssemblyAgent(BaseAgent):
    name = "ComplianceAssemblyAgent"

    async def run(
        self,
        db: AsyncSession,
        daca_request_id: uuid.UUID,
        input_payload: dict[str, Any],
    ) -> AgentResult:
        """
        Validate the compliance package for a DACA request.

        input_payload: {} (no additional input needed — reads from DB)
        """
        # Load DACA request
        req_result = await db.execute(
            select(DacaRequest).where(DacaRequest.id == daca_request_id)
        )
        request = req_result.scalar_one_or_none()
        if request is None:
            return AgentResult(
                success=False,
                output={"error": "DacaRequest not found"},
                confidence=0.0,
            )

        # Load compliance package
        cp_result = await db.execute(
            select(CompliancePackage).where(
                CompliancePackage.daca_request_id == daca_request_id
            )
        )
        package = cp_result.scalar_one_or_none()
        if package is None:
            return AgentResult(
                success=False,
                output={
                    "error": "No CompliancePackage exists for this request.",
                    "recommendation": "Create a CompliancePackage record before running this agent.",
                },
                confidence=0.0,
            )

        # Load associated documents for cross-reference
        doc_result = await db.execute(
            select(Document).where(Document.daca_request_id == daca_request_id)
        )
        documents = list(doc_result.scalars().all())
        doc_types_present = {doc.document_type for doc in documents}

        # --- Check each item ---
        checked_items: list[dict[str, Any]] = []
        missing_items: list[dict[str, Any]] = []
        total_applicable = 0
        total_complete = 0

        for field_name, label, is_required in CHECKLIST_ITEMS:
            value = getattr(package, field_name, None)

            # Determine if this item is applicable
            # Conditional items (name_change_docs, division_of_corps) are only applicable
            # when they are explicitly set to a boolean value (not None).
            is_conditional = field_name in (
                "name_change_docs_uploaded",
                "division_of_corps_filing_uploaded",
            )

            if is_conditional and value is None:
                # Not applicable for this request — skip
                checked_items.append({
                    "field": field_name,
                    "label": label,
                    "status": "NOT_APPLICABLE",
                    "value": None,
                })
                continue

            total_applicable += 1
            is_complete = bool(value)

            item_info = {
                "field": field_name,
                "label": label,
                "status": "COMPLETE" if is_complete else "MISSING",
                "value": value,
                "required": is_required,
            }

            if is_complete:
                total_complete += 1
                checked_items.append(item_info)
            else:
                missing_items.append(item_info)
                checked_items.append(item_info)

        # --- Cross-reference documents ---
        doc_warnings = self._cross_reference_documents(package, doc_types_present)

        # --- Compute readiness score ---
        readiness_score = total_complete / total_applicable if total_applicable > 0 else 0.0

        # --- Determine recommendation ---
        all_required_complete = all(
            item["status"] == "COMPLETE"
            for item in checked_items
            if item.get("required", False)
        )

        if all_required_complete and not missing_items:
            recommendation = (
                f"Compliance package is COMPLETE ({total_complete}/{total_applicable} items). "
                "All required items verified. Recommend transition to Pre-Webster Review."
            )
            next_status = DacaRequestStatus.PRE_WEBSTER_REVIEW
        elif all_required_complete:
            # All required complete, some optional missing
            optional_missing = [
                item["label"] for item in missing_items if not item.get("required", False)
            ]
            recommendation = (
                f"All required compliance items are complete. "
                f"Optional items still missing: {', '.join(optional_missing)}. "
                "Recommend transition to Pre-Webster Review."
            )
            next_status = DacaRequestStatus.PRE_WEBSTER_REVIEW
        else:
            required_missing = [
                item["label"] for item in missing_items if item.get("required", False)
            ]
            recommendation = (
                f"Compliance package is INCOMPLETE ({total_complete}/{total_applicable} items). "
                f"Missing required items: {', '.join(required_missing)}. "
                "Cannot proceed to Pre-Webster Review until all required items are complete."
            )
            next_status = None

        output = {
            "readiness_score": round(readiness_score, 3),
            "total_applicable": total_applicable,
            "total_complete": total_complete,
            "checklist": checked_items,
            "missing_items": [item["label"] for item in missing_items],
            "missing_required": [
                item["label"] for item in missing_items if item.get("required", False)
            ],
            "document_warnings": doc_warnings,
            "is_complete": package.is_complete,
        }

        return AgentResult(
            success=True,
            output=output,
            confidence=readiness_score,
            recommendation=recommendation,
            next_status=next_status,
        )

    @staticmethod
    def _cross_reference_documents(
        package: CompliancePackage, doc_types_present: set[str]
    ) -> list[str]:
        """
        Cross-reference the compliance checklist flags against actual uploaded documents.
        Returns warnings for any mismatches.
        """
        warnings: list[str] = []

        # Check: typeform_pdf_attached flag is True but no TYPEFORM_PDF document
        if package.typeform_pdf_attached and "TYPEFORM_PDF" not in doc_types_present:
            warnings.append(
                "typeform_pdf_attached is marked True but no TYPEFORM_PDF document record found."
            )

        # Check: loan_agreement_uploaded flag is True but no LOAN_AGREEMENT document
        if package.loan_agreement_uploaded and "LOAN_AGREEMENT" not in doc_types_present:
            warnings.append(
                "loan_agreement_uploaded is marked True but no LOAN_AGREEMENT document record found."
            )

        # Check: middesk_report_uploaded flag is True but no MIDDESK_REPORT document
        if package.middesk_report_uploaded and "MIDDESK_REPORT" not in doc_types_present:
            warnings.append(
                "middesk_report_uploaded is marked True but no MIDDESK_REPORT document record found."
            )

        # Check: articles_of_incorporation_uploaded but no ARTICLES_OF_INC document
        if package.articles_of_incorporation_uploaded and "ARTICLES_OF_INC" not in doc_types_present:
            warnings.append(
                "articles_of_incorporation_uploaded is marked True but no ARTICLES_OF_INC "
                "document record found."
            )

        return warnings
