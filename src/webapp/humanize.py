"""
Turn the register's internal flag strings into plain-English, actionable items for
an Ops rep (who is a mini-PM per DACA, not an engineer). Presentation-only: the raw
flags stay in the register; this just decides how a human reads them.

Each flag → {severity, title, action, detail}:
  severity  'high' | 'med' | 'low'  (drives color + sort order; red = act now)
  title     what's wrong, in one human sentence
  action    what the rep should do about it
  detail    the specific specifics parsed from the flag (optional, small print)
"""

from __future__ import annotations

SEV_ORDER = {"high": 0, "med": 1, "low": 2}


def _tail(flag: str) -> str:
    return flag.split(":", 1)[1].strip() if ":" in flag else ""


def humanize_flag(flag: str) -> dict:
    f = flag or ""
    if f.startswith("new_email_intake"):
        return {"severity": "high",
                "title": "New DACA request received by email",
                "action": "Confirm the borrower entity + lender, then open the Jira ticket / send the application.",
                "detail": _tail(f)}
    if f.startswith("source_conflict"):
        return {"severity": "high",
                "title": "Systems disagree on this DACA's status",
                "action": "Reconcile the tracker, Salesforce, and Jira so they match.",
                "detail": _tail(f)}
    if f.startswith("multiple_sheet_rows"):
        return {"severity": "med",
                "title": "Duplicate rows in the DACA tracker for this business",
                "action": "Confirm which tracker row is the correct one.",
                "detail": _tail(f)}
    if f.startswith("illegal_transition"):
        return {"severity": "med",
                "title": "Stage moved in an unexpected order",
                "action": "Check the current stage is right (a step may have been skipped).",
                "detail": _tail(f)}
    if f.startswith("loan_agreement_unmatched"):
        return {"severity": "med",
                "title": "Loan agreement received but not linked to a case",
                "action": "Match it to the right DACA and confirm the borrower/lender.",
                "detail": _tail(f)}
    if f.startswith("not_in_daca_summary_sheet"):
        return {"severity": "low",
                "title": "New Jira ticket not yet in the DACA tracker",
                "action": "Add it to the tracker, or confirm it isn't a DACA request.",
                "detail": ""}
    if f.startswith("sf_unmatched"):
        return {"severity": "low",
                "title": "No matching Salesforce DACA account",
                "action": "Link the Salesforce account or confirm its status.",
                "detail": _tail(f)}
    if f.startswith("sf_match"):
        return {"severity": "low",
                "title": "Salesforce match needs a human check",
                "action": "Verify this maps to the right Salesforce account.",
                "detail": _tail(f)}
    if f.startswith("sheet_status_unmapped"):
        return {"severity": "med",
                "title": "Tracker status not recognized",
                "action": "Use a standard status so the stage can be set.",
                "detail": _tail(f)}
    # Unknown flag — show it plainly rather than hiding it.
    return {"severity": "low", "title": f, "action": "", "detail": ""}
