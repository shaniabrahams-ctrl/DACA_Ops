"""
Gmail Integration — polls daca@rho.co inbox and sends emails.

Auth: OAuth 2.0 service account with domain-wide delegation.
Delegated user: daca@rho.co (GMAIL_DELEGATED_USER)
"""
import base64
import json
import logging
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

logger = logging.getLogger(__name__)


def _build_service():
    """Build and return an authorized Gmail API service object.

    With OAuth user credentials (interim setup), runs as the authenticated user
    and queries that user's inbox.

    With a service account + domain-wide delegation, impersonates
    settings.gmail_delegated_user (daca@rho.co) and queries that mailbox
    directly.
    """
    from googleapiclient.discovery import build
    from app.integrations.google_auth import get_credentials, auth_mode

    scopes = ["https://www.googleapis.com/auth/gmail.modify"]

    # Only delegate when using a service account; OAuth user runs as the user.
    delegated_user = (
        settings.gmail_delegated_user if auth_mode() == "service_account" else None
    )
    credentials = get_credentials(scopes, delegated_user=delegated_user)
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
async def poll_inbox(max_results: int = 20) -> list[dict[str, Any]]:
    """
    Polls the inbox for unread DACA-related emails.

    When running as a service account impersonating daca@rho.co, simply pulls
    unread messages — every email there is by definition addressed to daca.

    When running as a user (OAuth interim mode), filters to messages where
    daca@rho.co is in From/To/CC so we don't pull the user's personal email.
    """
    import asyncio
    from app.integrations.google_auth import auth_mode
    loop = asyncio.get_event_loop()

    daca_addr = settings.gmail_delegated_user  # daca@rho.co
    if auth_mode() == "oauth_user":
        query = (
            f"is:unread ("
            f"to:{daca_addr} OR from:{daca_addr} OR cc:{daca_addr}"
            f")"
        )
    else:
        query = "is:unread"

    def _fetch():
        service = _build_service()
        results = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )
        messages = results.get("messages", [])
        parsed = []
        for msg in messages:
            full = service.users().messages().get(userId="me", id=msg["id"]).execute()
            parsed.append(_parse_message(full))
        return parsed

    return await loop.run_in_executor(None, _fetch)


def _parse_message(msg: dict) -> dict[str, Any]:
    """Extract key fields from a Gmail message object."""
    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
    thread_id = msg.get("threadId", "")
    message_id = msg.get("id", "")

    subject = headers.get("Subject", "")
    sender = headers.get("From", "")
    to = headers.get("To", "")
    cc = headers.get("Cc", "")
    date_str = headers.get("Date", "")

    # Extract snippet
    snippet = msg.get("snippet", "")

    # Gmail web URL for this thread
    gmail_url = f"https://mail.google.com/mail/u/0/#inbox/{thread_id}"

    return {
        "message_id": message_id,
        "thread_id": thread_id,
        "subject": subject,
        "sender": sender,
        "to": to,
        "cc": cc,
        "date_str": date_str,
        "snippet": snippet,
        "gmail_url": gmail_url,
    }


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
async def send_email(
    to: list[str],
    subject: str,
    body_html: str,
    cc: list[str] | None = None,
    thread_id: str | None = None,
    in_reply_to: str | None = None,
) -> dict[str, Any]:
    """Send an email from daca@rho.co via Gmail API."""
    import asyncio
    loop = asyncio.get_event_loop()

    def _send():
        service = _build_service()

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.gmail_delegated_user
        msg["To"] = ", ".join(to)
        if cc:
            msg["Cc"] = ", ".join(cc)
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
            msg["References"] = in_reply_to

        msg.attach(MIMEText(body_html, "html"))
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

        body: dict[str, Any] = {"raw": raw}
        if thread_id:
            body["threadId"] = thread_id

        result = service.users().messages().send(userId="me", body=body).execute()
        return result

    return await loop.run_in_executor(None, _send)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
async def mark_as_read(message_id: str) -> None:
    """Mark a Gmail message as read."""
    import asyncio
    loop = asyncio.get_event_loop()

    def _mark():
        service = _build_service()
        service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": ["UNREAD"]},
        ).execute()

    await loop.run_in_executor(None, _mark)
