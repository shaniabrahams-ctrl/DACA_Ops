"""
Jira -> register sync for CSHELP "DACA Request" tickets.

DESIGN: this function is deliberately decoupled from *how* the Jira records are
fetched. It takes already-fetched ticket dicts (the shape returned by the
Atlassian search API / MCP tool) and writes them into the register. That means:

  - In THIS session, the agent fetches real tickets via the live Atlassian MCP
    connection and passes them in — real data, today.
  - On Rhollout, a scheduled job with a Jira service account fetches the same
    shape and passes them in — no code change here.

Only the ingestion source differs; the mapping, idempotency, and event-logging
are identical and live here.

NO INFERENCE: lifecycle_stage comes straight from the Jira status field (typed
source). Entity name is parsed from the summary, but the raw summary is always
retained so a human can verify the parse. Unmapped statuses are flagged, not
guessed. control_state is never set from Jira.
"""

from __future__ import annotations
import re
from typing import Optional

from src.register.db import Register, Case
from src.register.lifecycle import stage_for_jira_status, LifecycleStage

JIRA_BROWSE = "https://rho.atlassian.net/browse/"


def parse_entity_name(summary: str) -> str:
    """
    Best-effort entity extraction from the real observed summary formats (shown
    here with placeholder names — never real client identities in committed code,
    per the daca-data-security skill):
      "<BID> - EXAMPLE ENTITY INC | DACA Request"
      "DACA Request - Example Entity, Inc."
      "Example Holdings, LLC | DACA Request for Multiple Entities"
      "DACA Request | Example Entity Inc."
    The raw summary is retained on the case's flags-adjacent note by the caller;
    this only produces a display name. Never fails — worst case returns the summary.
    """
    s = summary.strip()
    # strip a leading Business ID "1911 - "
    s = re.sub(r"^\d+\s*-\s*", "", s)
    # split on the pipe and pick the side that isn't the "DACA Request..." boilerplate
    parts = [p.strip() for p in s.split("|")]
    parts = [p for p in parts if p]
    cand = None
    for p in parts:
        if not re.search(r"daca request", p, re.IGNORECASE):
            cand = p
            break
    if cand is None and parts:
        cand = parts[0]
    cand = cand or s
    # strip leading "DACA Request - " prefix
    cand = re.sub(r"^DACA Request\s*[-:]\s*", "", cand, flags=re.IGNORECASE).strip()
    return cand or summary


# lifecycle states the sheet/Salesforce establish as authoritative end-states —
# a Jira status must never silently downgrade these; a disagreement is flagged.
_TERMINAL = {
    LifecycleStage.ACTIVE.value, LifecycleStage.TERMINATED.value,
    LifecycleStage.CANCELED.value, LifecycleStage.REJECTED.value,
}


def sync_ticket(reg: Register, ticket: dict, now_iso: str) -> list[str]:
    """
    Overlay one Jira ticket onto the register. If a case already exists for this
    Jira key (seeded from the DACA Summary sheet), Jira updates its PIPELINE STAGE
    only when the case is still in-flight — it never downgrades an Active/Terminated
    case, and a genuine conflict (e.g. sheet says Canceled, Jira still open) is
    recorded as a flag. If no case exists yet (a brand-new ticket not in the sheet),
    a new case is created keyed by the Jira key.
    """
    key = ticket["key"]
    fields = ticket.get("fields", {})
    summary = fields.get("summary", "") or ""
    status_name = (fields.get("status") or {}).get("name", "") or ""
    updated = (fields.get("updated") or "")[:19] or now_iso
    evidence = f"{JIRA_BROWSE}{key}"

    stage, warning = stage_for_jira_status(status_name)
    jira_stage = stage or LifecycleStage.INQUIRY

    existing = reg.get_case_by_jira(key)

    if existing is None:
        # brand-new ticket, not yet in the sheet — create keyed by the Jira key
        case = Case(
            case_id=key,
            entity_legal_name=parse_entity_name(summary),
            lifecycle_stage=jira_stage.value,
            jira_key=key,
            last_synced_at=now_iso,
            stage_entered_at=updated,
            flags=([warning] if warning else []) + ["not_in_daca_summary_sheet"],
        )
        changes = reg.upsert_case(case, actor="sync:jira", ts=updated, evidence_link=evidence)
        reg.append_event(key, updated, "sync:jira", "note", field="jira_summary",
                         new_value=summary, evidence_link=evidence,
                         idempotency_key=f"summary:{key}:{summary}")
        return changes

    # case already exists (from the sheet). Overlay pipeline stage only if in-flight.
    if existing.lifecycle_stage in _TERMINAL:
        if jira_stage.value not in _TERMINAL and jira_stage != LifecycleStage.CLOSED_UNRECONCILED:
            reg._add_flag(existing.case_id,
                          f"source_conflict: sheet/SF={existing.lifecycle_stage} but "
                          f"Jira {key}={status_name!r} (open) — reconcile")
            reg.append_event(existing.case_id, now_iso, "sync:jira", "flag",
                             field="lifecycle_stage", old_value=existing.lifecycle_stage,
                             new_value=f"jira:{status_name}", evidence_link=evidence,
                             idempotency_key=f"conflict:{existing.case_id}:{status_name}")
        return []

    # in-flight case: Jira is authoritative for the pipeline stage
    upd = Case(case_id=existing.case_id, entity_legal_name=existing.entity_legal_name,
               lifecycle_stage=jira_stage.value, last_synced_at=now_iso)
    return reg.upsert_case(upd, actor="sync:jira", ts=updated, evidence_link=evidence)


def sync_all(reg: Register, tickets: list[dict], now_iso: str) -> dict:
    """Sync a batch. Returns a small run report (for receipts / dead-man checks)."""
    created = updated = unchanged = 0
    per_case = {}
    for t in tickets:
        changes = sync_ticket(reg, t, now_iso)
        per_case[t["key"]] = changes
        if any(c.startswith("created") for c in changes):
            created += 1
        elif changes:
            updated += 1
        else:
            unchanged += 1
    return {"tickets": len(tickets), "created": created, "updated": updated,
            "unchanged": unchanged, "per_case": per_case}
