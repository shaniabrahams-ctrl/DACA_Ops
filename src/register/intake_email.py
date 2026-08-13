"""
Email intake — turn a net-new DACA inquiry that arrives at daca@rho.co into a case.

The register syncs the sheet / Salesforce / Jira, but a brand-new request often
arrives ONLY as an email (Client Service loops the DACA team into a client thread,
CC'ing daca@rho.co — a Google Group with the internal DACA stakeholders) before any
Jira ticket or tracker row exists. Without this, such a request is invisible to the
tool — no card, no Slack ping. This module makes an inbound DACA inquiry a first-class
net-new case so it surfaces immediately and can be triaged.

TWO SIGNAL STRENGTHS (no-infer discipline, daca-data-security):
  - CLEAN: the subject/body clearly reads as a DACA request AND the entity was
    explicitly stated (not guessed from an email domain) AND nothing suggests this
    is a continuation of an existing open case. Auto-open the case — Ping A fires
    informational, no button.
  - AMBIGUOUS: any of the above doesn't hold (no "DACA" wording, entity only
    inferable from the domain, or it looks like it may reference an existing case).
    NO case is opened. The signal is recorded (idempotently) for a human Yes/No —
    "is this new, or does it belong with an existing case?" — never silently
    decided either way.

GROUPING: one DACA case can span multiple Zendesk tickets (a follow-up ticket
cross-links the original, e.g. Harmonate #264554 -> #265034). The classifier's
same-domain-as-an-open-case check is the signal that routes a likely-continuation
thread to a human confirm instead of silently creating a second case for the same
entity.

DISCIPLINE (no-infer, daca-data-security):
  - The borrower's legal entity, lender, and account are NOT guessed from an email.
    A clean case is created at stage `inquiry` with a `new_email_intake` flag telling
    the rep exactly what to confirm before it advances. Whatever the email states
    (requester, subject) is recorded verbatim; nothing is invented.
  - No sensitive content is stored — just the requester, subject, a short snippet,
    and the Gmail/Zendesk links. The thread itself stays in Gmail (view-don't-store).

DECOUPLED (same shape as the other syncs / R12): takes already-fetched thread dicts,
so an agent feeds them this session and a Rhollout Gmail-polling job feeds the same
shape later. Idempotent: re-running does not duplicate a case, a pending signal, or
their events.

thread dict keys:
  thread_id       Gmail thread id (-> deep link; also the pending_signals key)
  requester_email required — the client contact who wrote in
  requester_name  optional
  entity_name     optional — client/org name as stated (e.g. email signature); if
                  absent, the entity is only inferable from the domain, which is
                  itself an ambiguity trigger (never silently assumed).
  subject, snippet, received_date (YYYY-MM-DD), zendesk_url (optional)
"""

from __future__ import annotations
import re

from src.register.db import Register, Case
from src.register.lifecycle import LifecycleStage, ControlState

GMAIL_THREAD_URL = "https://mail.google.com/mail/u/0/#all/"

DACA_KEYWORDS = ("daca", "deposit account control", "control agreement")
TICKET_REF_RE = re.compile(r"#(\d{4,7})\b")


def _slug(text: str) -> str:
    return "".join(ch for ch in (text or "").upper() if ch.isalnum())[:24]


def case_id_for(thread: dict) -> str:
    base = thread.get("entity_name") or (thread.get("requester_email", "").split("@")[-1].split(".")[0])
    return "EMAIL-" + (_slug(base) or "UNKNOWN")


def _has_daca_keyword(*texts: str) -> bool:
    blob = " ".join((t or "") for t in texts).lower()
    return any(k in blob for k in DACA_KEYWORDS)


def _referenced_ticket_ids(*texts: str) -> set[str]:
    blob = " ".join((t or "") for t in texts)
    return set(TICKET_REF_RE.findall(blob))


def classify(reg: Register, thread: dict) -> dict:
    """Decide CLEAN vs AMBIGUOUS for an inbound thread. Never mutates the register.

    Returns {"decision": "clean"|"ambiguous", "reasons": [...], "candidate_case_id":
    str, "candidate_entity": str, "linked_case_id": str|None}. `reasons` is empty iff
    decision == "clean"."""
    requester = thread.get("requester_email", "")
    subject = thread.get("subject", "")
    snippet = thread.get("snippet", "")
    entity_explicit = bool(thread.get("entity_name"))
    candidate_entity = thread.get("entity_name") or requester.split("@")[-1]
    case_id = case_id_for(thread)

    reasons: list[str] = []
    if not _has_daca_keyword(subject, snippet):
        reasons.append("subject/body doesn't clearly read as a DACA request")
    if not entity_explicit:
        reasons.append("borrower entity only inferable from the email domain — not stated")

    linked_case_id = None
    domain = requester.split("@")[-1].lower() if requester else ""
    refs = _referenced_ticket_ids(subject, snippet)
    if domain:
        for c in reg.all_cases():
            if c.case_id == case_id:
                continue
            if c.lifecycle_stage in (LifecycleStage.TERMINATED.value, LifecycleStage.CANCELED.value,
                                     LifecycleStage.REJECTED.value):
                continue  # closed matters don't block a genuinely new inquiry from the same domain
            case_domains = {p.get("email", "").split("@")[-1].lower()
                            for p in reg.parties_for(c.case_id) if p.get("email")}
            if domain in case_domains:
                linked_case_id = c.case_id
                reasons.append(f"same contact domain as existing case {c.case_id} — "
                               f"possible continuation, not necessarily net-new")
                break
    if refs and not linked_case_id:
        # An explicit ticket # is mentioned but doesn't (yet) match a known case —
        # still worth a human glance rather than a silent auto-open.
        reasons.append(f"references ticket #{'/'.join(sorted(refs))} — confirm it isn't a follow-up")

    decision = "ambiguous" if reasons else "clean"
    return {"decision": decision, "reasons": reasons, "candidate_case_id": case_id,
            "candidate_entity": candidate_entity, "linked_case_id": linked_case_id}


def _open_case(reg: Register, thread: dict, now_iso: str) -> str:
    """Create the case + borrower_contact party + intake note. Shared by the clean
    auto-path and the ambiguous-confirmed-Yes path so both produce identical cases."""
    case_id = case_id_for(thread)
    entity = thread.get("entity_name") or thread.get("requester_email", "").split("@")[-1]
    requester = thread.get("requester_email", "")
    flag = ("new_email_intake: DACA inquiry received at daca@rho.co — confirm the "
            "borrower legal entity, lender/counterparty, and account, then open the "
            "Jira ticket / send the application.")
    case = Case(
        case_id=case_id,
        entity_legal_name=entity,
        lifecycle_stage=LifecycleStage.INQUIRY.value,
        control_state=ControlState.UNKNOWN.value,
        initial_inquiry_date=thread.get("received_date") or now_iso[:10],
        stage_entered_at=thread.get("received_date") or now_iso[:10],
        last_synced_at=now_iso,
        flags=[flag],
    )
    reg.upsert_case(case, actor="intake:email", ts=now_iso,
                    evidence_link=GMAIL_THREAD_URL + thread.get("thread_id", ""))
    if requester:
        reg.upsert_party(case_id, role="borrower_contact",
                         person=thread.get("requester_name") or None,
                         email=requester, verified_against="intake:email")
    note = f"New DACA inquiry — {thread.get('subject', '(no subject)')}"
    if thread.get("snippet"):
        note += f" · {thread['snippet'][:160]}"
    reg.append_event(case_id, now_iso, "intake:email", "note", new_value=note,
                     evidence_link=(thread.get("zendesk_url")
                                    or GMAIL_THREAD_URL + thread.get("thread_id", "")),
                     idempotency_key=f"emailintake:{case_id}:{thread.get('thread_id', '')}")
    return case_id


def confirm_pending_signal(reg: Register, thread: dict, actor: str, now_iso: str) -> str:
    """Human said Yes to an ambiguous signal: open the case (same path as clean intake)
    and mark the signal resolved. Idempotent — a repeat confirm is a no-op via
    resolve_pending_signal's own guard, and _open_case/upsert_case are themselves
    idempotent on case_id."""
    case_id = _open_case(reg, thread, now_iso)
    reg.resolve_pending_signal(thread.get("thread_id", ""), "opened", actor, now_iso, case_id=case_id)
    return case_id


def dismiss_pending_signal(reg: Register, thread_id: str, actor: str, now_iso: str) -> None:
    """Human said No: not a net-new case (existing case, or not a DACA request at all).
    No case is created; the signal is marked resolved so it stops appearing."""
    reg.resolve_pending_signal(thread_id, "dismissed", actor, now_iso)


def sync_email_intake(reg: Register, threads: list[dict], now_iso: str) -> dict:
    """Create/refresh net-new cases from inbound DACA inquiry emails.
    Returns {created: [case_id,...], ambiguous: [signal dict,...], seen: n}.
    `created` and `ambiguous` list only what's NEW this run — worth notifying on;
    re-running against the same threads produces neither (idempotent)."""
    created: list[str] = []
    ambiguous: list[dict] = []
    for t in threads:
        requester = t.get("requester_email", "")
        if not requester:
            continue
        case_id = case_id_for(t)
        if reg.get_case(case_id) is not None:
            continue  # already a case; a later sync (Jira/SF) owns it now
        result = classify(reg, t)
        if result["decision"] == "clean":
            _open_case(reg, t, now_iso)
            created.append(case_id)
        else:
            newly_recorded = reg.record_pending_signal(
                t.get("thread_id", ""), now_iso, result["reasons"],
                requester_email=requester, requester_name=t.get("requester_name"),
                subject=t.get("subject"), snippet=t.get("snippet"),
                candidate_entity=result["candidate_entity"], zendesk_url=t.get("zendesk_url"))
            if newly_recorded:
                ambiguous.append({**t, **result})
    return {"created": created, "ambiguous": ambiguous, "seen": len(threads)}
