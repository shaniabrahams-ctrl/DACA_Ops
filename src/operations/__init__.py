"""
DACA Operations Registry

The unified source of truth for all DACA cases in flight.
Syncs from Jira (case status), Drive (DACA Summary sheet), and Gmail (context)
to maintain a queryable registry of all open items, blockers, and case status.

This is what makes the tool actually operational — one place to ask:
"What are all outstanding DACA items?" and get a complete, deduplicated answer.

Syncing strategy:
  - Periodic (on-demand or scheduled) sync from Jira DACA tickets
  - Pull current DACA Summary sheet for status rollup
  - Query Gmail threads to extract open items and blockers
  - Merge results, deduplicate by case_id, sort by priority
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from enum import Enum


class CaseStatus(str, Enum):
    """DACA case lifecycle states."""
    INTAKE = "intake"
    FRAUD_REVIEW = "fraud_review"
    TYPEFORM_SENT = "typeform_sent"
    TEMPLATE_SENT = "template_sent"
    LEGAL_REDLINE = "legal_redline"
    COMPLIANCE_PENDING = "compliance_pending"
    DOCUSIGN_SENT = "docusign_sent"
    PENDING_SETUP = "pending_setup"
    ACTIVE = "active"
    CLOSED = "closed"


class ItemPriority(str, Enum):
    """Open item urgency."""
    BLOCKER = "blocker"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class OpenItem:
    """A single outstanding action item for a case."""
    case_id: str
    item_id: str
    description: str
    owner: str  # Who it's waiting on (client, Rho, lender, compliance, etc.)
    priority: ItemPriority
    due_date: Optional[str] = None
    source: str = ""  # Where this came from (Jira ticket, email, etc.)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class DACACaseSnapshot:
    """Current state of a single DACA case."""
    case_id: str
    business_name: str
    status: CaseStatus
    lender_name: str
    primary_contact: str
    contact_email: str
    jira_ticket: Optional[str]
    open_items: list[OpenItem] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: str = ""


@dataclass
class DACACaseRegistry:
    """In-memory registry of all DACA cases."""
    cases: dict[str, DACACaseSnapshot] = field(default_factory=dict)
    last_sync: Optional[str] = None

    def add_case(self, snapshot: DACACaseSnapshot) -> None:
        """Register or update a case."""
        self.cases[snapshot.case_id] = snapshot

    def get_case(self, case_id: str) -> Optional[DACACaseSnapshot]:
        """Retrieve a single case."""
        return self.cases.get(case_id)

    def get_all_cases(self) -> list[DACACaseSnapshot]:
        """Return all cases, sorted by status priority (blockers first)."""
        def priority_sort(case: DACACaseSnapshot) -> tuple[int, str]:
            # Cases with blockers come first, then by status
            has_blockers = 1 if case.blockers else 0
            return (has_blockers * -1, case.case_id)  # Negative = higher priority first
        return sorted(self.cases.values(), key=priority_sort, reverse=True)

    def get_all_open_items(self, status: Optional[CaseStatus] = None) -> list[OpenItem]:
        """Get all open items across all cases, optionally filtered by case status."""
        items = []
        for case in self.cases.values():
            if status is None or case.status == status:
                items.extend(case.open_items)
        # Sort by priority (blockers first) then by case_id
        priority_order = {ItemPriority.BLOCKER: 0, ItemPriority.HIGH: 1, ItemPriority.MEDIUM: 2, ItemPriority.LOW: 3}
        return sorted(items, key=lambda x: (priority_order.get(x.priority, 99), x.case_id))

    def get_blockers(self) -> dict[str, list[str]]:
        """Return all blockers keyed by case_id."""
        return {case.case_id: case.blockers for case in self.cases.values() if case.blockers}

    def get_cases_by_status(self, status: CaseStatus) -> list[DACACaseSnapshot]:
        """Get all cases at a specific lifecycle stage."""
        return [c for c in self.cases.values() if c.status == status]

    def format_summary(self) -> str:
        """Human-readable summary of all outstanding items."""
        lines = ["# DACA Operations Summary", f"\nGenerated: {datetime.now(timezone.utc).isoformat()}"]
        lines.append(f"Total Cases: {len(self.cases)}")

        # Group by status
        by_status = {}
        for case in self.cases.values():
            if case.status not in by_status:
                by_status[case.status] = []
            by_status[case.status].append(case)

        for status in CaseStatus:
            cases = by_status.get(status, [])
            if not cases:
                continue
            lines.append(f"\n## {status.value.upper()} ({len(cases)} cases)")
            for case in cases:
                lines.append(f"  - {case.business_name} ({case.case_id})")
                if case.blockers:
                    for blocker in case.blockers:
                        lines.append(f"    🚫 {blocker}")
                if case.open_items:
                    for item in case.open_items[:3]:  # Show first 3
                        lines.append(f"    ⏳ [{item.owner}] {item.description}")
                    if len(case.open_items) > 3:
                        lines.append(f"    ... and {len(case.open_items) - 3} more items")

        lines.append("\n## All Open Items (By Priority)")
        all_items = self.get_all_open_items()
        by_priority = {}
        for item in all_items:
            if item.priority not in by_priority:
                by_priority[item.priority] = []
            by_priority[item.priority].append(item)

        for priority in [ItemPriority.BLOCKER, ItemPriority.HIGH, ItemPriority.MEDIUM, ItemPriority.LOW]:
            items = by_priority.get(priority, [])
            if not items:
                continue
            lines.append(f"\n### {priority.value.upper()} ({len(items)} items)")
            for item in items:
                case = self.cases.get(item.case_id)
                case_name = case.business_name if case else item.case_id
                lines.append(
                    f"  - [{item.owner}] {case_name}: {item.description}"
                    + (f" (due: {item.due_date})" if item.due_date else "")
                )

        return "\n".join(lines)
