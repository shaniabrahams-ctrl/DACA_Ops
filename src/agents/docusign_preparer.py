"""
DocuSign Preparer Agent

Consumes a CaseRecord (from Case Investigator) to produce DocuSign
envelope manifests for each entity. Does NOT send anything — it produces
the manifest for human review and approval before the DACA ops team
triggers the actual DocuSign API call.

PRECONDITIONS (enforced by harness, not prompt):
  - CaseRecord must have no blockers
  - Version Gatekeeper must approve the document
  - Human must confirm the manifest before send

Prefill sources (in priority order, highest confidence first):
  1. Typeform responses (submitted by the debtor, most authoritative for debtor-side data)
  2. Email confirmation (client confirmed details in writing → overrides Typeform if different)
  3. Human-supplied (DACA ops team fills gaps at manifest review)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from src.context.record import CaseRecord, Entity, DocumentRecord, Severity
from src.agents.version_gatekeeper import GateResult, check_before_send


class PreconditionError(Exception):
    """Raised when harness preconditions are not met."""


@dataclass
class EnvelopeManifest:
    """
    Everything needed to create one DocuSign envelope.
    One envelope per debtor entity.
    """
    entity_legal_name: str
    entity_address: str
    debtor_signer_name: str
    debtor_signer_email: str
    debtor_signer_title: str          # REQUIRED — blocks send if empty
    account_ids: list[str]
    lender_legal_name: str
    lender_address: str
    lender_signer_name: str
    lender_signer_email: str
    lender_signer_title: Optional[str]
    transfer_method: str
    document: DocumentRecord
    ready_to_send: bool
    missing: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def prepare(
    record: CaseRecord,
    document: DocumentRecord,
) -> list[EnvelopeManifest]:
    """
    Produce envelope manifests for all entities in the case.

    Raises PreconditionError if:
    - The record has BLOCKER-severity discrepancy flags
    - The document fails the version gate

    Does NOT raise on missing fields — those are surfaced in manifest.missing
    and manifest.ready_to_send=False for human to fill before send.
    """
    # Precondition: no blockers
    blockers = record.blockers
    if blockers:
        raise PreconditionError(
            f"Case '{record.case_id}' has {len(blockers)} unresolved blocker(s):\n"
            + "\n".join(f"  - {b.description}" for b in blockers)
        )

    # Precondition: version gate
    gate = check_before_send(document, record)
    if not gate.approved:
        raise PreconditionError(
            f"Version gate blocked: {gate.reason}"
            + (
                f"\nUse document: '{gate.wb_approved_version.name}'"
                if gate.wb_approved_version else ""
            )
        )

    manifests = []
    for readiness in record.docusign_readiness:
        entity = readiness.entity
        p = readiness.prefilled
        missing = list(readiness.missing_fields)

        manifest = EnvelopeManifest(
            entity_legal_name=entity.legal_name,
            entity_address=p.get("address", ""),
            debtor_signer_name=p.get("signer_name", ""),
            debtor_signer_email=p.get("signer_email", ""),
            debtor_signer_title=p.get("signer_title", ""),
            account_ids=p.get("account_ids", []),
            lender_legal_name=p.get("lender_name", ""),
            lender_address=p.get("lender_address", ""),
            lender_signer_name=p.get("lender_signer_name", ""),
            lender_signer_email=p.get("lender_signer_email", ""),
            lender_signer_title=p.get("lender_signer_title"),
            transfer_method=p.get("transfer_method", ""),
            document=document,
            ready_to_send=len(missing) == 0,
            missing=missing,
        )
        manifests.append(manifest)

    return manifests


def format_for_human_review(manifests: list[EnvelopeManifest]) -> str:
    """
    Produce a human-readable manifest review table.
    This is what the DACA ops team sees before approving the DocuSign send.
    """
    lines = []
    for i, m in enumerate(manifests, 1):
        lines.append(f"\n--- Envelope {i}: {m.entity_legal_name} ---")
        lines.append(f"  Entity address:      {m.entity_address or '[MISSING]'}")
        lines.append(f"  Debtor signer:       {m.debtor_signer_name or '[MISSING]'}")
        lines.append(f"  Debtor email:        {m.debtor_signer_email or '[MISSING]'}")
        lines.append(f"  Debtor title:        {m.debtor_signer_title or '[MISSING - REQUIRED]'}")
        lines.append(f"  Account IDs:         {', '.join(m.account_ids) or '[MISSING]'}")
        lines.append(f"  Lender:              {m.lender_legal_name or '[MISSING]'}")
        lines.append(f"  Lender address:      {m.lender_address or '[MISSING]'}")
        lines.append(f"  Lender signer:       {m.lender_signer_name or '[MISSING]'}")
        lines.append(f"  Lender email:        {m.lender_signer_email or '[MISSING]'}")
        lines.append(f"  Lender title:        {m.lender_signer_title or '[MISSING]'}")
        lines.append(f"  Transfer method:     {m.transfer_method or '[MISSING]'}")
        lines.append(f"  Document:            {m.document.name} ({m.document.version_label})")
        if m.missing:
            lines.append(f"  *** MISSING FIELDS: {', '.join(m.missing)} ***")
        lines.append(f"  Ready to send:       {'YES' if m.ready_to_send else 'NO - fill missing fields above'}")
    return "\n".join(lines)
