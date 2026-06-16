"""
DACA Email Drafter

Generates client-facing email drafts grounded in the full case context.
Injects the current style guide (from the feedback learning loop) into
every drafting prompt so each successive draft benefits from accumulated
human edits.

Email types handled:
  outstanding_items   — list of what client still needs to provide
  status_update       — case is progressing, no action required from client
  docusign_send       — DocuSign envelopes are ready, instructions for signing
  wb_revision         — WB counter-redline has been circulated, explanation
  execution_complete  — all envelopes executed, confirmation to client
  follow_up           — generic follow-up when no response in N days

Design notes:
  - Every draft is grounded in CaseRecord — no fabrication
  - Style guide is injected as a system-level instruction, not as user content
  - Drafts are returned as plain text for human review; never sent automatically
  - After human sends, caller is responsible for recording feedback via
    feedback_store.record_feedback()
  - Draft is evaluated before return — evaluation result is included in the
    returned DraftResult so the UI can show quality score alongside the draft
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from src.context.record import CaseRecord
from src.learning.style_synthesizer import load_current_style_guide
from src.learning.draft_evaluator import evaluate_draft, DraftEvaluation, format_evaluation_for_human
from src.learning.terminology_mapper import sanitize_for_client


EMAIL_TYPE_INSTRUCTIONS = {
    "outstanding_items": (
        "Write an email to the client listing the specific information still needed "
        "to complete their DACA agreements. Be concrete and numbered. Do not include "
        "items that are already on file. Separate items needed now from items pending "
        "internal review. Do not make the client feel at fault."
    ),
    "status_update": (
        "Write a brief status update to the client. Confirm what stage the case is at, "
        "what Rho is currently doing, and when they can expect to hear back. "
        "Do not create false urgency or make commitments Rho cannot keep."
    ),
    "docusign_send": (
        "Write an email introducing the DocuSign envelopes the client is about to receive. "
        "Name the entities covered. Give brief signing instructions. "
        "Tell them who to contact if they have issues."
    ),
    "wb_revision": (
        "Write an email forwarding the Webster Bank counter-redline to the client's counsel. "
        "Be clear that this is Webster's position, not Rho's markup. "
        "Invite them to review and revert with any questions."
    ),
    "execution_complete": (
        "Write a brief confirmation that all DACA envelopes have been fully executed. "
        "Name the entities. Note any next steps (e.g., account activation timeline). "
        "Keep it short."
    ),
    "follow_up": (
        "Write a polite follow-up to the client. Reference what was previously requested "
        "and how long ago. Do not be passive-aggressive. Offer to help if there are questions."
    ),
}

DRAFTING_SYSTEM_BASE = """\
You are drafting a client-facing email on behalf of a Rho DACA operations representative. \
Rho is a business banking platform. DACA (Deposit Account Control Agreement) is a lender \
compliance product. The client is a business that has submitted a DACA application.

Rules:
- Ground every claim in the case record provided. Do not invent names, dates, or facts.
- Write in a professional but approachable tone — not stiff, not casual.
- Use the rep's first name (provided) as the sign-off, not "Rho Operations".
- Do not include a subject line unless asked.
- Do not use markdown formatting — this is a plain-text email.
- Be concise. Clients are busy.
- Never promise a timeline you cannot confirm from the case record.
"""


@dataclass
class DraftResult:
    draft_text: str
    email_type: str
    evaluation: DraftEvaluation
    evaluation_summary: str    # Pre-formatted for display


async def generate_draft(
    record: CaseRecord,
    email_type: str,
    anthropic_client,
    rep_name: str = "Shani",
    additional_context: str = "",
    model: str = "claude-sonnet-4-6",
) -> DraftResult:
    """
    Generate a client email draft for this case.

    Returns DraftResult with the draft, its evaluation, and a display-ready
    evaluation summary. The caller must show both to the human rep before send.
    """
    if email_type not in EMAIL_TYPE_INSTRUCTIONS:
        raise ValueError(
            f"Unknown email type '{email_type}'. "
            f"Valid types: {list(EMAIL_TYPE_INSTRUCTIONS.keys())}"
        )

    style_guide = load_current_style_guide()
    system_prompt = _build_system_prompt(style_guide)
    user_content = _build_user_content(record, email_type, rep_name, additional_context)

    response = anthropic_client.messages.create(
        model=model,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )

    draft_text = response.content[0].text.strip()

    # Sanitize for client-facing language (mandatory terminology mappings)
    sanitized_draft, terminology_issues = sanitize_for_client(draft_text)

    evaluation = evaluate_draft(
        draft=sanitized_draft,
        anthropic_client=anthropic_client,
        email_type=email_type,
    )

    # If there were terminology issues, inject them into the evaluation flags
    if terminology_issues:
        evaluation.flags.extend(terminology_issues)

    return DraftResult(
        draft_text=sanitized_draft,
        email_type=email_type,
        evaluation=evaluation,
        evaluation_summary=format_evaluation_for_human(evaluation),
    )


def _build_system_prompt(style_guide: str) -> str:
    prompt = DRAFTING_SYSTEM_BASE

    if style_guide.strip():
        # Extract most recent synthesis section only
        sections = style_guide.split("---")
        latest_rules = sections[-1].strip() if len(sections) > 1 else style_guide.strip()
        prompt += (
            "\n\nSTYLE GUIDE (apply these rules — derived from real human edits on past drafts):\n"
            + latest_rules
        )

    return prompt


def _build_user_content(
    record: CaseRecord,
    email_type: str,
    rep_name: str,
    additional_context: str,
) -> str:
    instruction = EMAIL_TYPE_INSTRUCTIONS[email_type]

    entities = ", ".join(e.legal_name for e in record.entities) if record.entities else "unknown entities"
    primary_contact = next(
        (c for c in record.contacts if c.role in ("primary", "account_owner", "client")),
        record.contacts[0] if record.contacts else None,
    )
    contact_name = primary_contact.name.split()[0] if primary_contact else "there"

    open_items = ""
    if record.open_items:
        items_list = "\n".join(
            f"  - [{item.owner}] {item.description}" for item in record.open_items
        )
        open_items = f"\nOpen items:\n{items_list}"

    blockers = ""
    if record.blockers:
        blocker_list = "\n".join(f"  - {b.description}" for b in record.blockers)
        blockers = f"\nBlockers:\n{blocker_list}"

    lender_info = ""
    if record.lender:
        lender_info = (
            f"\nLender: {record.lender.legal_name}"
            + (f", contact: {record.lender.contact_name}" if record.lender.contact_name else "")
        )

    parts = [
        f"Task: {instruction}",
        f"\nCase ID: {record.case_id}",
        f"Client contact first name: {contact_name}",
        f"Entities: {entities}",
        f"Case stage: {record.stage}" if hasattr(record, "stage") else "",
        lender_info,
        open_items,
        blockers,
        f"\nAdditional context: {additional_context}" if additional_context else "",
        f"\nSign off as: {rep_name} @ Rho",
    ]

    return "\n".join(p for p in parts if p)
