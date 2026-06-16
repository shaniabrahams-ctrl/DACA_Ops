"""
Email Attachment Scanner

Scans Gmail threads for DACA document attachments and registers them
in the DocumentRegistry with provenance inferred from the email direction
(who sent it, to whom).

WHY THIS EXISTS (the ShareFile gap):

  The Document Version Agent's first detection path relies on ShareFile
  notification emails being visible in the Gmail inbox. But:
  - ShareFile notifications go to whoever uploaded/downloaded — often Sam Davidson
  - Sam may not cc daca@rho.co on his ShareFile correspondence
  - If Jenifer's "you downloaded the wrong version" email had not cc'd Shani,
    the version agent would have had no signal from the ShareFile path

  This scanner provides a second, independent detection path:
  - It reads what was ACTUALLY ATTACHED to emails in the thread
  - It compares the attachment sent to the client against the attachment
    received from the client
  - If they match, the agent flags it — regardless of whether any
    ShareFile notification was ever forwarded

  In the Anonos case, this would have caught it because:
  1. Joseph's 6/1 email had the client's redline attached (CLIENT_SUBMITTED)
  2. Shani's 6/10 resend to Joseph had an attachment (outbound from Rho)
  3. Those two attachments would fingerprint as content-equivalent
  4. Flag fires: Rho is sending the client their own document back

ATTACHMENT PROVENANCE RULES:

  Sender is external (client/lender/counsel) → CLIENT_SUBMITTED
  Sender is @websterbank.com                  → WB_APPROVED
  Sender is @rho.co, recipient is external    → RHO_OPS_OUTBOUND (check against registry)
  Sender is @rho.co, recipient is @rho.co    → RHO_LEGAL_DRAFT or RHO_OPS_WORKING
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.context.sources.document_registry import (
    DocumentProvenance, DocumentChannel, DocumentFingerprint,
)
from src.context.analysis.document_diff import fingerprint_docx_bytes


RHO_DOMAIN = "rho.co"
WB_DOMAINS = ("websterbank.com", "websterfinancial.com")
DACA_DOC_PATTERNS = (".docx", "daca", "springing", "redline", "revision")


@dataclass
class AttachmentRecord:
    """A DACA document found as an email attachment."""
    message_id: str
    thread_id: str
    attachment_id: str
    filename: str
    mime_type: str
    size_bytes: int
    date: datetime
    sender: str
    recipients: list[str]
    inferred_provenance: DocumentProvenance
    fingerprint: Optional[DocumentFingerprint]    # Set after download
    file_bytes: Optional[bytes] = None


def is_daca_document(filename: str, mime_type: str) -> bool:
    """
    Return True if this attachment is likely a DACA agreement document.
    Filters out signatures, PDFs that are just email printouts, images, etc.
    """
    filename_lower = filename.lower()
    is_docx = filename_lower.endswith(".docx") or "word" in mime_type.lower()
    has_daca_keyword = any(kw in filename_lower for kw in DACA_DOC_PATTERNS)
    return is_docx and has_daca_keyword


def infer_attachment_provenance(sender: str, recipients: list[str]) -> DocumentProvenance:
    """
    Determine provenance from email direction.
    Called before the file is downloaded — purely from headers.
    """
    sender_lower = sender.lower()

    if any(wb in sender_lower for wb in WB_DOMAINS):
        return DocumentProvenance.WB_APPROVED

    if RHO_DOMAIN in sender_lower:
        # Rho → external = outbound from Rho (will be checked against registry)
        external_recipients = [
            r for r in recipients
            if RHO_DOMAIN not in r.lower() and not any(wb in r.lower() for wb in WB_DOMAINS)
        ]
        if external_recipients:
            return DocumentProvenance.RHO_OPS_WORKING   # Will be compared on check_outbound
        return DocumentProvenance.RHO_LEGAL_DRAFT

    # External sender → must be client or lender
    return DocumentProvenance.CLIENT_SUBMITTED


def extract_attachment_records_from_thread(thread_data: dict) -> list[AttachmentRecord]:
    """
    Parse a full Gmail thread (from mcp__Gmail__get_thread FULL_CONTENT response)
    and extract metadata for all DACA document attachments.

    Returns AttachmentRecord list — fingerprint field is None until download.
    File download is separate (see download_and_fingerprint_attachments).
    """
    records = []
    for msg in thread_data.get("messages", []):
        sender = msg.get("sender", "")
        to = msg.get("toRecipients", [])
        cc = msg.get("ccRecipients", [])
        all_recipients = to + cc
        date_str = msg.get("date", "")
        message_id = msg.get("id", "")
        thread_id = thread_data.get("id", "")

        try:
            from datetime import timezone
            date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            from datetime import timezone
            date = datetime.now(timezone.utc)

        for att in msg.get("attachments", []) or []:
            filename = att.get("filename", "")
            mime_type = att.get("mimeType", "")
            attachment_id = att.get("attachmentId", "")
            size = att.get("size", 0)

            if not is_daca_document(filename, mime_type):
                continue

            provenance = infer_attachment_provenance(sender, all_recipients)
            records.append(AttachmentRecord(
                message_id=message_id,
                thread_id=thread_id,
                attachment_id=attachment_id,
                filename=filename,
                mime_type=mime_type,
                size_bytes=size,
                date=date,
                sender=sender,
                recipients=all_recipients,
                inferred_provenance=provenance,
                fingerprint=None,
            ))

    return records


async def download_and_fingerprint_attachments(
    records: list[AttachmentRecord],
    gmail_client,
) -> list[AttachmentRecord]:
    """
    Download file bytes for each AttachmentRecord and compute fingerprints.
    Returns the same list with fingerprint and file_bytes populated.

    Skips attachments that fail to download — logs but does not raise.
    """
    import asyncio

    async def fetch_one(record: AttachmentRecord) -> AttachmentRecord:
        try:
            result = await gmail_client.get_attachment(
                message_id=record.message_id,
                attachment_id=record.attachment_id,
            )
            file_bytes = result.get("data") if result else None
            if file_bytes:
                if isinstance(file_bytes, str):
                    import base64
                    file_bytes = base64.urlsafe_b64decode(file_bytes + "==")
                record.file_bytes = file_bytes
                record.fingerprint = fingerprint_docx_bytes(file_bytes)
        except Exception:
            pass
        return record

    return list(await asyncio.gather(*[fetch_one(r) for r in records]))


def cross_check_attachments(
    records: list[AttachmentRecord],
) -> list[dict]:
    """
    Compare all attachment fingerprints across the thread to find mismatches.

    Specifically detects:
    1. Rho-sent attachment ≈ client-submitted attachment
       (sending client their own document back)
    2. No WB-authored revision marks in any Rho-sent attachment
       when client submitted a document earlier in the thread
       (never incorporated WB position into the response)

    Returns list of flag dicts with 'kind', 'description', 'evidence' keys.
    """
    flags = []

    client_sent = [r for r in records if r.provenance == DocumentProvenance.CLIENT_SUBMITTED
                   and r.fingerprint]
    rho_outbound = [r for r in records if r.provenance == DocumentProvenance.RHO_OPS_WORKING
                    and r.fingerprint]
    wb_docs = [r for r in records if r.provenance == DocumentProvenance.WB_APPROVED
               and r.fingerprint]

    for outbound in rho_outbound:
        # Check 1: Does the Rho-sent doc match a client-submitted doc?
        for client_doc in client_sent:
            score = outbound.fingerprint.similarity_score(client_doc.fingerprint)
            if score >= 0.70:
                flags.append({
                    "kind": "rho_sent_client_version_back",
                    "severity": "BLOCKER",
                    "description": (
                        f"Rho's outbound attachment '{outbound.filename}' "
                        f"(sent {outbound.date.strftime('%Y-%m-%d %H:%M')} to {outbound.recipients}) "
                        f"is {score:.0%} similar to client-submitted '{client_doc.filename}' "
                        f"(received {client_doc.date.strftime('%Y-%m-%d %H:%M')} from {client_doc.sender}). "
                        "This indicates Rho sent the client their own redline back, "
                        "not a counter-redline from Rho/Webster."
                    ),
                    "evidence": {
                        "outbound_message_id": outbound.message_id,
                        "client_submitted_message_id": client_doc.message_id,
                        "similarity_score": score,
                        "outbound_revision_authors": list(outbound.fingerprint.revision_author_set),
                        "client_revision_authors": list(client_doc.fingerprint.revision_author_set),
                    },
                })

        # Check 2: Rho-sent doc has no WB authors but WB docs exist
        if wb_docs:
            wb_authors_in_outbound = _has_wb_revision_authors(outbound.fingerprint)
            if not wb_authors_in_outbound:
                flags.append({
                    "kind": "outbound_missing_wb_revisions",
                    "severity": "BLOCKER",
                    "description": (
                        f"Rho's outbound attachment '{outbound.filename}' has no Webster Bank "
                        f"revision authors. WB document(s) exist in the thread "
                        f"({[d.filename for d in wb_docs]}). "
                        "The document sent to the client does not reflect Webster's position."
                    ),
                    "evidence": {
                        "outbound_message_id": outbound.message_id,
                        "outbound_revision_authors": list(outbound.fingerprint.revision_author_set),
                        "wb_docs": [d.filename for d in wb_docs],
                    },
                })

    # Check 3: No WB docs in thread at all when client submitted a redline
    if client_sent and not wb_docs and rho_outbound:
        flags.append({
            "kind": "no_wb_doc_in_thread",
            "severity": "WARNING",
            "description": (
                "Client submitted a redlined document and Rho sent a response, "
                "but no Webster Bank document appears in this thread as an attachment. "
                "Verify that WB's position is incorporated before sending further responses."
            ),
            "evidence": {
                "client_docs": [d.filename for d in client_sent],
                "rho_outbound": [d.filename for d in rho_outbound],
            },
        })

    return flags


def _has_wb_revision_authors(fp: DocumentFingerprint) -> bool:
    WB_PATTERNS = ["websterbank", "webster bank", "jenifer troy", "jennifer troy",
                   "jtroy", "stoliveira"]
    for author in fp.revision_author_set:
        if any(p in author.lower() for p in WB_PATTERNS):
            return True
    return False
