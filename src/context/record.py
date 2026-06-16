"""
Core data structures for a fully-loaded DACA case record.

A CaseRecord is the required input to every agent operation.
No operation (DocuSign prep, status update, version send) may proceed
without first passing through CaseContextLoader.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class SourceType(str, Enum):
    GMAIL = "gmail"
    JIRA = "jira"
    TYPEFORM = "typeform"
    DRIVE = "drive"
    SLACK = "slack"


class DiscrepancyKind(str, Enum):
    WRONG_DOCUMENT_VERSION = "wrong_document_version"
    SIGNATORY_MISMATCH = "signatory_mismatch"
    ENTITY_NOT_IN_SCOPE = "entity_not_in_scope"
    MISSING_WB_APPROVAL = "missing_wb_approval"
    CONTACT_UNCONFIRMED = "contact_unconfirmed"
    LENDER_UNCONFIRMED = "lender_unconfirmed"


class Severity(str, Enum):
    BLOCKER = "blocker"    # Must resolve before proceeding
    WARNING = "warning"    # Surface to human; proceed only with acknowledgement
    INFO = "info"          # Log; no gate required


@dataclass
class Source:
    """A single piece of evidence — where a fact was found."""
    source_type: SourceType
    source_id: str          # thread ID, ticket key, Drive file ID, etc.
    date: datetime
    excerpt: str            # The specific text that supports the fact


@dataclass
class Entity:
    """A DACA debtor entity."""
    legal_name: str
    address: Optional[str] = None
    account_ids: list[str] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)


@dataclass
class Contact:
    name: str
    email: str
    role: str               # "debtor_signer", "debtor_counsel", "lender_rep", etc.
    title: Optional[str] = None
    phone: Optional[str] = None
    sources: list[Source] = field(default_factory=list)


@dataclass
class LenderRecord:
    legal_name: str
    address: Optional[str] = None
    contacts: list[Contact] = field(default_factory=list)
    transfer_method: Optional[str] = None
    sources: list[Source] = field(default_factory=list)


@dataclass
class DocumentRecord:
    """A document in the case — with full version history."""
    name: str
    drive_id: Optional[str]
    version_label: str          # e.g. "v1-client-redline", "v2-wb-counter-redline"
    is_wb_approved: bool
    uploaded_at: Optional[datetime]
    uploaded_by: Optional[str]
    sent_to_client: bool = False
    sent_at: Optional[datetime] = None
    sources: list[Source] = field(default_factory=list)


@dataclass
class TimelineEvent:
    """An immutable fact extracted from a source."""
    date: datetime
    actor: str                  # email address or system
    description: str
    source: Source
    tags: list[str] = field(default_factory=list)   # "redline", "escalation", "wb", etc.


@dataclass
class JiraTicket:
    key: str                    # e.g. "LEGALHELP-383"
    summary: str
    status: str
    created: datetime
    events: list[TimelineEvent] = field(default_factory=list)


@dataclass
class OpenItem:
    description: str
    owner: str                  # who must resolve it
    blocking: bool              # blocks DocuSign if True
    sources: list[Source] = field(default_factory=list)


@dataclass
class DiscrepancyFlag:
    """
    A cross-source inconsistency that requires human acknowledgement
    before the case can proceed.

    The Anonos version mixup (v1 sent to client while v2 existed in ShareFile)
    is the canonical example this flag is designed to catch.
    """
    kind: DiscrepancyKind
    severity: Severity
    description: str
    evidence: list[Source]      # Sources that reveal the inconsistency
    resolution: Optional[str] = None


@dataclass
class DocuSignReadiness:
    """Prefill completeness score for each envelope."""
    entity: Entity
    ready: bool
    missing_fields: list[str]   # Human-readable list of what's missing
    prefilled: dict              # field_name -> value for all found fields


@dataclass
class CaseRecord:
    """
    The complete evidentiary record for a DACA case.
    Constructed by CaseContextLoader before any agent operation.
    """
    case_id: str                            # Typically the primary entity name
    loaded_at: datetime
    entities: list[Entity]
    lender: Optional[LenderRecord]
    contacts: list[Contact]
    timeline: list[TimelineEvent]           # Sorted ascending by date
    documents: list[DocumentRecord]
    jira_tickets: list[JiraTicket]
    open_items: list[OpenItem]
    discrepancy_flags: list[DiscrepancyFlag]
    docusign_readiness: list[DocuSignReadiness] = field(default_factory=list)

    @property
    def blockers(self) -> list[DiscrepancyFlag]:
        return [f for f in self.discrepancy_flags if f.severity == Severity.BLOCKER]

    @property
    def is_docusign_ready(self) -> bool:
        """True only when no blockers exist and all envelopes have no missing fields."""
        if self.blockers:
            return False
        return all(r.ready for r in self.docusign_readiness)

    def summary(self) -> str:
        lines = [
            f"Case: {self.case_id}",
            f"Entities ({len(self.entities)}): {', '.join(e.legal_name for e in self.entities)}",
            f"Lender: {self.lender.legal_name if self.lender else 'UNKNOWN'}",
            f"Timeline events: {len(self.timeline)}",
            f"Documents: {len(self.documents)}",
            f"Jira tickets: {[t.key for t in self.jira_tickets]}",
            f"Open items: {len(self.open_items)} ({sum(1 for i in self.open_items if i.blocking)} blocking)",
            f"Discrepancy flags: {len(self.discrepancy_flags)} "
            f"({len(self.blockers)} blockers)",
            f"DocuSign ready: {self.is_docusign_ready}",
        ]
        if self.blockers:
            lines.append("BLOCKERS:")
            for b in self.blockers:
                lines.append(f"  [{b.kind.value}] {b.description}")
        return "\n".join(lines)
