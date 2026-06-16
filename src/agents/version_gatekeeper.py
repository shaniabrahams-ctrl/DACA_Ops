"""
Version Gatekeeper

Runs before any document is sent to the client (DocuSign, email attachment,
or ShareFile). Blocks the send if the document is not WB-approved.

This is a harness-enforced gate — not a prompt rule. The Anonos version
mixup happened because there was no code-level check; Sam visually
confirmed access to ShareFile but downloaded the wrong file. A ShareFile
activity log showed the wrong download within minutes, but the signal
was never consumed by the workflow.

This gate consumes that signal:
  - Compares the document about to be sent against the known WB-approved version
  - Checks Drive for newer versions uploaded after the current one
  - Checks ShareFile notification threads for any "downloaded wrong version" flags
  - Blocks on mismatch; requires explicit human override to proceed
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from src.context.record import DocumentRecord, CaseRecord, DiscrepancyKind


@dataclass
class GateResult:
    approved: bool
    document: DocumentRecord
    reason: str
    wb_approved_version: Optional[DocumentRecord]  # The version that should be used


def check_before_send(
    document_to_send: DocumentRecord,
    record: CaseRecord,
) -> GateResult:
    """
    Gate check. Returns GateResult.approved=False if the document
    should not be sent.

    Rules (in priority order):
    1. Document must be WB-approved
    2. No newer WB-approved version may exist in the case record
    3. No WRONG_DOCUMENT_VERSION discrepancy may exist in the record
       for this document name
    """
    # Rule 1: Must be WB-approved
    if not document_to_send.is_wb_approved:
        wb_approved = _find_wb_approved(document_to_send.name, record)
        return GateResult(
            approved=False,
            document=document_to_send,
            reason=(
                f"Document '{document_to_send.name}' (version: {document_to_send.version_label}) "
                "is NOT WB-approved. "
                + (
                    f"Use '{wb_approved.version_label}' instead."
                    if wb_approved else
                    "No WB-approved version found in case record — obtain WB sign-off first."
                )
            ),
            wb_approved_version=wb_approved,
        )

    # Rule 2: No newer WB-approved version
    newer = _find_newer_wb_approved(document_to_send, record)
    if newer:
        return GateResult(
            approved=False,
            document=document_to_send,
            reason=(
                f"A newer WB-approved version exists: '{newer.version_label}' "
                f"(uploaded {newer.uploaded_at}). "
                f"Current document was uploaded {document_to_send.uploaded_at}. "
                "Send the newer version."
            ),
            wb_approved_version=newer,
        )

    # Rule 3: No existing discrepancy flag for this document
    for flag in record.discrepancy_flags:
        if (
            flag.kind == DiscrepancyKind.WRONG_DOCUMENT_VERSION
            and document_to_send.name in flag.description
        ):
            return GateResult(
                approved=False,
                document=document_to_send,
                reason=(
                    f"Case record has an unresolved version discrepancy for this document: "
                    f"{flag.description}"
                ),
                wb_approved_version=_find_wb_approved(document_to_send.name, record),
            )

    return GateResult(
        approved=True,
        document=document_to_send,
        reason="Document is WB-approved and no newer version exists.",
        wb_approved_version=None,
    )


def _find_wb_approved(doc_name: str, record: CaseRecord) -> Optional[DocumentRecord]:
    candidates = [
        d for d in record.documents
        if d.is_wb_approved and doc_name.split(" - ")[0] in d.name
    ]
    return max(candidates, key=lambda d: d.uploaded_at or 0) if candidates else None


def _find_newer_wb_approved(
    current: DocumentRecord, record: CaseRecord
) -> Optional[DocumentRecord]:
    if not current.uploaded_at:
        return None
    newer = [
        d for d in record.documents
        if d.is_wb_approved
        and d.drive_id != current.drive_id
        and d.uploaded_at
        and d.uploaded_at > current.uploaded_at
        and current.name.split(" - ")[0] in d.name
    ]
    return max(newer, key=lambda d: d.uploaded_at) if newer else None
