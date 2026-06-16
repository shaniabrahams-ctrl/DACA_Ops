"""
Style Guide Synthesizer

Reads accumulated (draft, sent, diff) feedback records and uses an LLM
to distill them into a concise, actionable style guide for the email drafter.

The style guide is a plain-text document injected into every drafting prompt.
It is NOT a fine-tuning signal — it is a prompt-level preference specification
updated by an LLM synthesis pass each time N new feedback records accumulate.

Why this works:
  - The diff between agent draft and human-sent email is an implicit instruction
  - Repeated diffs in the same direction = a stable preference
  - The synthesizer's job is to find those stable patterns and state them clearly
  - The drafter's job is to apply them on the next attempt

Style guide location: data/email_style_guide.md
  - Tracked in repo so changes are auditable
  - Human-readable so the team can read and manually adjust it
  - Versioned: each synthesis appends a dated snapshot rather than overwriting

Synthesis prompt design:
  - Provides ALL feedback records in full (draft + sent + diff)
  - Asks the model to identify: tone preferences, structural patterns,
    content additions/removals that happen repeatedly, phrases that always
    get replaced, things the model reliably gets wrong
  - Outputs a numbered list of rules, each with an example from the feedback
"""

from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.learning.feedback_store import DraftFeedbackRecord, load_all_feedback


STYLE_GUIDE_PATH = Path(__file__).parent.parent.parent / "data" / "email_style_guide.md"

SYNTHESIS_SYSTEM_PROMPT = """\
You are analyzing a set of email drafts and the final versions a human DACA operations rep \
sent to clients. Your job is to identify stable, repeating preferences — things the human \
consistently added, removed, reworded, or restructured.

Focus on patterns that appear across multiple examples. Ignore one-off changes that are \
case-specific. Your output will be used to instruct future drafts, so be concrete and \
actionable — each rule should be something a drafter can directly apply.

Output format: a numbered list of rules, each with:
  - The rule itself (one sentence, directive)
  - One short example from the feedback (before → after)
  - Confidence: HIGH (seen 3+ times), MEDIUM (seen 2 times), LOW (seen once but notable)

End with a section called ANTI-PATTERNS listing things the draft consistently gets wrong.\
"""


def synthesize_style_guide(
    anthropic_client,
    model: str = "claude-haiku-4-5-20251001",
    records: Optional[list[DraftFeedbackRecord]] = None,
) -> str:
    """
    Run a synthesis pass over all feedback records and update the style guide.

    Returns the new style guide text.
    Uses Haiku — synthesis is a structured extraction task, not a reasoning one.
    """
    if records is None:
        records = load_all_feedback()

    if not records:
        return ""

    feedback_text = _format_feedback_for_synthesis(records)

    response = anthropic_client.messages.create(
        model=model,
        max_tokens=2048,
        system=SYNTHESIS_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                f"Here are {len(records)} email feedback records "
                f"(agent draft vs. human-sent version):\n\n"
                f"{feedback_text}\n\n"
                "Please synthesize the stable preferences into a style guide."
            ),
        }],
    )

    new_rules = response.content[0].text
    updated_guide = _append_to_style_guide(new_rules, len(records))
    return updated_guide


def load_current_style_guide() -> str:
    """Return the current style guide text, or empty string if none exists yet."""
    if not STYLE_GUIDE_PATH.exists():
        return ""
    return STYLE_GUIDE_PATH.read_text()


def _format_feedback_for_synthesis(records: list[DraftFeedbackRecord]) -> str:
    parts = []
    for i, r in enumerate(records, 1):
        diff = r.diff
        parts.append(f"""--- Example {i} (case: {r.case_id}, type: {r.email_type}) ---
AGENT DRAFT:
{r.agent_draft}

HUMAN SENT:
{r.human_sent}

DIFF SUMMARY:
  Added: {diff.sentences_added or 'none'}
  Removed: {diff.sentences_removed or 'none'}
  Replaced: {[f"{x['before']!r} → {x['after']!r}" for x in diff.phrases_replaced] or 'none'}
  Length delta: {'+' if diff.length_delta >= 0 else ''}{diff.length_delta} chars
""")
    return "\n".join(parts)


def _append_to_style_guide(new_rules: str, record_count: int) -> str:
    """
    Append a new dated synthesis to the style guide file.
    Previous rules are preserved — older snapshots provide audit trail.
    """
    STYLE_GUIDE_PATH.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = (
        f"## Synthesis Pass — {timestamp} "
        f"({record_count} feedback records)\n\n"
    )

    existing = STYLE_GUIDE_PATH.read_text() if STYLE_GUIDE_PATH.exists() else ""

    if not existing:
        full_content = (
            "# DACA Email Draft Style Guide\n\n"
            "_Auto-generated from human edit feedback. Do not edit the rules directly — "
            "edit the feedback data or the synthesis prompt instead._\n\n"
            "_Each section below is a dated synthesis pass. The most recent section "
            "is authoritative; earlier sections are retained for audit._\n\n"
            "---\n\n"
        )
    else:
        full_content = existing + "\n---\n\n"

    full_content += header + new_rules + "\n"
    STYLE_GUIDE_PATH.write_text(full_content)
    return full_content
