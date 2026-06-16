"""
Cross-source discrepancy detection.

Runs after all sources are loaded. Compares facts across Gmail threads,
Jira, Typeform, and Drive to find inconsistencies that would block
a DocuSign send or require human review.

Each check is a pure function: (CaseRecord) -> list[DiscrepancyFlag].
The harness runs all checks and aggregates results.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.context.record import CaseRecord

from src.context.record import DiscrepancyFlag, DiscrepancyKind, Severity, Source, SourceType


def check_document_versions(record: "CaseRecord") -> list[DiscrepancyFlag]:
    """
    Detect cases where a superseded document version was sent to the client.

    This is the exact failure mode in the Anonos case:
    - WB uploaded v2 (counter-redline) to ShareFile on 6/10
    - ShareFile logs showed Sam downloaded v1 (original) instead
    - Shani forwarded v1 to the client
    - Client negotiated Section 6(b) against a superseded draft for 4 days

    Detection logic:
    - Find all documents where sent_to_client=True
    - For each, check if a newer WB-approved version exists in the record
    - If so, flag as BLOCKER
    """
    flags = []
    sent_docs = [d for d in record.documents if d.sent_to_client]
    wb_approved = {d.name: d for d in record.documents if d.is_wb_approved}

    for sent in sent_docs:
        approved = wb_approved.get(sent.name)
        if approved and not sent.is_wb_approved:
            flags.append(DiscrepancyFlag(
                kind=DiscrepancyKind.WRONG_DOCUMENT_VERSION,
                severity=Severity.BLOCKER,
                description=(
                    f"'{sent.name}' sent to client on {sent.sent_at} "
                    f"was an interim draft (version: {sent.version_label}). "
                    f"WB-approved version '{approved.version_label}' exists "
                    f"but was not the version forwarded. "
                    "Client may have negotiated against a superseded draft."
                ),
                evidence=sent.sources + approved.sources,
            ))
    return flags


def check_wb_approval_for_entities(record: "CaseRecord") -> list[DiscrepancyFlag]:
    """
    Every entity in the case must have a WB-approved DACA template.
    Flag any entity that does not have explicit WB sign-off.

    The Anonos case introduced Sonona LLC on 6/15 — a third entity
    not in the original LEGALHELP-383 scope. WB had only approved
    the redline for Anonos Innovations + Anonos Technologies.
    Sonona required a separate WB confirmation before DocuSign send.
    """
    flags = []
    approved_doc_names = {d.name for d in record.documents if d.is_wb_approved}

    for entity in record.entities:
        entity_in_approved = any(entity.legal_name in name for name in approved_doc_names)
        if not entity_in_approved:
            flags.append(DiscrepancyFlag(
                kind=DiscrepancyKind.MISSING_WB_APPROVAL,
                severity=Severity.BLOCKER,
                description=(
                    f"No WB-approved DACA document found for entity '{entity.legal_name}'. "
                    "WB approval required before DocuSign can be sent."
                ),
                evidence=entity.sources,
            ))
    return flags


def check_signatory_completeness(record: "CaseRecord") -> list[DiscrepancyFlag]:
    """
    Every DocuSign envelope requires: legal name, address, signer name,
    signer email, and signer title. Flag any entity where title is missing.

    The Anonos case: Joseph Sciascia's title was not on any Typeform
    or email — had to be explicitly surfaced as a blocker.
    """
    flags = []
    signers = {
        c for c in record.contacts
        if c.role in ("debtor_signer", "lender_signer")
    }
    for signer in signers:
        if not signer.title:
            flags.append(DiscrepancyFlag(
                kind=DiscrepancyKind.CONTACT_UNCONFIRMED,
                severity=Severity.BLOCKER,
                description=(
                    f"Signer '{signer.name}' ({signer.email}) has no confirmed title. "
                    "Title is required for DocuSign envelope. "
                    "Must be confirmed directly with the client before send."
                ),
                evidence=signer.sources,
            ))
    return flags


def check_lender_confirmed(record: "CaseRecord") -> list[DiscrepancyFlag]:
    """
    Lender details (name, address, signer) must be confirmed in email,
    not assumed from the Typeform alone. Lender info on Typeform is
    self-reported by the debtor and may be incomplete.
    """
    flags = []
    if not record.lender:
        flags.append(DiscrepancyFlag(
            kind=DiscrepancyKind.LENDER_UNCONFIRMED,
            severity=Severity.BLOCKER,
            description="No lender record found in case context. Lender details required before DocuSign.",
            evidence=[],
        ))
    elif not record.lender.contacts:
        flags.append(DiscrepancyFlag(
            kind=DiscrepancyKind.LENDER_UNCONFIRMED,
            severity=Severity.WARNING,
            description=(
                f"Lender '{record.lender.legal_name}' found but no confirmed lender signer. "
                "Verify lender representative details before DocuSign send."
            ),
            evidence=record.lender.sources,
        ))
    return flags


ALL_CHECKS = [
    check_document_versions,
    check_wb_approval_for_entities,
    check_signatory_completeness,
    check_lender_confirmed,
]


def run_all_checks(record: "CaseRecord") -> list[DiscrepancyFlag]:
    flags = []
    for check in ALL_CHECKS:
        flags.extend(check(record))
    return flags
