"""
DACA Compliance Module

Centralizes all compliance rules, validation, and signatory authority documentation
that governs DACA agreement execution.
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
from src.compliance.signing_authority_rules import SIGNING_AUTHORITY_MATRIX

__all__ = [
    "SigningAuthorityMatrix",
    "SigningAuthorityRule",
    "SignerPrecedent",
    "SignerRelationship",
    "AuthorityDocType",
    "EntityType",
    "SigningOutcome",
    "SIGNING_AUTHORITY_MATRIX",
]
