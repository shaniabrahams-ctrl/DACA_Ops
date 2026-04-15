"""
EmailDraftingAgent — generates AI-drafted emails for operator review.

Emails are NEVER auto-sent. The agent drafts, the operator reviews and sends.

5 SOP macro types:
  1. INTRO_KICKOFF — initial outreach to borrower/lender
  2. TEMPLATE_DISTRIBUTION — sending DACA template docs
  3. DOCUSIGN_SENT — notifying parties that DocuSign envelope is live
  4. ACCOUNT_OPERATIONAL — confirming DACA account is active
  5. FOLLOW_UP — gentle follow-up on outstanding items
  6. AD_HOC_REPLY — LLM-drafted reply to a specific thread

All macros use hardcoded Rho contacts where applicable:
  - Rho DocuSign signer: Mike Szarowicz (mike.szarowicz@rho.co)
  - Webster signer: Melissa Santos (mesantos@websterbank.com)
"""
import uuid
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.agents.base_agent import BaseAgent, AgentResult
from app.models.daca_request import DacaRequest
from app.models.email_draft import EmailDraft, DraftType
from app.models.borrower import Borrower
from app.models.lender import Lender

logger = logging.getLogger(__name__)

DRAFTING_SYSTEM = """You are a professional DACA operations specialist at Rho Financial Technologies.
Draft concise, professional emails for DACA (Deposit Account Control Agreement) operations.
Use formal but friendly tone. Always sign off as 'DACA Operations Team, Rho'.
Return HTML-formatted email body only — no subject line, no preamble."""


class EmailDraftingAgent(BaseAgent):
    name = "EmailDraftingAgent"

    async def run(
        self,
        db: AsyncSession,
        daca_request_id: uuid.UUID,
        input_payload: dict[str, Any],
    ) -> AgentResult:
        """
        input_payload: {
            draft_type: str,
            context: dict,  # extra context for the draft
            thread_context: str | None,  # existing thread text for AD_HOC_REPLY
        }
        """
        draft_type = input_payload.get("draft_type", DraftType.AD_HOC_REPLY)
        context = input_payload.get("context", {})
        thread_context = input_payload.get("thread_context")

        # Load request + relationships
        result = await db.execute(select(DacaRequest).where(DacaRequest.id == daca_request_id))
        request = result.scalar_one_or_none()
        if request is None:
            return AgentResult(success=False, output={"error": "Request not found"}, confidence=0.0)

        borrower_name = ""
        lender_name = ""
        if request.borrower_id:
            b_result = await db.execute(select(Borrower).where(Borrower.id == request.borrower_id))
            borrower = b_result.scalar_one_or_none()
            borrower_name = borrower.legal_name if borrower else ""
        if request.lender_id:
            l_result = await db.execute(select(Lender).where(Lender.id == request.lender_id))
            lender = l_result.scalar_one_or_none()
            lender_name = lender.institution_name if lender else ""

        prompt = self._build_prompt(
            draft_type=draft_type,
            external_ref=request.external_ref,
            borrower_name=borrower_name,
            lender_name=lender_name,
            context=context,
            thread_context=thread_context,
        )

        body_html = await self.call_claude(prompt, system=DRAFTING_SYSTEM)
        subject = self._default_subject(draft_type, request.external_ref, lender_name, borrower_name)

        draft = EmailDraft(
            daca_request_id=daca_request_id,
            draft_type=draft_type,
            subject=subject,
            body_html=body_html,
            to_addresses=context.get("to_addresses", []),
            cc_addresses=context.get("cc_addresses", []),
            send_method="DASHBOARD_GMAIL_API",
            status="DRAFT",
        )
        db.add(draft)
        await db.flush()

        return AgentResult(
            success=True,
            output={"draft_id": str(draft.id), "subject": subject},
            confidence=0.9 if draft_type != DraftType.AD_HOC_REPLY else 0.75,
            recommendation=f"Draft created: {subject}",
        )

    def _build_prompt(
        self,
        draft_type: str,
        external_ref: str,
        borrower_name: str,
        lender_name: str,
        context: dict,
        thread_context: str | None,
    ) -> str:
        base = f"DACA Request: {external_ref}\nBorrower: {borrower_name}\nLender: {lender_name}\n\n"

        if draft_type == DraftType.INTRO_KICKOFF:
            return base + (
                "Draft an introductory email to the borrower and lender introducing the DACA process. "
                "Explain what a DACA is, next steps, and who to contact."
            )
        elif draft_type == DraftType.TEMPLATE_DISTRIBUTION:
            return base + (
                "Draft an email distributing the DACA template documents. "
                "Mention that documents are attached/linked, signing order, and the timeline."
            )
        elif draft_type == DraftType.DOCUSIGN_SENT:
            return base + (
                "Draft an email notifying all parties that DocuSign envelopes have been sent. "
                "Include the signing order: Borrower → Lender → Rho (Mike Szarowicz) → Webster Bank (Melissa Santos). "
                "Ask them to complete within 5 business days."
            )
        elif draft_type == DraftType.ACCOUNT_OPERATIONAL:
            return base + (
                "Draft an email confirming that the DACA clearing account is now operational. "
                "Congratulate all parties and provide a brief summary of what the DACA means going forward."
            )
        elif draft_type == DraftType.FOLLOW_UP:
            outstanding = context.get("outstanding_items", "outstanding items")
            return base + (
                f"Draft a gentle follow-up email asking for updates on: {outstanding}. "
                "Be professional and helpful, not pushy."
            )
        elif draft_type == DraftType.AD_HOC_REPLY:
            thread = f"\n\nExisting thread:\n{thread_context}" if thread_context else ""
            question = context.get("question", "the inquiry below")
            return base + f"Draft a reply to {question}.{thread}"
        else:
            return base + "Draft a professional DACA-related email."

    def _default_subject(
        self, draft_type: str, external_ref: str, lender_name: str, borrower_name: str
    ) -> str:
        subjects = {
            DraftType.INTRO_KICKOFF: f"DACA Setup — {borrower_name} / {lender_name} [{external_ref}]",
            DraftType.TEMPLATE_DISTRIBUTION: f"DACA Templates — {borrower_name} / {lender_name} [{external_ref}]",
            DraftType.DOCUSIGN_SENT: f"DocuSign: DACA Agreement — {borrower_name} / {lender_name} [{external_ref}]",
            DraftType.ACCOUNT_OPERATIONAL: f"DACA Account Active — {borrower_name} / {lender_name} [{external_ref}]",
            DraftType.FOLLOW_UP: f"Follow-Up — DACA {external_ref}",
            DraftType.AD_HOC_REPLY: f"Re: DACA {external_ref}",
        }
        return subjects.get(draft_type, f"DACA {external_ref}")
