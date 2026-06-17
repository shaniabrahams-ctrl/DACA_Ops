"""
DACA Signing Authority Schema

Documents the complete rules for who can sign DACA agreements, what documentation
is required, what Webster Bank has accepted/rejected, and proven precedents.

Core principle (established across all cases):
  "Any person at any organizational level can sign a DACA as long as they have
   documented authorization from the entity, can be matched to account/CIP information,
   and provide required corporate authority proof."

Sources:
  - Rho DACA Process (Notion, June 16, 2026)
  - CSHELP-8871 (Anonos/Sonona case, June 16, 2026)
  - Rho DACA Submission Checklist (Notion, September 15, 2025)
  - 25+ Gmail threads with Webster Bank, March–June 2026
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SignerRelationship(str, Enum):
    """Relationship of signer to the entity."""
    UBO = "ubo"                                    # Ultimate Beneficial Owner
    OWNER = "owner"                               # Listed owner/founder
    ACCOUNT_OWNER = "account_owner"               # Account owner on Rho platform
    OFFICER = "officer"                           # Officer (CEO, CFO, COO, etc.)
    DIRECTOR = "director"                         # Board director
    EMPLOYEE = "employee"                         # Employee with delegated authority
    AUTHORIZED_REPRESENTATIVE = "authorized_rep"  # Non-employee with delegation


class AuthorityDocType(str, Enum):
    """Accepted forms of corporate signing authority proof."""
    BOARD_RESOLUTION = "board_resolution"
    AUTHORIZATION_LETTER = "authorization_letter"
    OFFICER_CERTIFICATE = "officer_certificate"
    ARTICLES_OF_INCORPORATION = "articles_of_incorporation"
    BYLAWS = "bylaws"
    OPERATING_AGREEMENT = "operating_agreement"
    BOARD_MINUTES = "board_minutes"
    COMPLETION_CERTIFICATE = "completion_certificate"


class EntityType(str, Enum):
    """Supported entity types for DACA."""
    CORPORATION = "corporation"
    LLC = "llc"
    PARTNERSHIP = "partnership"
    STARTUP = "startup"
    FOREIGN_SUBSIDIARY = "foreign_subsidiary"


class SigningOutcome(str, Enum):
    """Historical outcome of a signing attempt."""
    ACCEPTED = "accepted"
    REJECTED_INCOMPLETE_DOCS = "rejected_incomplete_docs"
    REJECTED_CIP_MISMATCH = "rejected_cip_mismatch"
    REJECTED_NO_AUTHORITY = "rejected_no_authority"
    REJECTED_MISSING_PROOF = "rejected_missing_proof"
    CONDITIONAL_APPROVAL = "conditional_approval"


@dataclass
class SigningAuthorityRule:
    """
    A rule that defines when someone is allowed to sign a DACA.
    """
    rule_id: str
    description: str
    entity_type: Optional[EntityType]  # None = applies to all
    signer_relationship: SignerRelationship
    required_docs: list[AuthorityDocType]
    also_requires_ub_documentation: bool  # Must include separate UBO proof?
    also_requires_account_owner_status: bool  # Must be added as Rho account owner?
    cip_matching_required: bool  # Must be verifiable on account/CIP?
    signer_title_required: bool  # Must have specific title?
    additional_requirements: str = ""
    source: str = ""  # Which Notion/ticket/email this came from
    date_established: str = ""


@dataclass
class SignerPrecedent:
    """
    A documented case where a signer was approved or rejected.
    Provides evidence for what Webster Bank has accepted.
    """
    precedent_id: str
    company_name: str
    signer_name: str
    signer_title: str
    signer_relationship: SignerRelationship
    entity_type: EntityType
    outcome: SigningOutcome
    date: str
    signed_by_date: Optional[str]  # When DACA was actually executed
    authority_docs_provided: list[AuthorityDocType] = field(default_factory=list)
    rejection_reason: Optional[str] = None
    remediation: Optional[str] = None  # How it was fixed
    webster_approved: bool = False  # Explicitly approved by Webster
    source: str = ""  # Jira ticket, Gmail thread, etc.
    notes: str = ""


@dataclass
class SigningAuthorityMatrix:
    """
    Master reference showing what's allowed given entity type + signer relationship.
    Used for pre-flight validation before submitting to Webster.
    """
    rules: dict[str, SigningAuthorityRule] = field(default_factory=dict)
    precedents: list[SignerPrecedent] = field(default_factory=list)
    webster_contact_for_questions: str = "jtroy@websterbank.com"

    def add_rule(self, rule: SigningAuthorityRule) -> None:
        """Register a signing authority rule."""
        self.rules[rule.rule_id] = rule

    def add_precedent(self, precedent: SignerPrecedent) -> None:
        """Register a documented case precedent."""
        self.precedents.append(precedent)

    def validate_signer(
        self,
        entity_type: EntityType,
        signer_relationship: SignerRelationship,
        is_ubo: bool = False,
    ) -> tuple[bool, list[str], list[AuthorityDocType]]:
        """
        Check if a proposed signer is allowed based on established rules.

        Returns:
          (allowed: bool, issues: list[str], required_docs: list[AuthorityDocType])
        """
        issues = []
        required_docs = []

        # Find applicable rules
        applicable_rules = [
            r for r in self.rules.values()
            if (r.entity_type is None or r.entity_type == entity_type)
            and r.signer_relationship == signer_relationship
        ]

        if not applicable_rules:
            issues.append(
                f"No established rule for {entity_type.value} with "
                f"{signer_relationship.value} signer relationship. "
                f"Escalate to {self.webster_contact_for_questions}"
            )
            return False, issues, []

        rule = applicable_rules[0]  # Use first (most specific) rule

        if rule.cip_matching_required:
            issues.append("Signer must be verifiable on account or CIP")
            required_docs.append(AuthorityDocType.COMPLETION_CERTIFICATE)

        if rule.also_requires_account_owner_status:
            issues.append("Signer must be added as account owner on Rho platform")

        if rule.also_requires_ub_documentation and not is_ubo:
            issues.append("Must provide separate UBO documentation (signer is not UBO)")

        required_docs.extend(rule.required_docs)

        allowed = len(issues) == 0  # All requirements met
        return allowed, issues, required_docs

    def get_precedents_for_relationship(
        self, signer_relationship: SignerRelationship
    ) -> list[SignerPrecedent]:
        """Find all documented cases for a given signer relationship."""
        return [p for p in self.precedents if p.signer_relationship == signer_relationship]

    def format_reference_guide(self) -> str:
        """Generate human-readable signing authority reference."""
        lines = ["# DACA Signing Authority Reference\n"]

        lines.append("## Core Principle")
        lines.append(
            "Any person at any organizational level can sign a DACA as long as:\n"
            "1. They have documented authorization from the entity\n"
            "2. They can be matched to account/CIP information\n"
            "3. If non-UBO: they are added as account owner AND provide authority proof\n"
            "4. All required documentation is complete\n"
        )

        lines.append("## Rules by Signer Relationship\n")
        for rel in SignerRelationship:
            rules = [r for r in self.rules.values() if r.signer_relationship == rel]
            if rules:
                lines.append(f"### {rel.value.replace('_', ' ').title()}")
                for rule in rules:
                    lines.append(f"- {rule.description}")
                    lines.append(f"  - Docs: {', '.join([d.value for d in rule.required_docs])}")
                    if rule.also_requires_ub_documentation:
                        lines.append("  - ALSO: Separate UBO documentation required")
                    if rule.cip_matching_required:
                        lines.append("  - ALSO: Must match CIP account information")

        lines.append("\n## Accepted Precedents\n")
        accepted = [p for p in self.precedents if p.webster_approved]
        for p in accepted[:10]:  # Show first 10
            lines.append(
                f"✓ {p.company_name} ({p.entity_type.value}): "
                f"{p.signer_name} ({p.signer_relationship.value}), {p.date}"
            )

        lines.append("\n## Rejections & Remediation\n")
        rejected = [p for p in self.precedents if p.outcome != SigningOutcome.ACCEPTED]
        for p in rejected[:10]:  # Show first 10
            lines.append(
                f"✗ {p.company_name}: {p.rejection_reason or 'Unknown'} "
                f"→ {p.remediation or 'Unresolved'}"
            )

        return "\n".join(lines)
