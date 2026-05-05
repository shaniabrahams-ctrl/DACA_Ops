"""
TriggerEventAgent — handles springing DACA trigger events.

ALWAYS human-gated per Rho policy: springing triggers require manual verification.

Actions:
  1. Validate the trigger request (lender email vs. known contacts)
  2. Pull account details for the affected DACA
  3. Package all verification data into a HumanReviewItem
  4. Set a 2-hour SLA during business hours (8am–5pm ET)

The operator makes the final decision and executes the trigger in RAP.
"""
import uuid
import logging
from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.agents.base_agent import BaseAgent, AgentResult
from app.models.daca_request import DacaRequest, DacaRequestStatus
from app.models.trigger_event import TriggerEvent
from app.models.lender import Lender
from app.models.borrower import Borrower
from app.models.account import Account
from app.models.human_review import HumanReviewItem

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")
BUSINESS_START = time(8, 0)
BUSINESS_END = time(17, 0)


class TriggerEventAgent(BaseAgent):
    name = "TriggerEventAgent"

    async def run(
        self,
        db: AsyncSession,
        daca_request_id: uuid.UUID,
        input_payload: dict[str, Any],
    ) -> AgentResult:
        """
        Prepare a verification package for a springing trigger event.

        input_payload: {
            trigger_event_id: str,          # UUID of the TriggerEvent record
            requested_by_email: str,        # email that sent the trigger request
            requested_by_name: str | None,
        }
        """
        trigger_event_id = input_payload.get("trigger_event_id")
        requested_by_email = input_payload.get("requested_by_email", "").strip().lower()

        # --- Load the DACA request and related entities ---
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

        # Load trigger event
        trigger_event: TriggerEvent | None = None
        if trigger_event_id:
            te_result = await db.execute(
                select(TriggerEvent).where(TriggerEvent.id == uuid.UUID(str(trigger_event_id)))
            )
            trigger_event = te_result.scalar_one_or_none()

        # Load lender
        lender: Lender | None = None
        if request.lender_id:
            l_result = await db.execute(
                select(Lender).where(Lender.id == request.lender_id)
            )
            lender = l_result.scalar_one_or_none()

        # Load borrower
        borrower: Borrower | None = None
        if request.borrower_id:
            b_result = await db.execute(
                select(Borrower).where(Borrower.id == request.borrower_id)
            )
            borrower = b_result.scalar_one_or_none()

        # Load accounts
        acct_result = await db.execute(
            select(Account).where(Account.daca_request_id == daca_request_id)
        )
        accounts = list(acct_result.scalars().all())

        # --- Step 1: Verify lender email against known contacts ---
        email_match = self._check_email_match(requested_by_email, lender)

        # --- Step 2: Build verification package ---
        account_details = [
            {
                "account_id": str(acct.id),
                "account_type": acct.account_type,
                "account_status": acct.account_status,
                "control_status": acct.control_status,
                "rap_ref": acct.rap_account_ref,
            }
            for acct in accounts
        ]

        lender_contacts = []
        if lender and lender.representatives:
            lender_contacts = lender.representatives

        verification_package = {
            "trigger_event_id": str(trigger_event.id) if trigger_event else None,
            "daca_request_ref": request.external_ref,
            "requested_by_email": requested_by_email,
            "requested_by_name": input_payload.get("requested_by_name"),
            "email_matches_known_contact": email_match["matches"],
            "email_match_details": email_match["details"],
            "lender": {
                "name": lender.institution_name if lender else None,
                "primary_email": lender.primary_contact_email if lender else None,
                "primary_phone": lender.primary_contact_phone if lender else None,
                "representatives": lender_contacts,
            },
            "borrower": {
                "name": borrower.legal_name if borrower else None,
                "contact_email": borrower.primary_contact_email if borrower else None,
            },
            "accounts": account_details,
            "event_type": trigger_event.event_type if trigger_event else "SPRINGING_TRIGGER",
            "lender_notified_webster": (
                trigger_event.lender_notified_webster if trigger_event else False
            ),
            "lender_external_bank_details_provided": (
                trigger_event.lender_external_bank_details_provided if trigger_event else False
            ),
        }

        # --- Step 3: Compute SLA deadline (2 hours during business hours) ---
        sla_deadline = self._compute_sla_deadline()

        # --- Step 4: Create HumanReviewItem ---
        recommendation = self._build_recommendation(email_match, trigger_event)

        review_item = HumanReviewItem(
            daca_request_id=daca_request_id,
            stage=DacaRequestStatus.TRIGGERED,
            review_type="GATE_APPROVAL",
            payload=verification_package,
            agent_recommendation=recommendation,
            agent_confidence=email_match["confidence"],
            agent_name=self.name,
            status="PENDING",
            sla_deadline=sla_deadline,
        )
        db.add(review_item)
        await db.flush()

        return AgentResult(
            success=True,
            output={
                "review_item_id": str(review_item.id),
                "verification_package": verification_package,
                "sla_deadline": sla_deadline.isoformat(),
                "email_verified": email_match["matches"],
            },
            confidence=email_match["confidence"],
            recommendation=recommendation,
            # Never auto-transition — always requires human gate
            next_status=None,
        )

    @staticmethod
    def _check_email_match(
        requested_email: str, lender: Lender | None
    ) -> dict[str, Any]:
        """Check if the requesting email matches any known lender contact."""
        if not lender or not requested_email:
            return {
                "matches": False,
                "confidence": 0.0,
                "details": "No lender record or no email provided.",
            }

        known_emails: list[str] = []

        if lender.primary_contact_email:
            known_emails.append(lender.primary_contact_email.strip().lower())

        if lender.representatives:
            for rep in lender.representatives:
                email = rep.get("email", "").strip().lower()
                if email:
                    known_emails.append(email)

        if requested_email in known_emails:
            return {
                "matches": True,
                "confidence": 0.95,
                "details": (
                    f"Email '{requested_email}' matches a known lender contact. "
                    "Manual verification still required per Rho policy."
                ),
            }

        # Check domain match as a weaker signal
        requested_domain = requested_email.split("@")[-1] if "@" in requested_email else ""
        known_domains = {e.split("@")[-1] for e in known_emails if "@" in e}

        if requested_domain and requested_domain in known_domains:
            return {
                "matches": False,
                "confidence": 0.5,
                "details": (
                    f"Email domain '{requested_domain}' matches lender domain, but the "
                    f"specific address '{requested_email}' is not a known contact. "
                    "Recommend calling the lender's phone number on file to verify."
                ),
            }

        return {
            "matches": False,
            "confidence": 0.1,
            "details": (
                f"Email '{requested_email}' does NOT match any known lender contact. "
                f"Known contacts: {known_emails or 'none on file'}. "
                "Operator MUST call lender's phone number on file to verify authenticity."
            ),
        }

    @staticmethod
    def _compute_sla_deadline() -> datetime:
        """
        Compute a 2-business-hour SLA deadline.
        Business hours: 8am-5pm ET, Monday-Friday.
        """
        now_et = datetime.now(ET)
        remaining_minutes = 120  # 2 hours in minutes

        current = now_et

        # If outside business hours, advance to next business day start
        current = _advance_to_business_hours(current)

        while remaining_minutes > 0:
            end_of_day = current.replace(
                hour=BUSINESS_END.hour, minute=BUSINESS_END.minute, second=0, microsecond=0
            )
            available_minutes = (end_of_day - current).total_seconds() / 60

            if available_minutes >= remaining_minutes:
                current += timedelta(minutes=remaining_minutes)
                remaining_minutes = 0
            else:
                remaining_minutes -= available_minutes
                # Move to next business day
                current = current + timedelta(days=1)
                current = current.replace(
                    hour=BUSINESS_START.hour, minute=BUSINESS_START.minute,
                    second=0, microsecond=0,
                )
                current = _advance_to_business_hours(current)

        return current.astimezone(timezone.utc)

    @staticmethod
    def _build_recommendation(
        email_match: dict[str, Any], trigger_event: TriggerEvent | None
    ) -> str:
        """Build a human-readable recommendation for the reviewer."""
        parts = []

        if email_match["matches"]:
            parts.append(
                "Lender email matches a known contact. Proceed with verification steps."
            )
        else:
            parts.append(
                "WARNING: Lender email does NOT match known contacts. "
                "Call the lender's phone number on file before proceeding."
            )

        if trigger_event and not trigger_event.lender_notified_webster:
            parts.append(
                "Lender has NOT yet notified Webster Bank "
                "(webster_rho_daca@websterbank.com). Remind them this is required per SOP."
            )

        if trigger_event and not trigger_event.lender_external_bank_details_provided:
            parts.append(
                "Lender has NOT provided external bank details. "
                "These are required before the trigger can be executed."
            )

        parts.append(
            "Per Rho policy, springing triggers ALWAYS require manual verification. "
            "Steps: (1) Verify lender identity, (2) Deactivate account in RAP, "
            "(3) Add lender external bank details, (4) Block account, (5) Reactivate."
        )

        return " ".join(parts)


def _advance_to_business_hours(dt: datetime) -> datetime:
    """Advance a datetime to the next business-hours window if currently outside."""
    # Skip weekends
    while dt.weekday() >= 5:  # Saturday=5, Sunday=6
        dt = dt + timedelta(days=1)
        dt = dt.replace(
            hour=BUSINESS_START.hour, minute=BUSINESS_START.minute,
            second=0, microsecond=0,
        )

    # Before business hours — snap to start
    if dt.time() < BUSINESS_START:
        dt = dt.replace(
            hour=BUSINESS_START.hour, minute=BUSINESS_START.minute,
            second=0, microsecond=0,
        )

    # After business hours — next business day
    if dt.time() >= BUSINESS_END:
        dt = dt + timedelta(days=1)
        dt = dt.replace(
            hour=BUSINESS_START.hour, minute=BUSINESS_START.minute,
            second=0, microsecond=0,
        )
        # Recurse in case we landed on a weekend
        dt = _advance_to_business_hours(dt)

    return dt
