"""
Email Draft Feedback Store

Records every (agent_draft, human_sent) pair so the style synthesizer
has raw material to learn from.

The signal: wherever the human's sent version differs from the agent's
draft is an implicit instruction. Accumulated across cases, patterns emerge:
recurring additions, recurring deletions, consistent tone shifts, structural
preferences, specific phrases that always get replaced.

Storage: append-only JSON lines file (one record per sent email).
Schema is deliberately flat — the synthesizer reads raw text, not structured fields.

Capture flow:
  1. Agent produces draft → EmailDraftContext stored with draft_id
  2. Human edits in Gmail, sends
  3. After send, capture_feedback() is called with the sent message content
  4. Diff is computed and stored alongside both versions and case context
  5. When feedback_count % SYNTHESIS_BATCH_SIZE == 0, trigger synthesis
"""

from __future__ import annotations
import json
import hashlib
import difflib
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


FEEDBACK_PATH = Path(__file__).parent.parent.parent / "data" / "email_feedback.jsonl"
SYNTHESIS_BATCH_SIZE = 5   # Re-synthesize style guide after this many new examples


@dataclass
class EditDiff:
    """Structured diff between agent draft and human-sent version."""
    sentences_added: list[str]       # In sent but not draft
    sentences_removed: list[str]     # In draft but not sent
    phrases_replaced: list[dict]     # [{"before": ..., "after": ...}]
    length_delta: int                # Positive = human made it longer
    summary: str                     # One-line characterization (filled by synthesizer)


@dataclass
class DraftFeedbackRecord:
    feedback_id: str
    case_id: str
    thread_subject: str
    recipient_email: str
    email_type: str          # e.g. "outstanding_items", "status_update", "docusign_send"
    agent_draft: str
    human_sent: str
    diff: EditDiff
    recorded_at: str         # ISO datetime
    rep_email: str           # Who sent it (shani.abrahams@rho.co etc.)
    case_stage: str          # e.g. "awaiting_signatures", "wb_review", "execution"


def compute_diff(agent_draft: str, human_sent: str) -> EditDiff:
    """
    Compute a structured diff between draft and sent versions.
    Sentence-level granularity — word-level diffs are too noisy for synthesis.
    """
    def to_sentences(text: str) -> list[str]:
        import re
        # Split on sentence-ending punctuation followed by whitespace or newline
        raw = re.split(r'(?<=[.!?])\s+', text.strip())
        return [s.strip() for s in raw if s.strip()]

    draft_sents = to_sentences(agent_draft)
    sent_sents = to_sentences(human_sent)

    matcher = difflib.SequenceMatcher(None, draft_sents, sent_sents, autojunk=False)

    added = []
    removed = []
    replaced = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "insert":
            added.extend(sent_sents[j1:j2])
        elif tag == "delete":
            removed.extend(draft_sents[i1:i2])
        elif tag == "replace":
            # Pair up replacements where possible
            draft_chunk = " ".join(draft_sents[i1:i2])
            sent_chunk = " ".join(sent_sents[j1:j2])
            replaced.append({"before": draft_chunk, "after": sent_chunk})

    return EditDiff(
        sentences_added=added,
        sentences_removed=removed,
        phrases_replaced=replaced,
        length_delta=len(human_sent) - len(agent_draft),
        summary="",  # Filled by synthesizer on next synthesis pass
    )


def record_feedback(
    case_id: str,
    thread_subject: str,
    recipient_email: str,
    email_type: str,
    agent_draft: str,
    human_sent: str,
    rep_email: str,
    case_stage: str = "",
) -> DraftFeedbackRecord:
    """
    Compute diff between draft and sent, store record, return it.
    Caller should check should_synthesize() after this and trigger synthesis if True.
    """
    diff = compute_diff(agent_draft, human_sent)

    record = DraftFeedbackRecord(
        feedback_id=hashlib.sha256(
            f"{case_id}{agent_draft[:50]}{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:16],
        case_id=case_id,
        thread_subject=thread_subject,
        recipient_email=recipient_email,
        email_type=email_type,
        agent_draft=agent_draft,
        human_sent=human_sent,
        diff=diff,
        recorded_at=datetime.now(timezone.utc).isoformat(),
        rep_email=rep_email,
        case_stage=case_stage,
    )

    FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with FEEDBACK_PATH.open("a") as f:
        f.write(json.dumps(_serialize(record)) + "\n")

    return record


def load_all_feedback() -> list[DraftFeedbackRecord]:
    if not FEEDBACK_PATH.exists():
        return []
    records = []
    with FEEDBACK_PATH.open() as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(_deserialize(json.loads(line)))
    return records


def feedback_count() -> int:
    if not FEEDBACK_PATH.exists():
        return 0
    with FEEDBACK_PATH.open() as f:
        return sum(1 for line in f if line.strip())


def should_synthesize() -> bool:
    """True when a new synthesis pass is due based on accumulated feedback."""
    count = feedback_count()
    return count > 0 and count % SYNTHESIS_BATCH_SIZE == 0


def _serialize(record: DraftFeedbackRecord) -> dict:
    d = asdict(record)
    return d


def _deserialize(d: dict) -> DraftFeedbackRecord:
    d["diff"] = EditDiff(**d["diff"])
    return DraftFeedbackRecord(**d)
