"""
Feedback Capture — closing the learning loop

Called after a human rep sends an email that was initiated from an agent draft.
Compares the sent version to the draft, records the feedback, and triggers
a style guide synthesis pass if enough new examples have accumulated.

Integration point:
  The harness or UI layer calls capture_and_maybe_synthesize() immediately
  after detecting that the rep sent a reply in a DACA thread.

Gmail detection strategy:
  - The agent draft is stored locally with a draft_id
  - When the rep sends from Gmail, we search the Sent folder for a message
    in the same thread that was sent after the draft was generated
  - The sent message body is compared to the stored draft
  - If similarity < 100%, the diff is recorded as feedback

This means the loop requires NO explicit human action beyond just sending.
The rep edits the draft however they want and hits send — the system learns
from the delta automatically.
"""

from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.learning.feedback_store import record_feedback, should_synthesize, DraftFeedbackRecord
from src.learning.style_synthesizer import synthesize_style_guide


PENDING_DRAFTS_PATH = Path(__file__).parent.parent.parent / "data" / "pending_drafts.jsonl"


@dataclass
class PendingDraft:
    """A draft that has been shown to the human but not yet sent."""
    draft_id: str
    case_id: str
    thread_id: str       # Gmail thread ID to watch for the sent reply
    email_type: str
    draft_text: str
    generated_at: str    # ISO datetime
    rep_email: str


def register_pending_draft(draft: PendingDraft) -> None:
    """Record that a draft was shown to the rep. Store so we can match it to the sent version."""
    PENDING_DRAFTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PENDING_DRAFTS_PATH.open("a") as f:
        f.write(json.dumps(vars(draft)) + "\n")


def capture_and_maybe_synthesize(
    draft_id: str,
    human_sent_text: str,
    thread_subject: str,
    recipient_email: str,
    case_stage: str,
    anthropic_client,
) -> Optional[str]:
    """
    Record feedback for a sent email and trigger synthesis if due.

    Returns:
      - The new style guide text if synthesis ran, else None.

    Call this after detecting that the rep sent an email in a tracked thread.
    """
    pending = _load_pending_draft(draft_id)
    if not pending:
        return None

    record_feedback(
        case_id=pending.case_id,
        thread_subject=thread_subject,
        recipient_email=recipient_email,
        email_type=pending.email_type,
        agent_draft=pending.draft_text,
        human_sent=human_sent_text,
        rep_email=pending.rep_email,
        case_stage=case_stage,
    )

    _mark_draft_captured(draft_id)

    if should_synthesize():
        return synthesize_style_guide(anthropic_client)

    return None


def get_uncaptured_drafts() -> list[PendingDraft]:
    """Return all drafts that haven't been matched to a sent email yet."""
    if not PENDING_DRAFTS_PATH.exists():
        return []
    drafts = []
    with PENDING_DRAFTS_PATH.open() as f:
        for line in f:
            line = line.strip()
            if line:
                d = json.loads(line)
                if not d.get("captured"):
                    drafts.append(PendingDraft(**{k: v for k, v in d.items() if k != "captured"}))
    return drafts


def _load_pending_draft(draft_id: str) -> Optional[PendingDraft]:
    if not PENDING_DRAFTS_PATH.exists():
        return None
    with PENDING_DRAFTS_PATH.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if d.get("draft_id") == draft_id:
                return PendingDraft(**{k: v for k, v in d.items() if k != "captured"})
    return None


def _mark_draft_captured(draft_id: str) -> None:
    """Mark a pending draft as captured so it isn't processed again."""
    if not PENDING_DRAFTS_PATH.exists():
        return
    lines = PENDING_DRAFTS_PATH.read_text().splitlines()
    updated = []
    for line in lines:
        if not line.strip():
            continue
        d = json.loads(line)
        if d.get("draft_id") == draft_id:
            d["captured"] = True
        updated.append(json.dumps(d))
    PENDING_DRAFTS_PATH.write_text("\n".join(updated) + "\n")
