"""
Email intake — turn a net-new DACA inquiry that arrives at daca@rho.co into a case.

The register syncs the sheet / Salesforce / Jira, but a brand-new request often
arrives ONLY as an email (Client Service loops the DACA team into a client thread)
before any Jira ticket or tracker row exists. Without this, such a request is
invisible to the tool — no card, no Slack ping. This module makes an inbound DACA
inquiry a first-class net-new case so it surfaces immediately and can be triaged.

DISCIPLINE (no-infer, daca-data-security):
  - The borrower's legal entity, lender, and account are NOT guessed from an email.
    The case is created at stage `inquiry` with a `new_email_intake` flag telling the
    rep exactly what to confirm before it advances. Whatever the email states
    (requester, subject) is recorded verbatim; nothing is invented.
  - No sensitive content is stored — just the requester, subject, a short snippet,
    and the Gmail/Zendesk links. The thread itself stays in Gmail (view-don't-store).

DECOUPLED (same shape as the other syncs / R12): takes already-fetched thread dicts,
so an agent feeds them this session and a Rhollout Gmail-polling job feeds the same
shape later. Idempotent: re-running does not duplicate a case or its events.

thread dict keys:
  thread_id       Gmail thread id (→ deep link)
  requester_email required — the client contact who wrote in
  requester_name  optional
  entity_name     optional — client/org name as stated (e.g. email signature); if
                  absent, falls back to the email domain. Flagged for confirmation.
  subject, snippet, received_date (YYYY-MM-DD), zendesk_url (optional)
"""

from __future__ import annotations
import re

from src.register.db import Register, Case
from src.register.lifecycle import LifecycleStage, ControlState

GMAIL_THREAD_URL = "https://mail.google.com/mail/u/0/#all/"


def _slug(text: str) -> str:
    return "".join(ch for ch in (text or "").upper() if ch.isalnum())[:24]


def case_id_for(thread: dict) -> str:
    base = thread.get("entity_name") or (thread.get("requester_email", "").split("@")[-1].split(".")[0])
    return "EMAIL-" + (_slug(base) or "UNKNOWN")


def sync_email_intake(reg: Register, threads: list[dict], now_iso: str) -> dict:
    """Create/refresh net-new cases from inbound DACA inquiry emails.
    Returns {created: [case_id,...], seen: n} — created is what's worth notifying on."""
    created = []
    for t in threads:
        requester = t.get("requester_email", "")
        if not requester:
            continue
        case_id = case_id_for(t)
        entity = t.get("entity_name") or requester.split("@")[-1]
        existed = reg.get_case(case_id) is not None
        flag = ("new_email_intake: DACA inquiry received at daca@rho.co — confirm the "
                "borrower legal entity, lender/counterparty, and account, then open the "
                "Jira ticket / send the application.")
        case = Case(
            case_id=case_id,
            entity_legal_name=entity,
            lifecycle_stage=LifecycleStage.INQUIRY.value,
            control_state=ControlState.UNKNOWN.value,
            initial_inquiry_date=t.get("received_date") or now_iso[:10],
            stage_entered_at=t.get("received_date") or now_iso[:10],
            last_synced_at=now_iso,
            flags=[flag] if not existed else [],
        )
        # Only create/label on first sight; never downgrade a case that has since
        # progressed (e.g. a Jira ticket later took over this entity).
        if not existed:
            reg.upsert_case(case, actor="intake:email", ts=now_iso,
                            evidence_link=GMAIL_THREAD_URL + t.get("thread_id", ""))
            if t.get("requester_email"):
                reg.upsert_party(case_id, role="borrower_contact",
                                 person=t.get("requester_name") or None,
                                 email=requester, verified_against="intake:email")
            note = f"New DACA inquiry — {t.get('subject','(no subject)')}"
            if t.get("snippet"):
                note += f" · {t['snippet'][:160]}"
            reg.append_event(case_id, now_iso, "intake:email", "note", new_value=note,
                             evidence_link=(t.get("zendesk_url")
                                            or GMAIL_THREAD_URL + t.get("thread_id", "")),
                             idempotency_key=f"emailintake:{case_id}:{t.get('thread_id','')}")
            created.append(case_id)
    return {"created": created, "seen": len(threads)}
