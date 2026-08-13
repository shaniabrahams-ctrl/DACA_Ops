"""
Typeform "DACA Application Form" submission -> Ping B (R12-adjacent, intake stage).

Typeform is the source of truth for "the client submitted the DACA Application
Form" — that submission is what the SOP calls the inquiry stage's done condition
(see PLAYBOOK[INQUIRY]["done"] in src/guide/playbook.py) and what fires:
  1. An automatic, internal stage advance: inquiry -> application_received. This is
     an internal register update, not an outward action, so it's automatic (handoff
     rule: internal updates = automatic, outward/irreversible = human-gated).
  2. A parallel, non-blocking fraud-review request posted to #csfraud.
  3. A STAGED (not created) DACA Jira ticket, surfaced via Ping B's "Confirm & create
     Jira ticket" button. The actual create is the existing idempotent
     POST /case/{id}/create-ticket path — this module only stages the draft text and
     never calls Jira itself.

DECOUPLED, same shape as the other syncs: takes an already-fetched text snapshot of
the "DACA Application Form - Typeform Responses" sheet (see tools/seed_register.py /
backfill_loan_agreements.py for how that snapshot is produced) — reuses
operations.loan_agreements.parse_responses()/match_case() rather than re-parsing.

IDEMPOTENCY: keyed on the Typeform response `token` via the event log's
idempotency_key (the same dedupe primitive every other sync uses) — re-running
against the same snapshot advances nothing twice, stages nothing twice, and the
caller (which posts Slack) is only handed the NEWLY-processed rows.

NO-INFER: an unmatched borrower name creates no case and stages no ticket — it's
reported back so a human can look at it, exactly like loan_agreements' unmatched
handling.
"""

from __future__ import annotations

from src.register.db import Register, Case
from src.register.lifecycle import LifecycleStage
from src.operations.loan_agreements import parse_responses, match_case


def _staged_summary(case: Case) -> str:
    return f"{case.business_id + ' - ' if case.business_id else ''}{case.entity_legal_name} | DACA Request"


def sync_typeform_applications(reg: Register, content: str, now_iso: str) -> dict:
    """Process the responses snapshot. Returns:
      {"submitted": [{"case_id", "entity", "lender_provided", "token", "staged_summary"}],
       "unmatched": [{"token", "borrower_name"}], "seen": n}
    `submitted` lists only tokens newly processed this run — the caller notifies on
    exactly this list (Ping B + the #csfraud post), never on already-seen tokens."""
    rows = parse_responses(content)
    submitted: list[dict] = []
    unmatched: list[dict] = []

    for row in rows:
        token = row["token"]
        case = match_case(reg, row["borrower_name"])
        if not case:
            unmatched.append({"token": token, "borrower_name": row["borrower_name"]})
            continue

        # Idempotency gate: the event log is the single dedupe primitive (db.py).
        # A False return means this token was already processed by a prior run.
        newly_seen = reg.append_event(
            case.case_id, now_iso, "sync:typeform", "application_submitted",
            new_value=token, idempotency_key=f"typeform_submitted:{case.case_id}:{token}")
        if not newly_seen:
            continue

        if case.lifecycle_stage == LifecycleStage.INQUIRY.value:
            reg.upsert_case(
                Case(case_id=case.case_id, entity_legal_name=case.entity_legal_name,
                     lifecycle_stage=LifecycleStage.APPLICATION_RECEIVED.value),
                actor="sync:typeform", ts=now_iso,
                evidence_link=f"typeform:response:{token}")
            case = reg.get_case(case.case_id)  # re-read post-advance for accurate staging text

        staged_summary = _staged_summary(case)
        reg.append_event(case.case_id, now_iso, "sync:typeform", "jira_ticket_staged",
                         new_value=staged_summary, idempotency_key=f"stage:{case.case_id}:{token}")
        reg.append_event(case.case_id, now_iso, "sync:typeform", "fraud_review_requested",
                         new_value="posted to #csfraud",
                         idempotency_key=f"csfraud:{case.case_id}:{token}")

        submitted.append({
            "case_id": case.case_id, "entity": case.entity_legal_name,
            "lender_provided": bool((row.get("lender_name") or "").strip()),
            "token": token, "staged_summary": staged_summary,
        })

    return {"submitted": submitted, "unmatched": unmatched, "seen": len(rows)}
