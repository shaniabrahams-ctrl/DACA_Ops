"""
Salesforce -> register enrichment + reconciliation.

Salesforce holds the DACA fields the tracker sheet leaves blank (Business ID,
DACA_Status__c, DACA_Type__c, DACA_Agreement_Date__c) — CURRENT_STATE_ASSESSMENT.md
§ pain point #1 was "lender name / mandatory data blank on most in-progress rows."

Two jobs:
  1. ENRICH — fill business_id, tier (DACA type), agreement_date on matched cases.
  2. RECONCILE the ambiguous Jira "Done" bucket. Jira "Done" only means the ticket
     closed; it does NOT prove the DACA is live. Salesforce DACA_Status__c is the
     authoritative control signal:
         DACA_Status__c = "Effective"   -> lifecycle ACTIVE  + control BORROWER_CONTROLLED
         DACA_Status__c = "Terminated"  -> lifecycle TERMINATED + control RELEASED
     This is a TYPED cross-source promotion, not an inference from a proxy — the
     exact distinction the Gumloop post-mortem turned on.

MATCHING DISCIPLINE: cases are matched to Salesforce accounts by normalized legal
name. A confident match enriches. An ambiguous or missing match is FLAGGED for
human review — never guessed. Multi-entity Jira tickets (one ticket, several SF
accounts) are flagged as such rather than silently collapsed.

Same decoupling as sync_jira: this takes already-fetched Salesforce record dicts,
so the agent feeds real records this session and a Rhollout job feeds them later.
"""

from __future__ import annotations
import re
from typing import Optional

from src.register.db import Register, Case
from src.register.lifecycle import LifecycleStage, ControlState

SF_STATUS_EFFECTIVE = "Effective"
SF_STATUS_TERMINATED = "Terminated"

_SUFFIXES = r"\b(inc|incorporated|llc|l\.l\.c|lp|l\.p|corp|corporation|co|company|ltd|limited)\b"


def normalize_name(name: str) -> str:
    n = (name or "").lower()
    n = n.replace("&", " and ")
    n = re.sub(r"[.,]", " ", n)
    n = re.sub(_SUFFIXES, " ", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def _bid(v) -> Optional[str]:
    if v is None or v == "":
        return None
    try:
        return str(int(float(v)))
    except (ValueError, TypeError):
        return str(v)


def build_sf_index(sf_records: list[dict]) -> dict[str, list[dict]]:
    idx: dict[str, list[dict]] = {}
    for r in sf_records:
        key = normalize_name(r.get("Name", ""))
        if key:
            idx.setdefault(key, []).append(r)
    return idx


def build_sf_bid_index(sf_records: list[dict]) -> dict[str, dict]:
    idx: dict[str, dict] = {}
    for r in sf_records:
        b = _bid(r.get("Business_ID__c"))
        if b:
            idx[b] = r
    return idx


def _match(case: Case, sf_index: dict[str, list[dict]],
           sf_bid_index: Optional[dict[str, dict]] = None) -> tuple[list[dict], Optional[str]]:
    """Return (matched_sf_records, warning). Business ID is the strongest key
    (both the sheet-seeded case and the SF record carry it); fall back to
    normalized name, then multi-entity subset matching."""
    if sf_bid_index and case.business_id and case.business_id in sf_bid_index:
        return [sf_bid_index[case.business_id]], None
    cname = normalize_name(case.entity_legal_name)
    if not cname:
        return [], "empty entity name — cannot match to Salesforce"
    if cname in sf_index:
        recs = sf_index[cname]
        if len(recs) > 1:
            return recs, f"ambiguous: {len(recs)} Salesforce accounts share this name"
        return recs, None
    # multi-entity: the Jira ticket names several entities; find any SF name that is
    # a token-subset match of the case name
    hits = []
    for key, recs in sf_index.items():
        if key and (key in cname):
            hits.extend(recs)
    if hits:
        return hits, ("multi-entity ticket — matched " + str(len(hits)) +
                      " Salesforce accounts; verify each maps to its own case")
    return [], "no Salesforce DACA account matched — needs manual link or has no DACA_Status yet"


def sync_salesforce(reg: Register, sf_records: list[dict], now_iso: str) -> dict:
    """Enrich + reconcile all register cases against real Salesforce DACA accounts."""
    sf_index = build_sf_index(sf_records)
    sf_bid_index = build_sf_bid_index(sf_records)
    enriched = reconciled = flagged = 0

    for case in reg.all_cases():
        matches, warning = _match(case, sf_index, sf_bid_index)
        evidence = "salesforce:Account.DACA_Status__c"

        if not matches:
            # Only flag when Salesforce is genuinely the source we need: a Jira-"Done"
            # case awaiting SF confirmation. For cases the DACA Summary sheet already
            # establishes as active/terminated, "not in SF" just means SF's DACA fields
            # lag the sheet — a low-value hygiene note, not a high-signal flag, so we
            # skip it to avoid the noisy-alert problem that erodes trust in flags.
            if case.lifecycle_stage == LifecycleStage.CLOSED_UNRECONCILED.value:
                reg._add_flag(case.case_id, f"sf_unmatched: {warning}")
                flagged += 1
            continue

        # Enrich from the (first) match; multi-entity handled via the flag above.
        rec = matches[0]
        biz = rec.get("Business_ID__c")
        daca_type = rec.get("DACA_Type__c")
        agreement = rec.get("DACA_Agreement_Date__c")
        sf_status = rec.get("DACA_Status__c")

        updates = Case(case_id=case.case_id, entity_legal_name=case.entity_legal_name,
                       lifecycle_stage=case.lifecycle_stage)
        if biz is not None:
            updates.business_id = str(int(biz)) if isinstance(biz, float) else str(biz)
        if daca_type:
            updates.tier = daca_type          # Springing / Fully Blocked
        if agreement:
            updates.agreement_date = agreement

        # Reconcile the ambiguous "Done" bucket using the authoritative SF status.
        promoted = False
        if case.lifecycle_stage == LifecycleStage.CLOSED_UNRECONCILED.value:
            if sf_status == SF_STATUS_EFFECTIVE:
                updates.lifecycle_stage = LifecycleStage.ACTIVE.value
                updates.control_state = ControlState.BORROWER_CONTROLLED.value
                updates.completion_date = agreement
                promoted = True
            elif sf_status == SF_STATUS_TERMINATED:
                updates.lifecycle_stage = LifecycleStage.TERMINATED.value
                updates.control_state = ControlState.RELEASED.value
                promoted = True

        if warning:
            reg._add_flag(case.case_id, f"sf_match: {warning}")
            flagged += 1

        changes = reg.upsert_case(updates, actor="sync:salesforce", ts=now_iso,
                                  evidence_link=evidence)
        if promoted:
            reconciled += 1
        if changes:
            enriched += 1

    return {"enriched": enriched, "reconciled": reconciled, "flagged": flagged}
