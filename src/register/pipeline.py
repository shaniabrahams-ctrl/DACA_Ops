"""
Pipeline surface — the always-current answer to "where is every DACA right now?"

This is the single most-requested artifact in the whole assessment
(CURRENT_STATE_ASSESSMENT.md §5.1: "at any given time/date, need immediate
visibility into where a daca is in the process") and the first workflow to ship
per the rollout order.

It is a pure VIEW over the register — no data of its own, no inference. Every
number is computed from real case rows. "Days in stage" comes from the real
stage_entered_at timestamp; it is never typed by hand. Where a fact is genuinely
unknown (waiting-on, next action) it renders as an explicit gap, not a guess —
because an invented "waiting on client" is worse than an honest "— (not set)".
"""

from __future__ import annotations
from datetime import datetime, timezone

from src.register.db import Register
from src.register.lifecycle import LifecycleStage

# Display order + labels for the active pipeline (off-pipeline flags shown separately)
STAGE_ORDER = [
    (LifecycleStage.INQUIRY, "Inquiry"),
    (LifecycleStage.APPLICATION_RECEIVED, "Application Received"),
    (LifecycleStage.FRAUD_REVIEW, "Fraud Review"),
    (LifecycleStage.TEMPLATES_SENT, "Templates / Agreement Sent"),
    (LifecycleStage.REDLINE_REVIEW, "Legal Redline Review"),
    (LifecycleStage.COMPLIANCE_REVIEW, "Compliance / Pre-Webster Review"),
    (LifecycleStage.DOCUSIGN, "DocuSign Sent"),
    (LifecycleStage.FINAL_SETUP, "Final Setup"),
    (LifecycleStage.ACTIVE, "Active"),
]
OFF_PIPELINE = [
    (LifecycleStage.CLOSED_UNRECONCILED, "Closed in Jira — executed? (needs reconciliation)"),
    (LifecycleStage.ON_HOLD, "On Hold"),
    (LifecycleStage.CANCELED, "Canceled"),
    (LifecycleStage.REJECTED, "Rejected"),
    (LifecycleStage.TERMINATED, "Terminated"),
]

STALE_DAYS = 30


def _days_since(iso: str, now: datetime) -> int | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (now - dt).days
    except ValueError:
        return None


def render_board(reg: Register, now_iso: str) -> str:
    now = datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    cases = reg.all_cases()
    by_stage: dict[str, list] = {}
    for c in cases:
        by_stage.setdefault(c.lifecycle_stage, []).append(c)

    in_flight = sum(len(by_stage.get(s.value, [])) for s, _ in STAGE_ORDER
                    if s not in (LifecycleStage.ACTIVE,))
    active = len(by_stage.get(LifecycleStage.ACTIVE.value, []))

    lines = []
    lines.append(f"# DACA Pipeline — where every case is right now")
    lines.append(f"_generated {now_iso} from the case register · {len(cases)} cases · "
                 f"{in_flight} in flight · {active} active_")
    lines.append("")

    for stage, label in STAGE_ORDER:
        group = by_stage.get(stage.value, [])
        if not group:
            continue
        lines.append(f"## {label}  ({len(group)})")
        for c in sorted(group, key=lambda x: x.stage_entered_at or "", reverse=False):
            d = _days_since(c.stage_entered_at, now)
            age = f"{d}d in stage" if d is not None else "age unknown"
            stale = "  ⚠️ STALE >30d" if (d is not None and d > STALE_DAYS) else ""
            flagmark = f"  🚩{len(c.flags)}" if c.flags else ""
            nxt = c.next_action or "— next action not set"
            owner = f" [{c.next_action_owner}]" if c.next_action_owner else ""
            lines.append(f"  • **{c.entity_legal_name}** ({c.jira_key}) — {age}{stale}{flagmark}")
            lines.append(f"      waiting on{owner}: {nxt}")
        lines.append("")

    # off-pipeline buckets
    off = [(s, l) for s, l in OFF_PIPELINE if by_stage.get(s.value)]
    if off:
        lines.append("---")
        for stage, label in off:
            group = by_stage.get(stage.value, [])
            names = ", ".join(f"{c.entity_legal_name} ({c.jira_key})" for c in group)
            lines.append(f"**{label}** ({len(group)}): {names}")
        lines.append("")

    # data-quality surface — flags are shown, never swallowed
    flagged = [c for c in cases if c.flags]
    if flagged:
        lines.append("## 🚩 Needs attention (data-quality / transition flags)")
        for c in flagged:
            for f in c.flags:
                lines.append(f"  • {c.entity_legal_name} ({c.jira_key}): {f}")
        lines.append("")

    return "\n".join(lines)
