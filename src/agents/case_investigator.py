"""
Case Investigator Agent

Implements the full-context reconstruction workflow demonstrated in the
Anonos investigation: given a case ID, systematically traverse every
available source, build the evidentiary record, and surface the complete
picture to the human operator before any action is taken.

This agent is the FIRST step in every DACA case workflow:
  1. Case Investigator loads full context → produces CaseRecord
  2. Human reviews CaseRecord summary + discrepancy flags
  3. Human clears blockers
  4. DocuSign Prep Agent uses CaseRecord to fill envelopes
  5. Version Gatekeeper checks document before send

The agent NEVER infers or assumes facts. Every field in CaseRecord
is sourced — it comes from a tool call, not model memory.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from src.context.record import CaseRecord, Severity


@dataclass
class InvestigationRequest:
    """Input to the Case Investigator."""
    primary_entity: str              # The entity name that kicked off the case
    additional_entities: list[str]   # Any additional entities disclosed later
    seed_jira_keys: list[str]        # Known Jira tickets at investigation start
    seed_contact_emails: list[str]   # Known contacts (from Typeform, prior email)
    lender_name: Optional[str]       # If already known


@dataclass
class InvestigationResult:
    record: CaseRecord
    timeline_narrative: str          # Human-readable chronological summary
    action_required: list[str]       # Ordered list of next steps for human
    docusign_manifests: list[dict]   # One per entity, ready for DocuSign prep


def build_investigation_request_from_typeform(typeform_row: dict) -> InvestigationRequest:
    """
    Convert a Typeform response row into an investigation request.
    Called when a new Typeform submission arrives (the standard intake path).
    """
    entity_name = typeform_row.get("entity_name") or typeform_row.get("company_name", "")
    additional = []
    if typeform_row.get("additional_entities"):
        additional = [e.strip() for e in typeform_row["additional_entities"].split(",")]

    return InvestigationRequest(
        primary_entity=entity_name,
        additional_entities=additional,
        seed_jira_keys=[],
        seed_contact_emails=[
            e for e in [
                typeform_row.get("signer_email"),
                typeform_row.get("contact_email"),
            ] if e
        ],
        lender_name=typeform_row.get("lender_name") or typeform_row.get("secured_party_name"),
    )


async def run(
    request: InvestigationRequest,
    loader,  # CaseContextLoader instance
) -> InvestigationResult:
    """
    Execute full case investigation and return structured result.

    The agent:
    1. Loads context from all sources (Gmail, Jira, Typeform, Drive)
    2. Runs all discrepancy checks
    3. Builds a human-readable timeline narrative
    4. Returns ordered action list and DocuSign manifests

    If blockers are found, DocuSign manifests are still built but
    marked as not-ready. The human operator must clear blockers first.
    """
    all_entities = [request.primary_entity] + request.additional_entities

    record = await loader.load(
        case_id=request.primary_entity,
        entity_names=all_entities,
        seed_contact_emails=request.seed_contact_emails,
        seed_jira_keys=request.seed_jira_keys,
        lender_name=request.lender_name,
    )

    narrative = _build_narrative(record)
    actions = _build_action_list(record)
    manifests = _build_docusign_manifests(record)

    return InvestigationResult(
        record=record,
        timeline_narrative=narrative,
        action_required=actions,
        docusign_manifests=manifests,
    )


def _build_narrative(record: CaseRecord) -> str:
    """
    Chronological plain-English summary of the case timeline.
    Every sentence cites a source (thread ID or ticket key).
    """
    if not record.timeline:
        return "No timeline events found."

    lines = [f"Timeline for {record.case_id} ({len(record.timeline)} events):\n"]
    for event in record.timeline:
        src = event.source
        lines.append(
            f"  {event.date.strftime('%Y-%m-%d %H:%M UTC')} — {event.actor}: "
            f"{event.description[:100]} [{src.source_type.value}:{src.source_id[:16]}]"
        )

    if record.discrepancy_flags:
        lines.append("\nDISCREPANCIES DETECTED:")
        for flag in record.discrepancy_flags:
            icon = "BLOCKER" if flag.severity == Severity.BLOCKER else "WARNING"
            lines.append(f"  [{icon}] {flag.description}")

    return "\n".join(lines)


def _build_action_list(record: CaseRecord) -> list[str]:
    """
    Ordered next steps for the human operator.
    Blockers come first. Each item specifies who owns it.
    """
    actions = []

    # Blockers first
    for flag in record.discrepancy_flags:
        if flag.severity == Severity.BLOCKER:
            actions.append(f"[BLOCKER] {flag.description}")

    # Open items
    for item in record.open_items:
        if item.blocking:
            prefix = "[BLOCKING]"
        else:
            prefix = "[ACTION]"
        actions.append(f"{prefix} ({item.owner}) {item.description}")

    # Warnings
    for flag in record.discrepancy_flags:
        if flag.severity == Severity.WARNING:
            actions.append(f"[WARNING] {flag.description}")

    if not actions:
        actions.append("No outstanding actions. Case is ready to proceed to DocuSign.")

    return actions


def _build_docusign_manifests(record: CaseRecord) -> list[dict]:
    """
    One manifest per entity, containing all prefilled fields and gap list.
    Passed to the DocuSign Prep Agent once blockers are cleared.
    """
    manifests = []
    for readiness in record.docusign_readiness:
        manifests.append({
            "entity": readiness.entity.legal_name,
            "ready": readiness.ready,
            "missing_fields": readiness.missing_fields,
            "prefilled": readiness.prefilled,
            "account_count": len(readiness.entity.account_ids),
        })
    return manifests
