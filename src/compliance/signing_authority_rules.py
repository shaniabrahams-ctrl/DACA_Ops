"""
DACA Signing Authority Rules — Populated Registry

This module instantiates the SigningAuthorityMatrix with all rules and precedents
derived from historical Jira tickets, Gmail threads, and internal documentation
(April 2025 — June 2026).

Rules are grounded in actual accepted cases, not inferred. Each rule includes
source citations.
"""

from src.compliance.signing_authority_schema import (
    SigningAuthorityMatrix,
    SigningAuthorityRule,
    SignerPrecedent,
    SignerRelationship,
    AuthorityDocType,
    EntityType,
    SigningOutcome,
)


def build_signing_authority_matrix() -> SigningAuthorityMatrix:
    """
    Build and return the complete DACA signing authority rules matrix.
    """
    matrix = SigningAuthorityMatrix()

    # ============================================================================
    # RULES (What's Allowed)
    # ============================================================================

    # Rule 1: UBO as signer (simplest case)
    matrix.add_rule(SigningAuthorityRule(
        rule_id="ubo_as_signer",
        description=(
            "Ultimate Beneficial Owner signing the DACA. "
            "No separate UBO documentation required (they ARE the UBO). "
            "Inherent authority; minimal friction."
        ),
        entity_type=None,  # Applies to all entity types
        signer_relationship=SignerRelationship.UBO,
        required_docs=[
            AuthorityDocType.COMPLETION_CERTIFICATE,
            AuthorityDocType.OFFICER_CERTIFICATE,
        ],
        also_requires_ub_documentation=False,
        also_requires_account_owner_status=False,
        cip_matching_required=True,
        signer_title_required=False,
        additional_requirements=(
            "Signer must be verifiable as UBO via Alloy/Tracer report. "
            "Must be matched to account/CIP information."
        ),
        source="CSHELP-8871 (Anonos/Sonona case, June 16, 2026)",
        date_established="2025-09-15",
    ))

    # Rule 2: Officer as signer with board resolution
    matrix.add_rule(SigningAuthorityRule(
        rule_id="officer_with_board_resolution",
        description=(
            "Officer (CEO, CFO, COO, etc.) signing with documented board resolution. "
            "Title requirement waived: any title acceptable if authorized. "
            "Requires separate UBO documentation."
        ),
        entity_type=None,  # Applies to all entity types
        signer_relationship=SignerRelationship.OFFICER,
        required_docs=[
            AuthorityDocType.BOARD_RESOLUTION,
            AuthorityDocType.COMPLETION_CERTIFICATE,
            AuthorityDocType.OFFICER_CERTIFICATE,
        ],
        also_requires_ub_documentation=True,
        also_requires_account_owner_status=False,
        cip_matching_required=True,
        signer_title_required=False,  # Title doesn't matter if authorized
        additional_requirements=(
            "Board resolution must explicitly authorize DACA signing, not just general authority. "
            "Must provide separate Alloy/Tracer for UBO."
        ),
        source="Rho DACA Process (Notion, June 16, 2026)",
        date_established="2025-09-15",
    ))

    # Rule 3: Account owner as signer with authority documentation
    matrix.add_rule(SigningAuthorityRule(
        rule_id="account_owner_with_authority",
        description=(
            "Account owner on Rho platform (non-UBO) signing with corporate authority proof. "
            "Permits delegation of signing authority to non-UBO staff. "
            "BOTH account owner status AND authority documentation required."
        ),
        entity_type=None,
        signer_relationship=SignerRelationship.ACCOUNT_OWNER,
        required_docs=[
            AuthorityDocType.BOARD_RESOLUTION,
            AuthorityDocType.COMPLETION_CERTIFICATE,
            AuthorityDocType.OFFICER_CERTIFICATE,
        ],
        also_requires_ub_documentation=True,
        also_requires_account_owner_status=True,
        cip_matching_required=True,
        signer_title_required=False,
        additional_requirements=(
            "Signer must be pre-added to Rho platform as account owner (client action). "
            "Authorization proof must be obtained BEFORE Rho platform provisioning. "
            "Separate UBO Alloy/Tracer report mandatory."
        ),
        source="CSHELP-8871 (June 16, 2026) — Shani Abrahams: "
                "'I think for prior DACAs, we were able to have a non-UBO sign if they "
                "were added as an account owner and also provided corporate signing authority.'",
        date_established="2026-06-16",
    ))

    # Rule 4: Employee with delegated authority
    matrix.add_rule(SigningAuthorityRule(
        rule_id="employee_with_delegation",
        description=(
            "Non-officer employee with explicit delegation from board/management. "
            "Permits CFO or controller-level staff to sign on behalf of entity. "
            "Requires formal delegation document."
        ),
        entity_type=None,
        signer_relationship=SignerRelationship.EMPLOYEE,
        required_docs=[
            AuthorityDocType.AUTHORIZATION_LETTER,
            AuthorityDocType.COMPLETION_CERTIFICATE,
            AuthorityDocType.OFFICER_CERTIFICATE,
        ],
        also_requires_ub_documentation=True,
        also_requires_account_owner_status=False,
        cip_matching_required=True,
        signer_title_required=False,
        additional_requirements=(
            "Delegation letter must be signed by UBO or board-authorized officer. "
            "Must clearly state DACA signing authority is granted. "
            "Signer must be actual employee (verifiable via CIP)."
        ),
        source="Rho DACA Process (Notion, June 16, 2026)",
        date_established="2025-09-15",
    ))

    # Rule 5: Foreign subsidiary — Poland (special case)
    matrix.add_rule(SigningAuthorityRule(
        rule_id="foreign_subsidiary_poland",
        description=(
            "Polish subsidiary with Managing Directors. "
            "Requires Certum digital signature OR wet ink signature. "
            "Must be signed by Managing Directors (Polish law requirement)."
        ),
        entity_type=EntityType.FOREIGN_SUBSIDIARY,
        signer_relationship=SignerRelationship.OFFICER,
        required_docs=[
            AuthorityDocType.BOARD_RESOLUTION,
            AuthorityDocType.OFFICER_CERTIFICATE,
        ],
        also_requires_ub_documentation=True,
        also_requires_account_owner_status=False,
        cip_matching_required=False,  # Different jurisdiction
        signer_title_required=True,  # Must be Managing Director
        additional_requirements=(
            "Signer must be Managing Director (per Polish corporate law). "
            "Must use Certum digital signature OR wet ink + certified copy. "
            "Escalate execution mechanics to Webster Legal (Jennifer Troy)."
        ),
        source="Rho DACA Process (Notion, June 16, 2026)",
        date_established="2025-09-15",
    ))

    # ============================================================================
    # PRECEDENTS (What Webster Has Actually Accepted)
    # ============================================================================

    # Precedent 1: Edward Montes — Officer (CFO), Intelligo Group USA Corp
    matrix.add_precedent(SignerPrecedent(
        precedent_id="p_intelligo_edward_montes",
        company_name="Intelligo Group USA Corp",
        signer_name="Edward Montes",
        signer_title="Officer/CFO",
        signer_relationship=SignerRelationship.OFFICER,
        entity_type=EntityType.CORPORATION,
        outcome=SigningOutcome.ACCEPTED,
        date="2026-03-24",
        signed_by_date="2026-03-24",
        authority_docs_provided=[
            AuthorityDocType.BOARD_RESOLUTION,
            AuthorityDocType.COMPLETION_CERTIFICATE,
        ],
        webster_approved=True,
        source="Gmail thread, March 24, 2026",
        notes=(
            "Initially rejected due to CIP mismatch (Edward not on account initially). "
            "Resolved via Alloy/Tracer verification + completion certificate. "
            "Final submission included full-signed version with signer name, address, "
            "and signature date documented."
        ),
    ))

    # Precedent 2: Dryden Liddle — Authorized Signatory, CIM LLC
    matrix.add_precedent(SignerPrecedent(
        precedent_id="p_cim_dryden_liddle",
        company_name="CIM LLC",
        signer_name="Dryden Liddle",
        signer_title="(Authorized Signatory)",
        signer_relationship=SignerRelationship.AUTHORIZED_REPRESENTATIVE,
        entity_type=EntityType.LLC,
        outcome=SigningOutcome.ACCEPTED,
        date="2025-04-29",
        signed_by_date="2025-04-29",
        authority_docs_provided=[
            AuthorityDocType.BOARD_RESOLUTION,
            AuthorityDocType.OFFICER_CERTIFICATE,
        ],
        webster_approved=True,
        source="DACA Summary Sheet, April 2025",
        notes="DACA Termination signed successfully. Board-authorized signatory.",
    ))

    # Precedent 3: Ruarí Phillips — Officer, Bud Financial Inc
    matrix.add_precedent(SignerPrecedent(
        precedent_id="p_bud_ruari_phillips",
        company_name="Bud Financial Inc",
        signer_name="Ruarí Phillips",
        signer_title="Officer",
        signer_relationship=SignerRelationship.OFFICER,
        entity_type=EntityType.CORPORATION,
        outcome=SigningOutcome.ACCEPTED,
        date="2026-05-21",
        signed_by_date="2026-05-21",
        authority_docs_provided=[
            AuthorityDocType.BOARD_RESOLUTION,
            AuthorityDocType.OFFICER_CERTIFICATE,
        ],
        webster_approved=True,
        source="DACA Summary Sheet, May 31, 2026",
        notes="Officer status + board resolution sufficient. No title-level requirement.",
    ))

    # Precedent 4: Edward Maslaveckas — Officer, Bud Financial Inc
    matrix.add_precedent(SignerPrecedent(
        precedent_id="p_bud_edward_maslaveckas",
        company_name="Bud Financial Inc",
        signer_name="Edward Maslaveckas",
        signer_title="Officer",
        signer_relationship=SignerRelationship.OFFICER,
        entity_type=EntityType.CORPORATION,
        outcome=SigningOutcome.ACCEPTED,
        date="2026-06-16",
        signed_by_date=None,
        authority_docs_provided=[
            AuthorityDocType.BOARD_RESOLUTION,
            AuthorityDocType.OFFICER_CERTIFICATE,
        ],
        webster_approved=True,
        source="CSHELP-6720 (June 16, 2026)",
        notes="Approved as signatory option. Board resolution on file.",
    ))

    # Precedent 5: Joseph Sciascia — Account Owner, Anonos Innovations LLC
    matrix.add_precedent(SignerPrecedent(
        precedent_id="p_anonos_joseph_sciascia",
        company_name="Anonos Innovations LLC",
        signer_name="Joseph Sciascia",
        signer_title="Account Owner",
        signer_relationship=SignerRelationship.ACCOUNT_OWNER,
        entity_type=EntityType.LLC,
        outcome=SigningOutcome.CONDITIONAL_APPROVAL,
        date="2026-06-16",
        signed_by_date=None,
        authority_docs_provided=[
            AuthorityDocType.OFFICER_CERTIFICATE,
        ],
        webster_approved=False,  # Conditional on receiving authority docs
        source="CSHELP-8871 (June 16, 2026)",
        notes=(
            "Approved IF: (1) Joseph is added as account owner on Rho platform, "
            "AND (2) corporate authority documentation provided. "
            "Also option: UBO (Ted Myerson) can sign instead."
        ),
    ))

    # Precedent 6: Ted Myerson — UBO/Account Owner, Anonos Entities & Sonona LLC
    matrix.add_precedent(SignerPrecedent(
        precedent_id="p_anonos_ted_myerson",
        company_name="Anonos Innovations LLC / Anonos Technologies LLC / Sonona LLC",
        signer_name="Ted Myerson",
        signer_title="UBO/Account Owner",
        signer_relationship=SignerRelationship.UBO,
        entity_type=EntityType.LLC,
        outcome=SigningOutcome.CONDITIONAL_APPROVAL,
        date="2026-06-16",
        signed_by_date=None,
        authority_docs_provided=[
            AuthorityDocType.OFFICER_CERTIFICATE,
        ],
        webster_approved=False,  # Subject to CSHELP-8871 compliance review
        source="CSHELP-8871 (June 16, 2026)",
        notes=(
            "UBO status sufficient authority. Compliance review pending "
            "(Josh Bobowski) on Sonona LLC signing authority and whether "
            "Joseph can sign for entities where he's NOT account owner."
        ),
    ))

    # Precedent 7: Edward Montes (Intelligo) — Initial rejection, CIP mismatch
    matrix.add_precedent(SignerPrecedent(
        precedent_id="p_intelligo_initial_rejection",
        company_name="Intelligo Group USA Corp",
        signer_name="Edward Montes",
        signer_title="Officer/CFO",
        signer_relationship=SignerRelationship.OFFICER,
        entity_type=EntityType.CORPORATION,
        outcome=SigningOutcome.REJECTED_CIP_MISMATCH,
        date="2026-03-20",
        rejection_reason=(
            "Signer could not be matched to account/CIP information. "
            "Edward not on account during initial submission."
        ),
        remediation=(
            "Resolved via: (1) Alloy/Tracer background check, (2) CIP verification "
            "showing Edward's connection to account, (3) Completion certificate with "
            "signer name, address, signature date."
        ),
        source="Gmail thread, March 24, 2026",
        notes="CIP matching is non-negotiable. External signers not permitted.",
    ))

    # Precedent 8: Signer documentation incomplete — Intelligo 2nd attempt
    matrix.add_precedent(SignerPrecedent(
        precedent_id="p_intelligo_incomplete_docs",
        company_name="Intelligo Group USA Corp",
        signer_name="Edward Montes",
        signer_title="Officer/CFO",
        signer_relationship=SignerRelationship.OFFICER,
        entity_type=EntityType.CORPORATION,
        outcome=SigningOutcome.REJECTED_INCOMPLETE_DOCS,
        date="2026-03-20",
        rejection_reason=(
            "Completion certificate lacking required fields: signer name, address, "
            "signature date not explicitly shown."
        ),
        remediation=(
            "Resubmitted completion certificate with all required fields filled in. "
            "Full-signed version provided with metadata."
        ),
        source="Gmail thread, March 24, 2026",
        notes=(
            "Completion certificate must include: full signer name, address, "
            "signature date, and title."
        ),
    ))

    # Precedent 9: Post Acute Analytics — CFO as signer, board resolution
    matrix.add_precedent(SignerPrecedent(
        precedent_id="p_post_acute_cfo",
        company_name="Post Acute Analytics Inc",
        signer_name="(CFO — name not documented)",
        signer_title="Chief Financial Officer",
        signer_relationship=SignerRelationship.OFFICER,
        entity_type=EntityType.CORPORATION,
        outcome=SigningOutcome.ACCEPTED,
        date="2026-05-28",
        signed_by_date="2026-05-28",
        authority_docs_provided=[
            AuthorityDocType.BOARD_RESOLUTION,
        ],
        webster_approved=True,
        source="Gmail thread, May 28, 2026",
        notes=(
            "Board resolution documented. DACA executed same day. "
            "General pattern: CFO preferred but not required."
        ),
    ))

    # Precedent 10: WTI Fund XI Inc (Lender) — Multiple authorized signers
    matrix.add_precedent(SignerPrecedent(
        precedent_id="p_wti_multiple_signers",
        company_name="WTI Fund XI Inc (Lender)",
        signer_name="(Multiple individuals)",
        signer_title="(Various officer titles)",
        signer_relationship=SignerRelationship.OFFICER,
        entity_type=EntityType.CORPORATION,
        outcome=SigningOutcome.ACCEPTED,
        date="2026-05-15",
        signed_by_date=None,
        authority_docs_provided=[
            AuthorityDocType.BOARD_RESOLUTION,
            AuthorityDocType.OFFICER_CERTIFICATE,
        ],
        webster_approved=True,
        source="Gmail thread, May 2026",
        notes=(
            "Multiple authorized signers permitted. Each must be individually "
            "documented. Webster Bank can designate multiple signing authorities."
        ),
    ))

    return matrix


# Build the singleton registry on import
SIGNING_AUTHORITY_MATRIX = build_signing_authority_matrix()
