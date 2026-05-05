"""
AgreementGenerationAgent — generates DACA agreements from template.

Template: "10.24.25 Springing DACA" (Drive file: 1yzdpW6V-jSC_R-CBl2wev7QlDXCUAWzI)
Only this template version is approved per the Legal Department memo (Feb 27, 2026).

Actions:
  1. Download the approved .docx template from Google Drive
  2. Populate template fields (borrower name, lender name, account details, effective date)
  3. Upload generated document to Google Drive client files folder
  4. Create an Agreement record linking the generated doc

If has_redlines=True on the DacaRequest, escalate to human review instead of
auto-generating — redlined agreements require legal review.
"""
import io
import uuid
import logging
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.agents.base_agent import BaseAgent, AgentResult
from app.models.daca_request import DacaRequest, DacaRequestStatus
from app.models.agreement import Agreement
from app.models.borrower import Borrower
from app.models.lender import Lender
from app.models.account import Account
from app.models.human_review import HumanReviewItem
from app.config import settings

logger = logging.getLogger(__name__)

TEMPLATE_FILE_ID = settings.drive_daca_template_file_id
CLIENT_FILES_FOLDER_ID = settings.drive_client_files_folder_id
TEMPLATE_VERSION = "10.24.25"


class AgreementGenerationAgent(BaseAgent):
    name = "AgreementGenerationAgent"

    async def run(
        self,
        db: AsyncSession,
        daca_request_id: uuid.UUID,
        input_payload: dict[str, Any],
    ) -> AgentResult:
        """
        Generate a DACA agreement from the approved template.

        input_payload: {
            effective_date: str | None,  # ISO date, defaults to today
        }
        """
        # --- Load DACA request ---
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

        # --- Check for redlines ---
        if request.has_redlines:
            return await self._escalate_for_redlines(db, request)

        # --- Load related entities ---
        borrower = await self._load_borrower(db, request.borrower_id)
        lender = await self._load_lender(db, request.lender_id)
        accounts = await self._load_accounts(db, daca_request_id)

        if not borrower:
            return AgentResult(
                success=False,
                output={"error": "Borrower not found. Cannot generate agreement without borrower details."},
                confidence=0.0,
            )
        if not lender:
            return AgentResult(
                success=False,
                output={"error": "Lender not found. Cannot generate agreement without lender details."},
                confidence=0.0,
            )

        # --- Parse effective date ---
        effective_date_str = input_payload.get("effective_date")
        if effective_date_str:
            effective_date = date.fromisoformat(effective_date_str)
        else:
            effective_date = date.today()

        # --- Build template data ---
        template_data = self._build_template_data(
            request=request,
            borrower=borrower,
            lender=lender,
            accounts=accounts,
            effective_date=effective_date,
        )

        # --- Download template, populate, upload ---
        try:
            generated_doc_bytes = await self._generate_document(template_data)
        except Exception as exc:
            logger.error("Failed to generate agreement document: %s", exc)
            return AgentResult(
                success=False,
                output={"error": f"Document generation failed: {exc}"},
                confidence=0.0,
            )

        file_name = (
            f"DACA Agreement - {borrower.legal_name} - "
            f"{lender.institution_name} - {request.external_ref}.docx"
        )

        try:
            drive_result = await self._upload_to_drive(generated_doc_bytes, file_name)
        except Exception as exc:
            logger.error("Failed to upload agreement to Drive: %s", exc)
            return AgentResult(
                success=False,
                output={"error": f"Drive upload failed: {exc}"},
                confidence=0.0,
            )

        # --- Create or update Agreement record ---
        agreement = await self._upsert_agreement(
            db=db,
            daca_request_id=daca_request_id,
            drive_result=drive_result,
            effective_date=effective_date,
        )

        return AgentResult(
            success=True,
            output={
                "agreement_id": str(agreement.id),
                "drive_file_id": drive_result.get("id"),
                "drive_url": drive_result.get("webViewLink"),
                "file_name": file_name,
                "template_version": TEMPLATE_VERSION,
                "effective_date": effective_date.isoformat(),
                "populated_fields": list(template_data.keys()),
            },
            confidence=1.0,
            recommendation=(
                f"Agreement generated from template v{TEMPLATE_VERSION} and uploaded to Drive. "
                f"Ready for distribution to signing parties."
            ),
            next_status=DacaRequestStatus.TEMPLATES_AGREEMENTS_SENT,
        )

    async def _escalate_for_redlines(
        self, db: AsyncSession, request: DacaRequest
    ) -> AgentResult:
        """Create a HumanReviewItem for redlined agreements that need legal review."""
        review_item = HumanReviewItem(
            daca_request_id=request.id,
            stage=DacaRequestStatus.LEGAL_REDLINE_REVIEW,
            review_type="GATE_APPROVAL",
            payload={
                "reason": "has_redlines",
                "external_ref": request.external_ref,
                "redlines_notes": request.redlines_notes,
                "message": (
                    "This DACA request has redlines. The standard template cannot be "
                    "auto-generated. Legal must review and prepare a custom agreement."
                ),
            },
            agent_recommendation=(
                "Request has redlines — cannot auto-generate from standard template. "
                "Legal team must prepare a custom agreement and get Webster approval. "
                "Note: Webster approval for one client does NOT set precedent for future clients."
            ),
            agent_confidence=1.0,
            agent_name=self.name,
            status="PENDING",
        )
        db.add(review_item)
        await db.flush()

        return AgentResult(
            success=True,
            output={
                "escalated": True,
                "reason": "has_redlines",
                "review_item_id": str(review_item.id),
            },
            confidence=1.0,
            recommendation=(
                "Redlined agreement — escalated to human review. "
                "Legal must prepare a custom agreement."
            ),
            # Do not auto-transition; human must handle redline review
            next_status=None,
        )

    @staticmethod
    def _build_template_data(
        request: DacaRequest,
        borrower: Borrower,
        lender: Lender,
        accounts: list[Account],
        effective_date: date,
    ) -> dict[str, str]:
        """Build the field mapping for template population."""
        # Account details — list all checking accounts
        account_lines = []
        for acct in accounts:
            line = f"Account Type: {acct.account_type}"
            if acct.routing_number:
                line += f", Routing: {acct.routing_number}"
            if acct.rap_account_ref:
                line += f", Ref: {acct.rap_account_ref}"
            account_lines.append(line)
        account_details_str = "\n".join(account_lines) if account_lines else "See attached schedule"

        # Borrower address
        borrower_address = ""
        if borrower.address:
            addr = borrower.address
            parts = [
                addr.get("street", ""),
                addr.get("city", ""),
                addr.get("state", ""),
                addr.get("zip", ""),
            ]
            borrower_address = ", ".join(p for p in parts if p)

        # Lender address
        lender_address = lender.business_address or ""

        return {
            "BORROWER_LEGAL_NAME": borrower.legal_name,
            "BORROWER_ADDRESS": borrower_address,
            "LENDER_LEGAL_NAME": lender.institution_name,
            "LENDER_ADDRESS": lender_address,
            "ACCOUNT_DETAILS": account_details_str,
            "EFFECTIVE_DATE": effective_date.strftime("%B %d, %Y"),
            "DACA_REF": request.external_ref,
        }

    @staticmethod
    async def _generate_document(template_data: dict[str, str]) -> bytes:
        """
        Download the template from Drive and populate placeholder fields.
        Uses python-docx for deterministic template population (no AI needed).
        """
        import asyncio
        from docx import Document as DocxDocument
        from app.integrations import google_drive as drive_integration

        # Download the template
        template_bytes = await drive_integration.download_file(TEMPLATE_FILE_ID)

        loop = asyncio.get_event_loop()

        def _populate():
            doc = DocxDocument(io.BytesIO(template_bytes))

            # Replace placeholders in paragraphs
            for paragraph in doc.paragraphs:
                _replace_in_paragraph(paragraph, template_data)

            # Replace placeholders in tables
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for paragraph in cell.paragraphs:
                            _replace_in_paragraph(paragraph, template_data)

            # Replace placeholders in headers/footers
            for section in doc.sections:
                for header_footer in [section.header, section.footer]:
                    for paragraph in header_footer.paragraphs:
                        _replace_in_paragraph(paragraph, template_data)

            output = io.BytesIO()
            doc.save(output)
            return output.getvalue()

        return await loop.run_in_executor(None, _populate)

    @staticmethod
    async def _upload_to_drive(
        doc_bytes: bytes, file_name: str
    ) -> dict[str, str]:
        """Upload the generated document to the client files folder on Drive."""
        from app.integrations import google_drive as drive_integration

        return await drive_integration.upload_file(
            file_content=doc_bytes,
            file_name=file_name,
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            folder_id=CLIENT_FILES_FOLDER_ID,
        )

    @staticmethod
    async def _upsert_agreement(
        db: AsyncSession,
        daca_request_id: uuid.UUID,
        drive_result: dict[str, str],
        effective_date: date,
    ) -> Agreement:
        """Create or update the Agreement record for this request."""
        result = await db.execute(
            select(Agreement).where(Agreement.daca_request_id == daca_request_id)
        )
        agreement = result.scalar_one_or_none()

        if agreement is None:
            agreement = Agreement(
                daca_request_id=daca_request_id,
                template_version=TEMPLATE_VERSION,
                agreement_type="ORIGINAL",
                generated_document_drive_id=drive_result.get("id"),
                generated_document_drive_url=drive_result.get("webViewLink"),
                effective_date=effective_date,
                signing_status="DRAFT",
            )
            db.add(agreement)
        else:
            agreement.generated_document_drive_id = drive_result.get("id")
            agreement.generated_document_drive_url = drive_result.get("webViewLink")
            agreement.effective_date = effective_date
            agreement.template_version = TEMPLATE_VERSION

        await db.flush()
        return agreement

    @staticmethod
    async def _load_borrower(
        db: AsyncSession, borrower_id: uuid.UUID | None
    ) -> Borrower | None:
        if not borrower_id:
            return None
        result = await db.execute(select(Borrower).where(Borrower.id == borrower_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def _load_lender(
        db: AsyncSession, lender_id: uuid.UUID | None
    ) -> Lender | None:
        if not lender_id:
            return None
        result = await db.execute(select(Lender).where(Lender.id == lender_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def _load_accounts(
        db: AsyncSession, daca_request_id: uuid.UUID
    ) -> list[Account]:
        result = await db.execute(
            select(Account).where(Account.daca_request_id == daca_request_id)
        )
        return list(result.scalars().all())


def _replace_in_paragraph(paragraph, template_data: dict[str, str]) -> None:
    """
    Replace placeholder tokens in a python-docx paragraph while preserving formatting.

    Placeholders are expected as {{FIELD_NAME}} in the template.
    We operate on runs to preserve font/style formatting.
    """
    full_text = paragraph.text
    if not any(f"{{{{{key}}}}}" in full_text for key in template_data):
        return

    # Perform replacements on the full text
    new_text = full_text
    for key, value in template_data.items():
        placeholder = f"{{{{{key}}}}}"
        new_text = new_text.replace(placeholder, value)

    if new_text == full_text:
        return

    # Rewrite the runs: clear all runs, write new text into the first run
    # to preserve the paragraph-level style.
    if paragraph.runs:
        # Keep first run's formatting, clear the rest
        first_run = paragraph.runs[0]
        for run in paragraph.runs[1:]:
            run.text = ""
        first_run.text = new_text
    else:
        paragraph.text = new_text
