"""
"Rho DACA Summary" Google Sheet -> register. THE historical backbone.

The DACA Summary sheet is the operational tracker of record — the fullest source
of the DACA book (48 rows back to 2023), keyed by Business ID, and the ONLY source
that carries lender name/contact/email, account last-4, and the human notes/legal-
ticket references. Salesforce has authoritative status but no lender; Jira has live
pipeline stage but only recent cases. So the merge uses the sheet as the spine,
keyed on Business ID, and overlays Salesforce (status) and Jira (pipeline stage).

This module parses the sheet's PRIMARY table only (the numbered Business-ID rows),
not the several legacy sub-tables below it. It:
  - keys each case by Business ID (dedupes rows that repeat a BID — real: e.g. a
    stalled "Canceled" row later superseded by an "Active" one)
  - records the lender as a party, the account last-4 in accounts (never full #)
  - captures the note verbatim and extracts referenced Jira/LEGALHELP tickets
  - maps the sheet Status to lifecycle + control_state
  - flags cross-source conflicts for human review rather than resolving silently

Decoupled from fetching (same pattern as the other syncs): the caller passes the
sheet's text content; the agent reads it live this session, a Rhollout job reads it
via the Sheets API later.
"""

from __future__ import annotations
import re
from typing import Optional

from src.register.db import Register, Case
from src.register.lifecycle import LifecycleStage, ControlState

SHEET_ID = "140z-O_ZoRyY97w4W5hBYBsUylQPJysj8rVXbzRJzRls"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit"
JIRA_BROWSE = "https://rho.atlassian.net/browse/"

_MONTHS = {m: i for i, m in enumerate(
    ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"], 1)}

# sheet Status -> (lifecycle_stage, control_state). Conservative: where the sheet
# status doesn't establish fund control, control stays UNKNOWN.
_STATUS_MAP = {
    "active":     (LifecycleStage.ACTIVE, ControlState.BORROWER_CONTROLLED),
    "live":       (LifecycleStage.ACTIVE, ControlState.BORROWER_CONTROLLED),
    "blocked":    (LifecycleStage.ACTIVE, ControlState.LENDER_CONTROLLED),   # fully-blocked type
    "terminated": (LifecycleStage.TERMINATED, ControlState.RELEASED),
    "canceled":   (LifecycleStage.CANCELED, ControlState.UNKNOWN),
    "cancelled":  (LifecycleStage.CANCELED, ControlState.UNKNOWN),
    "in progress": (None, ControlState.UNKNOWN),   # defer stage to Jira overlay
}
# rank for dedup when one Business ID has several rows (higher = more authoritative)
_STATUS_RANK = {"active": 5, "live": 5, "blocked": 4, "in progress": 3,
                "terminated": 2, "canceled": 1, "cancelled": 1, "": 0}


def parse_date(s: str) -> Optional[str]:
    """'Aug/29/2023' -> '2023-08-29'. Returns None if unparseable."""
    s = (s or "").strip()
    m = re.match(r"([A-Za-z]{3})[a-z]*/(\d{1,2})/(\d{4})", s)
    if not m:
        return None
    mon = _MONTHS.get(m.group(1).lower())
    if not mon:
        return None
    return f"{int(m.group(3)):04d}-{mon:02d}-{int(m.group(2)):02d}"


def parse_daca_summary(content: str) -> list[dict]:
    """
    Parse the primary Business-ID table from the sheet's markdown-table text.
    A primary row: >=15 pipe-cells, cell[1] is the row number, cell[2] is a
    numeric Business ID. This deliberately excludes the legacy sub-tables
    (user-access lists, the Webster 5-column list) which don't match that shape.
    """
    COLS = {"num":1, "bid":2, "name":3, "status":4, "lender":5, "lender_contact":6,
            "lender_email":7, "account":8, "inquiry":9, "agreement":10,
            "completion":11, "note":12, "termination":13, "jira":14}
    rows = []
    for line in content.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 15:
            continue
        if not (cells[COLS["num"]].isdigit() and cells[COLS["bid"]].isdigit()):
            continue
        rows.append({k: cells[i] for k, i in COLS.items()})
    return rows


def _extract_tickets(*texts: str) -> tuple[Optional[str], Optional[str]]:
    """Return (cshelp_or_ops_key, legalhelp_key) found in the given text cells."""
    blob = " ".join(t or "" for t in texts)
    legal = re.search(r"LEGALHELP-\d+", blob, re.IGNORECASE)
    other = re.search(r"(CSHELP|COMPLHELP|COMPOPS|FOPS)-\d+", blob, re.IGNORECASE)
    return (other.group(0).upper() if other else None,
            legal.group(0).upper() if legal else None)


def _dedupe_by_bid(rows: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(r["bid"], []).append(r)
    return groups


def sync_gsheet(reg: Register, content: str, now_iso: str) -> dict:
    rows = parse_daca_summary(content)
    groups = _dedupe_by_bid(rows)
    created = updated = flagged = 0

    for bid, grp in groups.items():
        # pick the most authoritative row; merge non-empty fields from the rest
        grp_sorted = sorted(grp, key=lambda r: _STATUS_RANK.get(r["status"].strip().lower(), 0),
                            reverse=True)
        primary = dict(grp_sorted[0])
        for other in grp_sorted[1:]:
            for k, v in other.items():
                if not primary.get(k) and v:
                    primary[k] = v

        status_raw = primary["status"].strip().lower()
        stage, control = _STATUS_MAP.get(status_raw, (None, ControlState.UNKNOWN))
        flags: list[str] = []
        if stage is None and status_raw not in ("in progress",):
            flags.append(f"sheet_status_unmapped: {primary['status']!r}")
        if len(grp) > 1:
            flags.append(f"multiple_sheet_rows: {len(grp)} rows share Business ID {bid} "
                         f"(statuses: {[r['status'].strip() for r in grp]}) — merged, verify")

        other_key, legal_key = _extract_tickets(primary.get("jira"), primary.get("note"))
        case_id = str(bid)
        case = Case(
            case_id=case_id,
            business_id=str(bid),
            entity_legal_name=primary["name"],
            lifecycle_stage=(stage or LifecycleStage.APPLICATION_RECEIVED).value,
            control_state=control.value,
            lender_name=primary.get("lender") or None,
            jira_key=other_key,
            legal_jira_key=legal_key,
            agreement_date=parse_date(primary.get("agreement")),
            completion_date=parse_date(primary.get("completion")),
            termination_date=parse_date(primary.get("termination")),
            initial_inquiry_date=parse_date(primary.get("inquiry")),
            stage_entered_at=(parse_date(primary.get("completion"))
                              or parse_date(primary.get("agreement"))
                              or parse_date(primary.get("inquiry")) or now_iso[:10]),
            last_synced_at=now_iso,
            flags=flags,
        )
        existed = reg.get_case(case_id) is not None
        reg.upsert_case(case, actor="sync:gsheet", ts=now_iso, evidence_link=SHEET_URL)
        created += 0 if existed else 1
        updated += 1 if existed else 0
        if flags:
            flagged += 1

        # lender as a party (the sheet is the only source with lender contacts)
        if primary.get("lender") or primary.get("lender_email"):
            reg.upsert_party(case_id, role="lender",
                             legal_name=primary.get("lender") or None,
                             person=primary.get("lender_contact") or None,
                             email=(primary.get("lender_email") or "").split(",")[0].strip() or None,
                             verified_against="gsheet:daca_summary")
        # account last-4 (already masked in the sheet)
        acct = primary.get("account", "")
        if acct:
            for last4 in re.findall(r"\d{3,4}", acct):
                try:
                    reg.conn.execute(
                        "INSERT OR IGNORE INTO accounts (case_id, account_ref, schedule_a) "
                        "VALUES (?,?,1)", (case_id, last4))
                except Exception:
                    pass
            reg.conn.commit()
        # note verbatim to the timeline
        if primary.get("note"):
            reg.append_event(case_id, now_iso, "sync:gsheet", "note",
                             new_value=primary["note"], evidence_link=SHEET_URL,
                             idempotency_key=f"gsheetnote:{case_id}:{primary['note'][:40]}")

    return {"rows": len(rows), "cases": len(groups),
            "created": created, "updated": updated, "flagged": flagged}
