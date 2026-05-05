"""
Zendesk Sync Service — pulls DACA-related tickets from Zendesk into the platform.

Two pull rules (per Shani's requirements):
  1. Any ticket where daca@rho.co is the requester, in CCs, or in collaborators
  2. Any ticket whose subject or description mentions "DACA"

For NEW tickets we send a Slack notification to #daca-ops.
For EXISTING tickets, if a new comment was added since last sync, we also notify.
"""
import logging
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.config import settings
from app.db.session import AsyncSessionLocal
from app.integrations import zendesk as zendesk_api
from app.integrations import slack as slack_api
from app.models.daca_request import DacaRequest
from app.models.zendesk_ticket import ZendeskTicket, MatchReason

logger = logging.getLogger(__name__)

DACA_REF_PATTERN = re.compile(r"DACA-\d{4}-\d{4}")
DACA_KEYWORD_PATTERN = re.compile(r"\bdaca\b", re.IGNORECASE)


def _is_zendesk_configured() -> bool:
    """Returns True if Zendesk credentials are present."""
    return bool(settings.zendesk_api_token) and bool(settings.zendesk_email)


def _parse_zendesk_dt(value: str | None) -> datetime | None:
    """Parse Zendesk ISO 8601 timestamp."""
    if not value:
        return None
    try:
        # Zendesk format: '2026-05-05T14:00:00Z'
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _build_web_url(ticket_id: int) -> str:
    """Build the human-readable Zendesk URL for a ticket."""
    base = settings.zendesk_subdomain.rstrip("/")
    return f"{base}/agent/tickets/{ticket_id}"


def _classify_match(ticket: dict[str, Any]) -> tuple[str, str | None]:
    """
    Determine why this ticket matched our DACA filters.

    Returns (match_reason, matched_daca_ref or None)
    """
    subject = ticket.get("subject") or ""
    description = ticket.get("description") or ""
    combined = f"{subject}\n{description}"

    # Strongest signal: subject contains a DACA-YYYY-NNNN ref
    ref_match = DACA_REF_PATTERN.search(combined)
    if ref_match:
        return MatchReason.DACA_REF_MATCH, ref_match.group(0)

    # Check participants for daca@rho.co
    participants: set[str] = set()
    requester = ticket.get("via", {}).get("source", {}).get("from", {}).get("address")
    if requester:
        participants.add(requester.lower())
    for cc in (ticket.get("email_cc_ids") or []) + (ticket.get("collaborator_ids") or []):
        # IDs not emails; we'd need to resolve. Skip for now.
        pass
    if "daca@rho.co" in (ticket.get("recipient") or "").lower():
        return MatchReason.DACA_EMAIL_IN_THREAD, None
    if any("daca@rho.co" in (e or "").lower() for e in participants):
        return MatchReason.DACA_EMAIL_IN_THREAD, None

    # Otherwise it must have matched the DACA keyword search
    if DACA_KEYWORD_PATTERN.search(combined):
        return MatchReason.DACA_KEYWORD, None

    return MatchReason.DACA_KEYWORD, None  # default fallback


async def _resolve_user_email(user_id: int | None) -> tuple[str | None, str | None]:
    """Best-effort resolution of a Zendesk user_id to (email, name)."""
    if not user_id:
        return None, None
    try:
        user = await zendesk_api.get_user(user_id)
        if user:
            return user.get("email"), user.get("name")
    except Exception:
        logger.debug("Failed to resolve Zendesk user_id=%s", user_id, exc_info=True)
    return None, None


async def _match_to_daca_request(db, matched_ref: str | None) -> DacaRequest | None:
    """If the ticket subject contained a DACA-YYYY-NNNN ref, link to that request."""
    if not matched_ref:
        return None
    result = await db.execute(
        select(DacaRequest).where(DacaRequest.external_ref == matched_ref)
    )
    return result.scalars().first()


async def _send_slack_alert(
    ticket: ZendeskTicket,
    is_new: bool,
    new_comments: int = 0,
) -> bool:
    """Send a Slack alert to #daca-ops about this ticket. Returns True on success."""
    if not settings.slack_bot_token or settings.slack_bot_token == "xoxb-":
        logger.debug("Slack token not configured; skipping ticket alert")
        return False

    channel = settings.slack_daca_ops_channel_id
    if not channel:
        return False

    if is_new:
        header = ":zendesk: New DACA mention in Zendesk"
    else:
        header = f":zendesk: {new_comments} new comment(s) on Zendesk ticket"

    fields: list[dict[str, Any]] = [
        {"type": "mrkdwn", "text": f"*Ticket:*\n#{ticket.zendesk_ticket_id}"},
        {"type": "mrkdwn", "text": f"*Status:*\n{ticket.status or 'unknown'}"},
    ]
    if ticket.requester_email:
        fields.append({"type": "mrkdwn", "text": f"*Requester:*\n{ticket.requester_email}"})
    if ticket.matched_daca_ref:
        fields.append({"type": "mrkdwn", "text": f"*Linked DACA:*\n{ticket.matched_daca_ref}"})
    fields.append({"type": "mrkdwn", "text": f"*Match reason:*\n{ticket.match_reason}"})

    blocks: list[dict[str, Any]] = [
        {"type": "header", "text": {"type": "plain_text", "text": header}},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{ticket.subject or '(no subject)'}*"},
        },
        {"type": "section", "fields": fields},
    ]

    if ticket.description:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"_{(ticket.description or '')[:300]}_",
            },
        })

    if ticket.web_url:
        blocks.append({
            "type": "actions",
            "elements": [{
                "type": "button",
                "text": {"type": "plain_text", "text": "Open in Zendesk"},
                "url": ticket.web_url,
            }],
        })

    try:
        await slack_api.send_blocks(channel_id=channel, blocks=blocks, text=header)
        return True
    except Exception:
        logger.warning("Failed to send Slack alert for Zendesk ticket #%s",
                       ticket.zendesk_ticket_id, exc_info=True)
        return False


async def _upsert_ticket(db, raw: dict[str, Any]) -> tuple[ZendeskTicket, bool, int]:
    """
    Insert or update a Zendesk ticket record.

    Returns (ticket, is_new, new_comment_count_since_last_sync)
    """
    zendesk_id = raw.get("id")
    if zendesk_id is None:
        raise ValueError("Zendesk ticket missing 'id'")

    # Check if we already have it
    existing_q = await db.execute(
        select(ZendeskTicket).where(ZendeskTicket.zendesk_ticket_id == zendesk_id)
    )
    existing = existing_q.scalars().first()

    match_reason, matched_ref = _classify_match(raw)
    daca_request = await _match_to_daca_request(db, matched_ref)

    requester_email, requester_name = await _resolve_user_email(raw.get("requester_id"))
    assignee_email, _ = await _resolve_user_email(raw.get("assignee_id"))

    # Get current comment count
    try:
        comments = await zendesk_api.list_ticket_comments(zendesk_id)
        current_comment_count = len(comments)
    except Exception:
        current_comment_count = 0

    fields: dict[str, Any] = {
        "zendesk_ticket_id": zendesk_id,
        "subject": raw.get("subject"),
        "description": raw.get("description"),
        "status": raw.get("status"),
        "priority": raw.get("priority"),
        "ticket_type": raw.get("type"),
        "requester_email": requester_email,
        "requester_name": requester_name,
        "assignee_email": assignee_email,
        "tags": raw.get("tags"),
        "external_id": raw.get("external_id"),
        "match_reason": match_reason,
        "matched_daca_ref": matched_ref,
        "web_url": _build_web_url(zendesk_id),
        "zendesk_created_at": _parse_zendesk_dt(raw.get("created_at")),
        "zendesk_updated_at": _parse_zendesk_dt(raw.get("updated_at")),
        "last_synced_at": datetime.now(timezone.utc),
        "daca_request_id": daca_request.id if daca_request else None,
        "last_comment_count": current_comment_count,
    }

    if existing is None:
        ticket = ZendeskTicket(**fields)
        db.add(ticket)
        await db.flush()
        return ticket, True, current_comment_count

    # Update existing
    new_comments = max(0, current_comment_count - (existing.last_comment_count or 0))
    for field, value in fields.items():
        if field == "last_comment_count":
            continue
        if value is not None or field in ("daca_request_id",):
            setattr(existing, field, value)
    existing.last_comment_count = current_comment_count
    await db.flush()
    return existing, False, new_comments


async def sync_zendesk_tickets() -> dict[str, int]:
    """
    Main sync entry point. Pulls DACA-related Zendesk tickets and notifies on new
    matches or new comments.

    Returns counts: {"created": N, "updated": N, "notified": N}
    """
    if not _is_zendesk_configured():
        logger.info("Zendesk credentials not configured; skipping sync")
        return {"created": 0, "updated": 0, "notified": 0}

    # Run two searches and dedupe by ticket id
    queries = [
        # Tickets with daca@rho.co involved (requester, cc, or recipient)
        'type:ticket cc:daca@rho.co OR requester:daca@rho.co OR recipient:daca@rho.co',
        # Tickets that mention "DACA" anywhere
        'type:ticket "DACA"',
    ]

    seen_ids: set[int] = set()
    raw_tickets: list[dict[str, Any]] = []

    for q in queries:
        try:
            results = await zendesk_api.search_tickets(q)
        except Exception:
            logger.exception("Zendesk search failed for query: %s", q)
            continue
        for t in results:
            tid = t.get("id")
            if tid and tid not in seen_ids:
                seen_ids.add(tid)
                raw_tickets.append(t)

    if not raw_tickets:
        logger.info("Zendesk sync: no DACA-related tickets found")
        return {"created": 0, "updated": 0, "notified": 0}

    logger.info("Zendesk sync: %d unique DACA-related tickets to process", len(raw_tickets))

    created = 0
    updated = 0
    notified = 0

    async with AsyncSessionLocal() as db:
        try:
            for raw in raw_tickets:
                try:
                    ticket, is_new, new_comments = await _upsert_ticket(db, raw)
                    if is_new:
                        created += 1
                        sent = await _send_slack_alert(ticket, is_new=True)
                        if sent:
                            ticket.slack_notification_sent = True
                            notified += 1
                    else:
                        updated += 1
                        if new_comments > 0:
                            sent = await _send_slack_alert(
                                ticket, is_new=False, new_comments=new_comments
                            )
                            if sent:
                                notified += 1
                except Exception:
                    logger.exception(
                        "Failed to process Zendesk ticket id=%s", raw.get("id")
                    )
                    continue
            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception("Zendesk sync transaction failed")
            raise

    summary = {"created": created, "updated": updated, "notified": notified}
    logger.info("Zendesk sync complete: %s", summary)
    return summary
