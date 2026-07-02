"""
Client Comms Agent — drafts and sends replies on the Zendesk channel.

Jira/CSHELP is internal case tracking. Zendesk (this module) plus Gmail are
where the client actually writes in and where the DACA Ops team responds,
attaches documents, and shares SendSafely links. This agent is the only
caller of ZendeskClient's write path (post_comment/create_ticket) — nothing
else in the codebase should call those directly, so the human-approval gate
below is the sole path anything reaches a client through.

Two-step, always:
  1. generate_reply() -> CommsDraftResult. Never sends. Grounded in the
     actual client thread (not just the case record) plus the same style
     guide / evaluation / terminology pipeline email_drafter.py uses, so
     voice stays consistent whether the reply goes out over Gmail or
     Zendesk.
  2. send_reply() -> SendReceipt. Takes the human-approved final text
     (which may differ from the draft after edits) and an explicit
     approved_by identity. This is the only function that touches
     ZendeskClient.post_comment.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from src.context.record import CaseRecord
from src.integrations.zendesk_client import ZendeskClient, ZendeskTicketThread, SendReceipt
from src.agents.email_drafter import (
    EMAIL_TYPE_INSTRUCTIONS,
    DRAFTING_SYSTEM_BASE,
)
from src.learning.style_synthesizer import load_current_style_guide
from src.learning.draft_evaluator import evaluate_draft, DraftEvaluation, format_evaluation_for_human
from src.learning.terminology_mapper import sanitize_for_client


SENDSAFELY_DROPZONE_URL = "https://rho.sendsafely.com/dropzone/daca"


@dataclass
class SuggestedAttachment:
    label: str              # e.g. "Standard Springing DACA template"
    drive_id: Optional[str]  # Source doc from the case record, if applicable


@dataclass
class CommsDraftResult:
    ticket_id: str
    reply_type: str
    draft_text: str
    evaluation: DraftEvaluation
    evaluation_summary: str
    suggested_attachments: list[SuggestedAttachment]
    include_sendsafely_link: bool


async def fetch_client_thread(
    zendesk: ZendeskClient, ticket_id: str
) -> Optional[ZendeskTicketThread]:
    """Fetch the ticket + its comment thread. Returns None if the ticket
    can't be read — caller should fall back to drafting from the case
    record alone rather than blocking on a Zendesk outage."""
    return await zendesk.get_ticket_with_thread(ticket_id)


async def generate_reply(
    record: CaseRecord,
    reply_type: str,
    anthropic_client,
    ticket_id: str,
    thread: Optional[ZendeskTicketThread] = None,
    rep_name: str = "Shani",
    request_sendsafely: bool = False,
    attachments: Optional[list[SuggestedAttachment]] = None,
    additional_context: str = "",
    model: str = "claude-sonnet-4-6",
) -> CommsDraftResult:
    """
    Draft a Zendesk reply. Never sends — returns a CommsDraftResult for
    human review, same contract as email_drafter.generate_draft().

    Grounding priority: the actual client message text in `thread` (what
    they actually asked) takes precedence over case-record inference —
    replying to a question the client didn't ask is worse than a slightly
    less complete answer to the one they did.
    """
    if reply_type not in EMAIL_TYPE_INSTRUCTIONS:
        raise ValueError(
            f"Unknown reply type '{reply_type}'. Valid types: {list(EMAIL_TYPE_INSTRUCTIONS.keys())}"
        )

    style_guide = load_current_style_guide()
    system_prompt = _build_system_prompt(style_guide, request_sendsafely)
    user_content = _build_user_content(
        record, reply_type, rep_name, thread, additional_context
    )

    response = anthropic_client.messages.create(
        model=model,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    draft_text = response.content[0].text.strip()

    sanitized_draft, terminology_issues = sanitize_for_client(draft_text)

    evaluation = evaluate_draft(
        draft=sanitized_draft,
        anthropic_client=anthropic_client,
        email_type=reply_type,
    )
    if terminology_issues:
        evaluation.flags.extend(terminology_issues)

    return CommsDraftResult(
        ticket_id=ticket_id,
        reply_type=reply_type,
        draft_text=sanitized_draft,
        evaluation=evaluation,
        evaluation_summary=format_evaluation_for_human(evaluation),
        suggested_attachments=attachments or [],
        include_sendsafely_link=request_sendsafely,
    )


async def send_reply(
    zendesk: ZendeskClient,
    ticket_id: str,
    approved_text: str,
    approved_by: str,
    attachment_bytes: Optional[list[tuple[str, bytes, str]]] = None,
    public: bool = True,
) -> SendReceipt:
    """
    Send the human-approved reply. `approved_text` is what actually goes
    out — it may be the draft verbatim or an edited version; this function
    does not care which, but it never generates or alters text itself.

    attachment_bytes: list of (filename, bytes, content_type) tuples for
    files to attach directly (e.g. the standard template). For anything
    sensitive the client should upload (compliance documents, account
    info), use build_sendsafely_block() to embed the dropzone link in the
    reply text instead of pulling files through Rho's own systems.
    """
    upload_tokens = []
    for filename, data, content_type in attachment_bytes or []:
        token = await zendesk.upload_attachment(filename, data, content_type)
        upload_tokens.append(token)

    return await zendesk.post_comment(
        ticket_id=ticket_id,
        body=approved_text,
        approved_by=approved_by,
        public=public,
        upload_tokens=upload_tokens or None,
    )


def build_sendsafely_block() -> str:
    """
    Standard language for requesting sensitive documents back through
    SendSafely rather than as a plain email/Zendesk attachment. Per the
    SOP: 'Please do not send your SSN, account number, ID, or any personal
    information via email.'
    """
    return (
        "For any sensitive documents (IDs, account statements, or other "
        "personal/financial information), please upload them securely here "
        f"rather than as an email attachment: {SENDSAFELY_DROPZONE_URL}"
    )


def _build_system_prompt(style_guide: str, request_sendsafely: bool) -> str:
    prompt = DRAFTING_SYSTEM_BASE + (
        "\n\nThis reply is going out on the Zendesk client-support channel, not email. "
        "Ground your answer in the client's actual message from the thread provided — "
        "answer what they asked, don't just restate the case status."
    )
    if request_sendsafely:
        prompt += (
            "\n\nThe human operator has flagged that sensitive documents are needed back "
            "from the client. Reference that they should be uploaded via SendSafely rather "
            "than emailed — do not ask for SSNs, account numbers, or IDs directly in the reply."
        )
    if style_guide.strip():
        sections = style_guide.split("---")
        latest_rules = sections[-1].strip() if len(sections) > 1 else style_guide.strip()
        prompt += (
            "\n\nSTYLE GUIDE (apply these rules — derived from real human edits on past drafts):\n"
            + latest_rules
        )
    return prompt


def _build_user_content(
    record: CaseRecord,
    reply_type: str,
    rep_name: str,
    thread: Optional[ZendeskTicketThread],
    additional_context: str,
) -> str:
    instruction = EMAIL_TYPE_INSTRUCTIONS[reply_type]
    entities = ", ".join(e.legal_name for e in record.entities) if record.entities else "unknown entities"

    thread_text = ""
    if thread and thread.comments:
        public_comments = [c for c in thread.comments if c.public]
        if public_comments:
            last = public_comments[-1]
            thread_text = f"\nClient's most recent message:\n{last.body}"

    open_items = ""
    if record.open_items:
        items_list = "\n".join(f"  - [{item.owner}] {item.description}" for item in record.open_items)
        open_items = f"\nOpen items:\n{items_list}"

    parts = [
        f"Task: {instruction}",
        f"\nCase ID: {record.case_id}",
        f"Entities: {entities}",
        thread_text,
        open_items,
        f"\nAdditional context: {additional_context}" if additional_context else "",
        f"\nSign off as: {rep_name} @ Rho",
    ]
    return "\n".join(p for p in parts if p)
