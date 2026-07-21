"""
DACA case lifecycle model — the two status dimensions the tracker sheet conflates.

REDESIGN_PROPOSALS.md §1.3 identified the single worst data-model defect in the
current DACA Summary sheet: one "Status" column encoding two orthogonal things —
*where a case is in the pipeline* and *who controls the funds*. A triggered-but-
live DACA and a mid-pipeline application become indistinguishable in any query.

This module splits them into two enums, and — critically — maps the REAL Jira
statuses observed on live CSHELP "DACA Request" tickets to lifecycle_stage.
The mapping table below is grounded in an actual JQL pull (2026-07-20), not
assumed vocabulary:

    Fraud Initial Review        Templates/Agreement Sent
    Legal Redline Review        Pre-Webster Package Review
    Docusign Sent               Done            Rejected

DISCIPLINE (the Gumloop lesson, GUMLOOP_AGENT_REVIEW.md failure #1):
  lifecycle_stage comes from a TYPED source (the Jira status field). It is never
  inferred from email dates or proxies. control_state is NOT inferred from Jira
  at all — Jira has no notion of fund control — so a case's control_state stays
  UNKNOWN until a real trigger/termination document establishes it. We show
  "unknown", we do not guess "borrower-controlled".
"""

from __future__ import annotations
from enum import Enum


class LifecycleStage(str, Enum):
    """Where a case is in the pipeline. Forward-mostly, mirroring the Jira flow."""
    INQUIRY = "inquiry"
    APPLICATION_RECEIVED = "application_received"
    FRAUD_REVIEW = "fraud_review"
    TEMPLATES_SENT = "templates_sent"
    REDLINE_REVIEW = "redline_review"
    COMPLIANCE_REVIEW = "compliance_review"     # incl. Pre-Webster package review / affirmation
    DOCUSIGN = "docusign"
    FINAL_SETUP = "final_setup"
    ACTIVE = "active"
    TERMINATED = "terminated"
    # Off-pipeline flags (not stages you pass through)
    ON_HOLD = "on_hold"
    REJECTED = "rejected"
    CANCELED = "canceled"                        # client stalled / withdrew (distinct from rejected)
    CLOSED_UNRECONCILED = "closed_unreconciled"  # Jira "Done" with no executed-doc confirmation yet


class ControlState(str, Enum):
    """Who controls the funds. Orthogonal to lifecycle_stage."""
    UNKNOWN = "unknown"                  # default until a real signal establishes it
    BORROWER_CONTROLLED = "borrower_controlled"
    LENDER_CONTROLLED = "lender_controlled"   # trigger event fired
    RELEASED = "released"                # terminated / security interest released


# Real Jira status -> lifecycle_stage. Keys are the exact status .name strings
# returned by the live CSHELP "DACA Request" board on 2026-07-20.
# Anything not in this map is surfaced as an explicit UNMAPPED flag rather than
# being silently bucketed (config-drift lesson, GUMLOOP_AGENT_REVIEW.md #10).
JIRA_STATUS_TO_STAGE: dict[str, LifecycleStage] = {
    "Fraud Initial Review": LifecycleStage.FRAUD_REVIEW,
    "Templates/Agreement Sent": LifecycleStage.TEMPLATES_SENT,
    "Legal Redline Review": LifecycleStage.REDLINE_REVIEW,
    "Pre-Webster Package Review": LifecycleStage.COMPLIANCE_REVIEW,
    "Docusign Sent": LifecycleStage.DOCUSIGN,
    "Rejected": LifecycleStage.REJECTED,
    # NOTE: "Done" deliberately maps to CLOSED_UNRECONCILED, not ACTIVE.
    # Jira "Done" only means the ticket is closed — it does NOT prove the DACA
    # executed and the account is live. Promotion to ACTIVE requires a real
    # signal (executed agreement in Drive, or a DocuSign "completed" event).
    # Inferring ACTIVE from "Done" is exactly the proxy-inference failure the
    # Gumloop agents were rule-fenced against.
    "Done": LifecycleStage.CLOSED_UNRECONCILED,
}


def stage_for_jira_status(status_name: str) -> tuple[LifecycleStage | None, str | None]:
    """
    Returns (stage, warning). If the Jira status is unmapped, stage is None and
    warning explains it — the case still lands in the register, flagged, rather
    than being dropped or guessed.
    """
    stage = JIRA_STATUS_TO_STAGE.get(status_name)
    if stage is None:
        return None, f"Unmapped Jira status {status_name!r} — needs a mapping decision, not a guess."
    return stage, None


# Allowed forward transitions (out-of-order transitions are a real error class the
# Gumloop agent could not prevent — GUMLOOP_AGENT_REVIEW.md #6). This makes an
# illegal transition detectable at write time. On_hold/rejected/terminated are
# reachable from most stages, so they're handled separately in is_allowed().
_FORWARD: dict[LifecycleStage, set[LifecycleStage]] = {
    LifecycleStage.INQUIRY: {LifecycleStage.APPLICATION_RECEIVED, LifecycleStage.FRAUD_REVIEW},
    LifecycleStage.APPLICATION_RECEIVED: {LifecycleStage.FRAUD_REVIEW},
    LifecycleStage.FRAUD_REVIEW: {LifecycleStage.TEMPLATES_SENT},
    LifecycleStage.TEMPLATES_SENT: {LifecycleStage.REDLINE_REVIEW, LifecycleStage.COMPLIANCE_REVIEW},
    LifecycleStage.REDLINE_REVIEW: {LifecycleStage.COMPLIANCE_REVIEW, LifecycleStage.TEMPLATES_SENT},
    LifecycleStage.COMPLIANCE_REVIEW: {LifecycleStage.DOCUSIGN},
    LifecycleStage.DOCUSIGN: {LifecycleStage.FINAL_SETUP, LifecycleStage.ACTIVE},
    LifecycleStage.FINAL_SETUP: {LifecycleStage.ACTIVE},
    LifecycleStage.ACTIVE: {LifecycleStage.TERMINATED},
    LifecycleStage.CLOSED_UNRECONCILED: {LifecycleStage.ACTIVE, LifecycleStage.TERMINATED},
}

_ALWAYS_REACHABLE = {LifecycleStage.ON_HOLD, LifecycleStage.REJECTED,
                     LifecycleStage.TERMINATED, LifecycleStage.CLOSED_UNRECONCILED}


def is_allowed_transition(old: LifecycleStage, new: LifecycleStage) -> bool:
    if old == new:
        return True
    if new in _ALWAYS_REACHABLE:
        return True
    if old == LifecycleStage.ON_HOLD:  # can resume to anything forward
        return True
    return new in _FORWARD.get(old, set())
