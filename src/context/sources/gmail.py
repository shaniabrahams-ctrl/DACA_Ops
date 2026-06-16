"""
Gmail case context source.

Implements the multi-query search pattern required to reconstruct
full case history. A single query is never sufficient — cases involve
multiple parties (debtor, lender, counsel, WB, Rho ops, Rho legal)
across multiple threads. All relevant threads must be found and read.

Search strategy (derived from Anonos post-mortem):
  1. Entity name + "daca@rho.co"  → daca team threads
  2. Entity name + "DACA"          → all DACA-related mentions
  3. Contact email directly        → threads where contact emailed without daca@ in cc
  4. Jira ticket numbers           → ticket notification threads (contain internal notes)
  5. Lender name (if known)        → lender-facing threads
  6. "sharefile" + entity name     → WB ShareFile notification threads (catches version events)

Why this matters: the version mixup in the Anonos case was only visible in
the ShareFile notification thread (query 6). Without it, the discrepancy
between the document sent to the client and WB's approved version would
not surface.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class GmailMessage:
    id: str
    thread_id: str
    date: datetime
    sender: str
    to: list[str]
    cc: list[str]
    subject: str
    snippet: str
    body: Optional[str] = None       # Populated when full thread is fetched
    attachments: list[dict] = None   # [{attachmentId, filename, mimeType, size}]
                                     # Populated from FULL_CONTENT response


@dataclass
class GmailThread:
    id: str
    subject: str
    messages: list[GmailMessage]
    relevance_tags: list[str]      # e.g. ["redline", "wb_sharefile", "jira"]


def build_search_queries(
    entity_names: list[str],
    contact_emails: list[str],
    jira_keys: list[str],
    lender_name: Optional[str] = None,
) -> list[str]:
    """
    Returns the full set of Gmail search queries to run for a case.
    Results are unioned and deduplicated by thread ID.
    """
    queries = []
    for name in entity_names:
        # Core case threads
        queries.append(f'"{name}" daca@rho.co')
        queries.append(f'"{name}" DACA')
        # WB ShareFile notification threads — catches document version events
        queries.append(f'sharefile "{name}"')

    for email in contact_emails:
        queries.append(f"from:{email} DACA")
        queries.append(f"to:{email} DACA")

    for key in jira_keys:
        queries.append(f'subject:"{key}"')

    if lender_name:
        queries.append(f'"{lender_name}" DACA')

    return queries


def tag_thread(thread: GmailThread) -> list[str]:
    """
    Assign relevance tags to a thread based on participants and content.
    Tags drive downstream analysis (e.g. which threads to check for version events).
    """
    tags = []
    all_text = " ".join(
        f"{m.sender} {' '.join(m.to)} {' '.join(m.cc)} {m.subject} {m.snippet}"
        for m in thread.messages
    ).lower()

    if "sharefile" in all_text:
        tags.append("wb_sharefile")
    if "redline" in all_text or "revision" in all_text:
        tags.append("redline")
    if "legalhelp" in all_text or "cshelp" in all_text:
        tags.append("jira")
    if "docusign" in all_text or "docusign" in all_text:
        tags.append("docusign")
    if "typeform" in all_text or "application form" in all_text:
        tags.append("typeform")
    if "closing" in all_text or "timely" in all_text:
        tags.append("escalation")
    if "webster" in all_text or "wb" in all_text or "websterbank" in all_text:
        tags.append("wb")
    if any(
        word in all_text
        for word in ["wrong version", "incorrect version", "miscommunication", "downloaded the original"]
    ):
        tags.append("version_error")

    return tags


def extract_document_events(thread: GmailThread) -> list[dict]:
    """
    Scan a WB ShareFile thread for document upload/download events.
    These are the evidence records for document version integrity checks.

    Returns list of events with: actor, action (upload/download), filename, timestamp.
    The Anonos root cause was Sam downloading v1 when v2 existed — this function
    would have surfaced that as a download event on the wrong file.
    """
    events = []
    for msg in thread.messages:
        if "wb_sharefile" not in thread.relevance_tags:
            continue
        body = (msg.body or msg.snippet).lower()
        # ShareFile notification format: "Uploads" / "Downloads" sections
        if "uploads" in body or "downloads" in body:
            events.append({
                "thread_id": thread.id,
                "message_id": msg.id,
                "date": msg.date,
                "sender": msg.sender,
                "raw_snippet": msg.snippet,
            })
    return events
