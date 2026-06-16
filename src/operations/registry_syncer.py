"""
DACA Registry Syncer

Pulls data from Jira, Google Drive (DACA Summary sheet), and Gmail threads
to populate the DACACaseRegistry with current case status and open items.

This is the bridge between the operational sources of truth and the unified registry.

Sync flow:
  1. Query Jira for all CSHELP DACA tickets
  2. Extract case ID, status, lender, contact from each ticket
  3. Pull DACA Summary sheet for current status rollup
  4. Query Gmail for each case's threads (context/blockers)
  5. Merge results into DACACaseRegistry

The registry is then queryable: "Show me all blockers" or "What's pending for Edwards?"
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

from src.operations import (
    DACACaseRegistry, DACACaseSnapshot, OpenItem, CaseStatus, ItemPriority
)


class RegistrySyncer:
    """
    Syncs data from Jira, Drive, Gmail into a unified DACACaseRegistry.
    Designed to be called periodically or on-demand.
    """

    def __init__(self):
        self.registry = DACACaseRegistry()

    async def sync_from_jira(self, jira_client) -> DACACaseRegistry:
        """
        Query all DACA tickets from Jira (CSHELP project, DACA-tagged).
        Extract: case_id, status, business_name, lender, contact, blockers.
        """
        # This would use the Atlassian Jira API
        # For now, document the interface
        jql = 'project = "CSHELP" AND labels in (DACA) AND status NOT IN (Done, Closed)'
        # results = jira_client.search_issues(jql, maxResults=100)
        # for issue in results:
        #     case = DACACaseSnapshot(
        #         case_id=issue.fields.customfield_CASE_ID or issue.key,
        #         business_name=issue.fields.summary.split("|")[0].strip(),
        #         status=self._map_jira_status(issue.fields.status),
        #         ...
        #     )
        #     self.registry.add_case(case)
        return self.registry

    async def sync_from_drive_sheet(self, drive_client, sheet_id: str) -> DACACaseRegistry:
        """
        Pull the DACA Summary sheet and reconcile case statuses.
        Sheet contains: Rho ID, Business Name, Status, DACA Completion Date, etc.
        """
        # This would use Google Sheets API
        # For now, document the interface
        # sheet = drive_client.get_sheet(sheet_id, range="Sheet1")
        # for row in sheet.values[1:]:  # Skip header
        #     rho_id, business_name, status, ... = row
        #     case = self.registry.get_case(str(rho_id))
        #     if case:
        #         case.status = self._map_sheet_status(status)
        #         case.last_updated = datetime.now(timezone.utc).isoformat()
        return self.registry

    async def sync_from_gmail(self, gmail_client, case_contexts: dict) -> DACACaseRegistry:
        """
        Query Gmail for each case's threads and extract open items/blockers.
        case_contexts: {case_id: {"entity_names": [...], "contact_email": "..."}}

        Looks for:
        - Emails marked as "awaiting response from client" → adds OpenItem
        - Threads with unresolved questions → adds OpenItem
        - Blockers mentioned in DRI notes → adds to case.blockers
        """
        # This would query Gmail and parse thread content
        # For now, document the interface
        # for case_id, context in case_contexts.items():
        #     case = self.registry.get_case(case_id)
        #     if not case:
        #         continue
        #     threads = gmail_client.search_threads(
        #         f'"{context["entity_names"][0]}" DACA after:2026-06-01'
        #     )
        #     for thread in threads:
        #         # Parse thread for blockers, open questions
        #         if "awaiting" in thread.subject.lower():
        #             case.open_items.append(OpenItem(...))
        return self.registry

    def _map_jira_status(self, jira_status: str) -> CaseStatus:
        """Map Jira status names to CaseStatus enum."""
        mapping = {
            "Fraud Initial Review": CaseStatus.FRAUD_REVIEW,
            "Typeform Sent": CaseStatus.TYPEFORM_SENT,
            "Templates/Agreements Sent": CaseStatus.TEMPLATE_SENT,
            "Legal Redline Review": CaseStatus.LEGAL_REDLINE,
            "Pending Compliance Package Assembly": CaseStatus.COMPLIANCE_PENDING,
            "Docusign Sent": CaseStatus.DOCUSIGN_SENT,
            "Pending Final Setup": CaseStatus.PENDING_SETUP,
            "Done": CaseStatus.ACTIVE,
        }
        return mapping.get(jira_status, CaseStatus.INTAKE)

    def _map_sheet_status(self, sheet_status: str) -> CaseStatus:
        """Map DACA Summary sheet status to CaseStatus enum."""
        status_lower = sheet_status.lower()
        if "fraud" in status_lower:
            return CaseStatus.FRAUD_REVIEW
        if "typeform" in status_lower:
            return CaseStatus.TYPEFORM_SENT
        if "template" in status_lower:
            return CaseStatus.TEMPLATE_SENT
        if "redline" in status_lower:
            return CaseStatus.LEGAL_REDLINE
        if "compliance" in status_lower:
            return CaseStatus.COMPLIANCE_PENDING
        if "docusign" in status_lower:
            return CaseStatus.DOCUSIGN_SENT
        if "setup" in status_lower:
            return CaseStatus.PENDING_SETUP
        if "active" in status_lower:
            return CaseStatus.ACTIVE
        return CaseStatus.INTAKE

    async def full_sync(self, jira_client, drive_client, gmail_client, sheet_id: str) -> DACACaseRegistry:
        """
        Run full sync: Jira → Drive → Gmail.
        Returns populated registry.
        """
        await self.sync_from_jira(jira_client)
        await self.sync_from_drive_sheet(drive_client, sheet_id)
        # Gmail sync requires case contexts; would be passed by caller
        self.registry.last_sync = datetime.now(timezone.utc).isoformat()
        return self.registry


def print_outstanding_items(registry: DACACaseRegistry) -> str:
    """
    Print all outstanding DACA items in a human-readable format.
    This is the answer to "what are all outstanding items?"
    """
    return registry.format_summary()
