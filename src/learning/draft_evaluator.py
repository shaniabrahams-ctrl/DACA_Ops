"""
Draft Evaluator

Scores an agent-produced email draft against the current style guide
BEFORE surfacing it to the human rep.

The goal is not to block drafts — the human always sees the draft. The goal
is to surface a quality score and specific flags so the rep knows immediately
what to look for, and so the system can track whether draft quality is
improving over time.

Score interpretation:
  5 — Matches all known style preferences; likely needs minimal editing
  4 — Minor issues (1-2 flags); quick edit expected
  3 — Moderate issues; noticeable editing expected
  2 — Major issues; draft is a starting point only
  1 — Do not use; regenerate with additional context

Flags are derived from the current style guide rules — each rule violation
becomes a flag. This means the evaluator automatically gets stricter as the
style guide accumulates more rules.

Evaluation is done with Haiku (cheap, fast) since it's a classification task.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from src.learning.style_synthesizer import load_current_style_guide


@dataclass
class DraftEvaluation:
    score: int                    # 1-5
    flags: list[str]              # Specific rule violations
    suggestions: list[str]        # Concrete fix for each flag
    style_guide_version: str      # Timestamp of style guide used
    raw_response: str             # Full evaluator response for debugging


EVALUATOR_SYSTEM_PROMPT = """\
You are evaluating an email draft against a style guide derived from real human edits. \
Your job is to identify where the draft violates the style guide rules.

For each rule in the style guide that the draft violates, cite the rule number, \
explain the violation in one sentence, and suggest the specific fix.

Output format:
SCORE: [1-5]
FLAGS:
  - Rule N: [violation description] → Fix: [specific change]
  ...
(Output "FLAGS: none" if the draft follows all rules.)

Scoring rubric:
  5 = no flags
  4 = 1 flag (minor)
  3 = 2-3 flags or 1 structural flag
  2 = 4+ flags or multiple structural issues
  1 = draft does not match the context / regenerate\
"""


def evaluate_draft(
    draft: str,
    anthropic_client,
    email_type: str = "",
    model: str = "claude-haiku-4-5-20251001",
) -> DraftEvaluation:
    """
    Evaluate a draft against the current style guide.
    Returns DraftEvaluation with score and flags.

    If no style guide exists yet, returns score=None and empty flags
    (not enough data to evaluate).
    """
    style_guide = load_current_style_guide()

    if not style_guide.strip():
        return DraftEvaluation(
            score=0,
            flags=["No style guide yet — evaluation not available until first synthesis pass."],
            suggestions=[],
            style_guide_version="none",
            raw_response="",
        )

    # Extract the most recent synthesis section (authoritative)
    sections = style_guide.split("---")
    latest_rules = sections[-1].strip() if sections else style_guide

    response = anthropic_client.messages.create(
        model=model,
        max_tokens=1024,
        system=EVALUATOR_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                f"STYLE GUIDE (current rules):\n{latest_rules}\n\n"
                f"EMAIL TYPE: {email_type or 'unspecified'}\n\n"
                f"DRAFT TO EVALUATE:\n{draft}"
            ),
        }],
    )

    raw = response.content[0].text
    score, flags, suggestions = _parse_evaluation(raw)

    # Derive style guide version from its first heading
    version = _extract_guide_version(style_guide)

    return DraftEvaluation(
        score=score,
        flags=flags,
        suggestions=suggestions,
        style_guide_version=version,
        raw_response=raw,
    )


def format_evaluation_for_human(evaluation: DraftEvaluation) -> str:
    """Format evaluation result for display to the Rho rep alongside the draft."""
    if evaluation.score == 0:
        return "(Draft quality evaluation: not yet available — collecting feedback first.)"

    score_label = {5: "Looks good", 4: "Minor edits expected", 3: "Moderate edits expected",
                   2: "Heavy edits expected", 1: "Regenerate recommended"}.get(evaluation.score, "")

    lines = [f"Draft quality: {evaluation.score}/5 — {score_label}"]
    if evaluation.flags:
        lines.append("Flags:")
        for flag, suggestion in zip(evaluation.flags, evaluation.suggestions or [""]*len(evaluation.flags)):
            lines.append(f"  • {flag}")
            if suggestion:
                lines.append(f"    → {suggestion}")
    return "\n".join(lines)


def _parse_evaluation(raw: str) -> tuple[int, list[str], list[str]]:
    """Parse score, flags, and suggestions from evaluator output."""
    score = 3   # Default if parsing fails
    flags = []
    suggestions = []

    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("SCORE:"):
            try:
                score = int(line.split(":")[1].strip())
            except (ValueError, IndexError):
                pass
        elif line.startswith("- Rule") or line.startswith("• Rule"):
            parts = line.lstrip("-•").strip()
            if "→ Fix:" in parts:
                flag_part, fix_part = parts.split("→ Fix:", 1)
                flags.append(flag_part.strip())
                suggestions.append(fix_part.strip())
            else:
                flags.append(parts)
                suggestions.append("")

    if "FLAGS: none" in raw or "FLAGS:\n  none" in raw.lower():
        flags = []
        suggestions = []

    return score, flags, suggestions


def _extract_guide_version(style_guide: str) -> str:
    for line in style_guide.splitlines():
        if "Synthesis Pass" in line:
            return line.strip("# ").strip()
    return "unknown"
