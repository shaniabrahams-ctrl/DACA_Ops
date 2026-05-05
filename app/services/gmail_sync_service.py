"""
Gmail Sync Service — polls the daca@rho.co inbox and creates/updates
EmailThread records in the database.

Runs on a schedule (default: every 60 seconds) via the background task scheduler.
"""
import logging
import re
from datetime import datetime, timezone
from email.utils import parseaddr, parsedate_to_datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import AsyncSessionLocal
from app.integrations.gmail import mark_as_read, poll_inbox
from app.models.borrower import Borrower
from app.models.daca_request import DacaRequest
from app.models.email_thread import EmailThread
from app.models.lender import Lender
from app.services.notification_service import send_email_alert

logger = logging.getLogger(__name__)

# Matches DACA-YYYY-NNNN references (e.g. DACA-2026-0047)
DACA_REF_PATTERN = re.compile(r"DACA-\d{4}-\d{4}")


def _extract_email(raw: str) -> str:
    """
    Extract the bare email address from a header value like
    'John Smith <john@example.com>' or plain 'john@example.com'.
    """
    _, addr = parseaddr(raw)
    return addr.lower().strip()


def _collect_participants(sender: str, to: str, cc: str) -> list[str]:
    """
    Collect all unique email addresses from From/To/CC header values.
    Each header may contain comma-separated addresses.
    """
    seen: set[str] = set()
    for raw_field in (sender, to, cc):
        if not raw_field:
            continue
        # Split on commas — handles "Alice <a@b.com>, Bob <c@d.com>"
        for part in raw_field.split(","):
            addr = _extract_email(part.strip())
            if addr:
                seen.add(addr)
    return sorted(seen)


def _is_rho_address(email_or_header: str) -> bool:
    """Return True if the address belongs to @rho.co."""
    addr = _extract_email(email_or_header)
    return addr.endswith("@rho.co")


def _parse_date(date_str: str) -> datetime:
    """Best-effort parse of an RFC 2822 date string into a tz-aware datetime."""
    try:
        dt = parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return datetime.now(timezone.utc)


async def match_thread_to_request(
    db: AsyncSession,
    subject: str,
    participants: list[str],
) -> DacaRequest | None:
    """
    Try to link an email thread to an existing DacaRequest.

    Strategy:
      1. Scan the subject line for a DACA-YYYY-NNNN reference and look it up.
      2. If no ref found, check whether any participant email matches a
         Borrower.primary_contact_email or Lender.primary_contact_email
         that is linked to a DacaRequest.
    """
    # --- Strategy 1: subject contains a DACA external_ref ---
    match = DACA_REF_PATTERN.search(subject or "")
    if match:
        ref = match.group(0)
        result = await db.execute(
            select(DacaRequest).where(DacaRequest.external_ref == ref)
        )
        daca_request = result.scalars().first()
        if daca_request:
            return daca_request

    # --- Strategy 2: match participant emails to borrower/lender contacts ---
    if not participants:
        return None

    # Check borrower contacts
    result = await db.execute(
        select(Borrower).where(
            Borrower.primary_contact_email.in_(participants)
        )
    )
    borrower = result.scalars().first()
    if borrower and borrower.daca_requests:
        # Return the most recently created request for this borrower
        return borrower.daca_requests[-1]

    # Check lender contacts
    result = await db.execute(
        select(Lender).where(
            Lender.primary_contact_email.in_(participants)
        )
    )
    lender = result.scalars().first()
    if lender and lender.daca_requests:
        return lender.daca_requests[-1]

    return None


async def poll_and_sync_emails() -> None:
    """
    Main sync function — polls the daca@rho.co inbox for unread messages and
    creates or updates EmailThread records for each one.

    Designed to be called on a recurring schedule by the background task runner.
    """
    creds = settings.google_service_account_json
    if not creds or creds.startswith("/") or creds == "":
        logger.debug("Gmail sync skipped — GOOGLE_SERVICE_ACCOUNT_JSON not configured")
        return

    try:
        messages = await poll_inbox()
    except Exception:
        logger.exception("Failed to poll Gmail inbox")
        return

    if not messages:
        logger.debug("Gmail sync: no unread messages")
        return

    created = 0
    updated = 0
    errors = 0

    async with AsyncSessionLocal() as db:
        try:
            for msg in messages:
                try:
                    was_created = await _process_message(db, msg)
                    if was_created:
                        created += 1
                    else:
                        updated += 1
                except Exception:
                    errors += 1
                    logger.exception(
                        "Error processing Gmail message %s (thread %s)",
                        msg.get("message_id"),
                        msg.get("thread_id"),
                    )

            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception("Failed to commit Gmail sync transaction")
            return

    logger.info(
        "Gmail sync complete: %d created, %d updated, %d errors (out of %d messages)",
        created,
        updated,
        errors,
        len(messages),
    )


async def _process_message(db: AsyncSession, msg: dict) -> bool:
    """
    Process a single Gmail message dict.

    Returns True if a new EmailThread was created, False if an existing one
    was updated.
    """
    thread_id = msg["thread_id"]
    message_id = msg["message_id"]
    subject = msg.get("subject", "")
    sender = msg.get("sender", "")
    to = msg.get("to", "")
    cc = msg.get("cc", "")
    date_str = msg.get("date_str", "")
    snippet = msg.get("snippet", "")
    gmail_url = msg.get("gmail_url", "")

    message_dt = _parse_date(date_str)
    participants = _collect_participants(sender, to, cc)
    awaiting = not _is_rho_address(sender)

    # Look up existing thread
    result = await db.execute(
        select(EmailThread).where(EmailThread.gmail_thread_id == thread_id)
    )
    email_thread = result.scalars().first()

    is_new = email_thread is None

    if is_new:
        # --- Create new EmailThread ---
        daca_request = await match_thread_to_request(db, subject, participants)

        email_thread = EmailThread(
            gmail_thread_id=thread_id,
            gmail_message_ids=[message_id],
            subject=subject,
            participants=participants,
            last_message_at=message_dt,
            last_sender=sender,
            last_snippet=snippet[:300] if snippet else None,
            awaiting_response=awaiting,
            thread_status="ACTIVE",
            gmail_url=gmail_url,
            daca_request_id=daca_request.id if daca_request else None,
        )
        db.add(email_thread)
        await db.flush()

        # Send Slack notification for new threads
        try:
            await send_email_alert(
                db,
                subject=subject,
                sender=sender,
                snippet=snippet,
                thread_url=gmail_url,
                external_ref=daca_request.external_ref if daca_request else None,
            )
            email_thread.slack_notification_sent = True
        except Exception:
            logger.warning(
                "Failed to send Slack alert for thread %s", thread_id, exc_info=True
            )

    else:
        # --- Update existing EmailThread ---
        existing_ids = email_thread.gmail_message_ids or []
        if message_id not in existing_ids:
            email_thread.gmail_message_ids = existing_ids + [message_id]

        email_thread.last_message_at = message_dt
        email_thread.last_sender = sender
        email_thread.last_snippet = snippet[:300] if snippet else email_thread.last_snippet
        email_thread.awaiting_response = awaiting

        # Merge new participants into existing list
        existing_participants = set(email_thread.participants or [])
        merged = existing_participants | set(participants)
        email_thread.participants = sorted(merged)

        # If thread was not previously linked to a request, try again
        if email_thread.daca_request_id is None:
            daca_request = await match_thread_to_request(db, subject, participants)
            if daca_request:
                email_thread.daca_request_id = daca_request.id

    # Mark message as read in Gmail
    try:
        await mark_as_read(message_id)
    except Exception:
        logger.warning(
            "Failed to mark message %s as read in Gmail", message_id, exc_info=True
        )

    return is_new
