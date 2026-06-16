"""
DACA Ops Agent Harness

Enforces the mandatory sequence for every case operation:

  LOAD FULL CONTEXT → DETECT DISCREPANCIES → SURFACE TO HUMAN → HUMAN CLEARS → PROCEED

This is a CODE-LEVEL enforcement, not a prompt rule. Agents cannot
skip context loading, cannot send documents without version gate approval,
and cannot proceed past blockers without explicit human sign-off.

The harness is the reliability layer. Model capabilities determine
what gets extracted from context; the harness determines what is
allowed to proceed.

Workflow states:
  INVESTIGATING  → CaseContextLoader running
  NEEDS_HUMAN    → Blockers or missing fields require human input
  READY          → All blockers cleared, ready for DocuSign send
  SENT           → DocuSign envelopes dispatched
"""

from __future__ import annotations
from enum import Enum
from dataclasses import dataclass
from typing import Optional

from src.context.loader import CaseContextLoader
from src.context.record import CaseRecord
from src.agents.case_investigator import InvestigationRequest, InvestigationResult, run as investigate
from src.agents.version_gatekeeper import check_before_send, GateResult
from src.agents.docusign_preparer import prepare, format_for_human_review, EnvelopeManifest, PreconditionError


class WorkflowState(str, Enum):
    INVESTIGATING = "investigating"
    NEEDS_HUMAN = "needs_human"
    READY = "ready"
    SENT = "sent"


@dataclass
class WorkflowContext:
    request: InvestigationRequest
    state: WorkflowState
    investigation: Optional[InvestigationResult] = None
    manifests: Optional[list[EnvelopeManifest]] = None
    human_review_text: Optional[str] = None
    error: Optional[str] = None


async def run_case_workflow(
    request: InvestigationRequest,
    loader: CaseContextLoader,
    document_drive_id: Optional[str] = None,
) -> WorkflowContext:
    """
    Execute the full DACA case workflow for a single case.

    Returns a WorkflowContext at whatever state the harness reached.
    If state is NEEDS_HUMAN, human_review_text contains what to show the operator.
    If state is READY, manifests contains the envelope manifests pending approval.

    The harness NEVER sends DocuSign envelopes autonomously — the human must
    call approve_and_send() with explicit confirmation.
    """
    ctx = WorkflowContext(request=request, state=WorkflowState.INVESTIGATING)

    # Step 1: Load full context — mandatory, no bypass
    ctx.investigation = await investigate(request, loader)
    record = ctx.investigation.record

    # Step 2: Surface blockers to human if any exist
    if record.blockers or ctx.investigation.action_required:
        ctx.state = WorkflowState.NEEDS_HUMAN
        ctx.human_review_text = _format_needs_human(ctx.investigation)
        return ctx

    # Step 3: Find the WB-approved document to use
    if not record.documents:
        ctx.state = WorkflowState.NEEDS_HUMAN
        ctx.human_review_text = "No documents found in case record. Upload WB-approved DACA to Drive."
        return ctx

    wb_doc = next((d for d in record.documents if d.is_wb_approved), None)
    if not wb_doc:
        ctx.state = WorkflowState.NEEDS_HUMAN
        ctx.human_review_text = "No WB-approved document found. Obtain WB sign-off before proceeding."
        return ctx

    # Step 4: Version gate
    gate = check_before_send(wb_doc, record)
    if not gate.approved:
        ctx.state = WorkflowState.NEEDS_HUMAN
        ctx.human_review_text = f"Version gate blocked: {gate.reason}"
        return ctx

    # Step 5: Build manifests
    try:
        ctx.manifests = prepare(record, wb_doc)
    except PreconditionError as e:
        ctx.state = WorkflowState.NEEDS_HUMAN
        ctx.human_review_text = str(e)
        return ctx

    # Check if all manifests are ready
    not_ready = [m for m in ctx.manifests if not m.ready_to_send]
    if not_ready:
        ctx.state = WorkflowState.NEEDS_HUMAN
        ctx.human_review_text = (
            "Envelopes have missing fields — fill before send:\n"
            + format_for_human_review(ctx.manifests)
        )
        return ctx

    ctx.state = WorkflowState.READY
    ctx.human_review_text = (
        "All envelopes ready for send. Human approval required:\n"
        + format_for_human_review(ctx.manifests)
    )
    return ctx


def _format_needs_human(investigation: InvestigationResult) -> str:
    lines = [
        f"Case '{investigation.record.case_id}' requires human action before proceeding.",
        "",
        "REQUIRED ACTIONS:",
    ]
    for i, action in enumerate(investigation.action_required, 1):
        lines.append(f"  {i}. {action}")

    lines.append("")
    lines.append("TIMELINE SUMMARY:")
    lines.append(investigation.timeline_narrative)

    return "\n".join(lines)
