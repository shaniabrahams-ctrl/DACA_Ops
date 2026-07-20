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


def sync_ticket(reg: Register, ticket: dict, now_iso: str) -> list[str]:
    """
    Map one Jira ticket dict -> Case and upsert. Returns changes applied.
    `ticket` is one node from the Atlassian search response: {key, fields:{...}}.
    """
    key = ticket["key"]
    fields = ticket.get("fields", {})
    summary = fields.get("summary", "") or ""
    status_name = (fields.get("status") or {}).get("name", "") or ""
    updated = (fields.get("updated") or "")[:19] or now_iso

    stage, warning = stage_for_jira_status(status_name)
    flags: list[str] = []
    if warning:
        flags.append(warning)
        stage = stage or LifecycleStage.INQUIRY  # park it somewhere visible, flagged

    entity = parse_entity_name(summary)
    evidence = f"{JIRA_BROWSE}{key}"

    case = Case(
        case_id=key,                       # stable id = jira key for iteration 1
        entity_legal_name=entity,
        lifecycle_stage=stage.value,
        jira_key=key,
        last_synced_at=now_iso,
        stage_entered_at=updated,
        flags=flags,
    )
    # record the raw summary as a note event once (idempotent) so the parse is auditable
    reg_changes = reg.upsert_case(case, actor="sync:jira", ts=updated, evidence_link=evidence)
    reg.append_event(key, updated, "sync:jira", "note", field="jira_summary",
                     new_value=summary, evidence_link=evidence,
                     idempotency_key=f"summary:{key}:{summary}")
    return reg_changes


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
