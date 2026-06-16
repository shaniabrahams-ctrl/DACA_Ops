"""
Client-Facing Terminology Mapper

Maps internal/technical terms to client-facing equivalents for email drafts.
This prevents the drafter from accidentally using Rho jargon that confuses clients.

Examples:
  - DACA Clearing Account → DACA Account
  - Springing DACA → DACA (in most client contexts)
  - RAP → (internal system, never mentioned to clients)
  - TCT → (internal system, never mentioned to clients)

The terminology map is consulted AFTER draft generation to ensure consistency.
"""

from __future__ import annotations
from typing import Dict

# Internal → Client-facing mappings
TERMINOLOGY_MAP: Dict[str, str] = {
    "DACA Clearing Account": "DACA Account",
    "Springing DACA": "DACA",
    "daca@rho.co": "our DACA team",
    "DocuSign": "DocuSign",  # Already client-facing
    "Webster Bank": "Webster Bank",  # Already client-facing
}

# Phrases that should NEVER appear in client-facing emails
FORBIDDEN_TERMS = [
    "RAP",
    "TCT",
    "Tenet",
    "impersonate",
    "Middesk",
    "Alloy",
    "Tracer",
    "compliance package",
    "lender onboarding",
]


def sanitize_for_client(draft: str) -> tuple[str, list[str]]:
    """
    Apply terminology mappings and check for forbidden terms.

    Returns:
      (sanitized_draft, list_of_issues_found)

    Issues are warnings, not blockers — the rep still sees the draft,
    but we flag places where client-facing language could improve.
    """
    sanitized = draft
    issues = []

    # Apply terminology mappings
    for internal, client_facing in TERMINOLOGY_MAP.items():
        if internal in sanitized:
            sanitized = sanitized.replace(internal, client_facing)

    # Check for forbidden terms (case-insensitive)
    sanitized_lower = sanitized.lower()
    for forbidden in FORBIDDEN_TERMS:
        if forbidden.lower() in sanitized_lower:
            issues.append(f"Uses internal term '{forbidden}' — consider replacing with client-facing equivalent")

    return sanitized, issues


def add_terminology_rules_to_style_guide() -> str:
    """
    Returns text to be appended to the style guide as a permanent rule set.
    Run this once when initializing the style guide.
    """
    return """## Mandatory Terminology Rules

These are not learned from feedback — they are hardcoded to prevent client confusion:

- **DACA Clearing Account** → **DACA Account** (internal vs. client-facing)
- **Springing DACA** → **DACA** (when addressing clients)
- **daca@rho.co** → **our DACA team** (email address is internal)

**Never mention to clients:**
- Internal system names (RAP, TCT, Tenet)
- Compliance vendor names (Middesk, Alloy, Tracer)
- Internal processes (impersonation, account deactivation mechanics)
"""
