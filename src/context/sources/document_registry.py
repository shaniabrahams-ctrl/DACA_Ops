"""
Document Registry

Tracks provenance of every document that enters or leaves the DACA workflow.
Every document is registered with:
  - Who produced/submitted it (client, WB, Rho legal, Rho ops)
  - How it arrived (email attachment, ShareFile, Drive upload, DocuSign)
  - Content fingerprint for comparison
  - Version label relative to the negotiation lifecycle

This is the source of truth the Document Version Agent queries.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class DocumentProvenance(str, Enum):
    CLIENT_SUBMITTED = "client_submitted"       # Came from the debtor or their counsel
    WB_APPROVED = "wb_approved"                 # Uploaded/confirmed by Webster Bank legal
    RHO_LEGAL_DRAFT = "rho_legal_draft"         # Produced by Rho's internal legal team
    RHO_OPS_WORKING = "rho_ops_working"         # Working copy in Rho ops workflow
    EXECUTION_COPY = "execution_copy"            # Final signed version


class DocumentChannel(str, Enum):
    EMAIL_ATTACHMENT = "email_attachment"
    SHAREFILE = "sharefile"
    GOOGLE_DRIVE = "google_drive"
    DOCUSIGN = "docusign"
    MANUAL_UPLOAD = "manual_upload"


@dataclass
class DocumentFingerprint:
    """
    Content signature for a document — used to detect when two differently-named
    files are substantively the same (the Anonos failure mode).

    sha256_hex: exact byte hash — catches identical files regardless of name
    normalized_text_hash: hash of whitespace-normalized extracted text —
        catches files that differ only in formatting, metadata, or authoring info
    revision_author_set: set of {author} strings from Word tracked-changes markup —
        if two docs have the same revision authors, they likely share the same origin
    change_count: number of tracked changes (insertions + deletions) —
        a WB counter-redline will have MORE changes than the client's original
    """
    sha256_hex: str
    normalized_text_hash: str
    revision_author_set: frozenset
    change_count: int

    def is_byte_identical(self, other: "DocumentFingerprint") -> bool:
        return self.sha256_hex == other.sha256_hex

    def is_content_equivalent(self, other: "DocumentFingerprint") -> bool:
        """True if substantive text is the same even if bytes differ."""
        return self.normalized_text_hash == other.normalized_text_hash

    def similarity_score(self, other: "DocumentFingerprint") -> float:
        """
        0.0 = completely different, 1.0 = identical
        Used to catch near-identical documents (e.g., same content, different filename).
        """
        score = 0.0
        if self.sha256_hex == other.sha256_hex:
            return 1.0
        if self.normalized_text_hash == other.normalized_text_hash:
            score += 0.7
        shared_authors = self.revision_author_set & other.revision_author_set
        if self.revision_author_set and shared_authors:
            score += 0.2 * (len(shared_authors) / max(len(self.revision_author_set), 1))
        if self.change_count == other.change_count:
            score += 0.1
        return min(score, 1.0)


@dataclass
class RegisteredDocument:
    """A document registered in the provenance store."""
    doc_id: str                         # Stable ID (Drive file ID or computed hash)
    case_id: str
    name: str
    provenance: DocumentProvenance
    channel: DocumentChannel
    registered_at: datetime
    submitted_by: str                   # Email of the person who sent/uploaded it
    fingerprint: Optional[DocumentFingerprint]
    drive_id: Optional[str] = None
    gmail_thread_id: Optional[str] = None
    gmail_message_id: Optional[str] = None
    version_label: Optional[str] = None
    notes: str = ""

    @property
    def is_client_origin(self) -> bool:
        return self.provenance == DocumentProvenance.CLIENT_SUBMITTED

    @property
    def is_wb_origin(self) -> bool:
        return self.provenance == DocumentProvenance.WB_APPROVED


class DocumentRegistry:
    """
    In-memory registry for a case session.
    In production, backed by a persistent store (Postgres).
    """

    def __init__(self, case_id: str):
        self.case_id = case_id
        self._docs: list[RegisteredDocument] = []

    def register(self, doc: RegisteredDocument) -> None:
        self._docs.append(doc)

    def get_by_provenance(self, provenance: DocumentProvenance) -> list[RegisteredDocument]:
        return [d for d in self._docs if d.provenance == provenance]

    def get_wb_approved(self) -> list[RegisteredDocument]:
        return self.get_by_provenance(DocumentProvenance.WB_APPROVED)

    def get_client_submitted(self) -> list[RegisteredDocument]:
        return self.get_by_provenance(DocumentProvenance.CLIENT_SUBMITTED)

    def find_similar(
        self,
        fingerprint: DocumentFingerprint,
        threshold: float = 0.7,
    ) -> list[tuple[RegisteredDocument, float]]:
        """
        Find all registered documents that are similar to the given fingerprint.
        Returns (doc, similarity_score) pairs above threshold, sorted by score desc.
        """
        results = []
        for doc in self._docs:
            if not doc.fingerprint:
                continue
            score = fingerprint.similarity_score(doc.fingerprint)
            if score >= threshold:
                results.append((doc, score))
        return sorted(results, key=lambda x: x[1], reverse=True)

    def get_latest_wb_approved(self) -> Optional[RegisteredDocument]:
        wb_docs = self.get_wb_approved()
        if not wb_docs:
            return None
        return max(wb_docs, key=lambda d: d.registered_at)

    def summary(self) -> str:
        lines = [f"Document Registry — {self.case_id} ({len(self._docs)} documents)"]
        for doc in sorted(self._docs, key=lambda d: d.registered_at):
            lines.append(
                f"  [{doc.provenance.value}] {doc.name} "
                f"— submitted by {doc.submitted_by} at {doc.registered_at.strftime('%Y-%m-%d %H:%M')} "
                f"via {doc.channel.value}"
            )
        return "\n".join(lines)
