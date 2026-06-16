"""
Document Version Agent

Monitors every document that enters or exits the DACA workflow and
raises flags before a wrong version can reach the client.

WHAT IT CATCHES (grounded in the Anonos post-mortem):

  The specific failure:
    1. Client submitted their redline markup (v1) via email attachment
    2. WB uploaded their counter-redline (v2) to ShareFile
    3. Sam downloaded v1 (their own upload) from ShareFile, not v2
    4. Shani forwarded v1 to the client via email
    5. Client negotiated Section 6(b) for 4 days against their own version

  The content signal that would have caught it:
    - v1 had revision authors: client/client-counsel
    - v2 had revision authors: Jenifer Troy (Webster Bank)
    - The doc Shani sent had NO Webster-authored revisions
    - Any document sent to the client that lacks WB revision authors
      and matches a client-submitted document = BLOCKED

TRIGGER POINTS:
  register_inbound()  — call when any document arrives (email, ShareFile, Drive)
  check_outbound()    — call before any document is sent to any external party
  scan_drive_folder() — periodic scan of the case Drive folder to catch
                        version drift without waiting for a send event

INTEGRATION WITH HARNESS:
  The harness calls check_outbound() as a precondition before DocuSign
  prep and before any email with an attachment is sent to the client.
  check_outbound() raising VersionConflictError is a hard block.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from src.context.sources.document_registry import (
    DocumentRegistry, RegisteredDocument, DocumentProvenance,
    DocumentChannel, DocumentFingerprint,
)
from src.context.analysis.document_diff import (
    fingerprint_docx_bytes, compare_documents,
)


class VersionFlag(str, Enum):
    SENDING_CLIENT_VERSION_BACK = "sending_client_version_back"
    NO_WB_AUTHORS_IN_OUTBOUND = "no_wb_authors_in_outbound"
    NEWER_WB_VERSION_EXISTS = "newer_wb_version_exists"
    OUTBOUND_MATCHES_CLIENT_SUBMITTED = "outbound_matches_client_submitted"
    UNKNOWN_PROVENANCE = "unknown_provenance"


@dataclass
class VersionCheckResult:
    approved: bool
    flags: list[VersionFlag]
    explanation: str
    recommended_document: Optional[RegisteredDocument]
    comparison_details: Optional[dict]


class VersionConflictError(Exception):
    """Raised by check_outbound when a hard block is triggered."""
    def __init__(self, result: VersionCheckResult):
        self.result = result
        super().__init__(result.explanation)


class DocumentVersionAgent:
    """
    Stateful agent that maintains a DocumentRegistry per case
    and enforces version integrity for all document movements.
    """

    # Known Webster Bank email domains and author name patterns
    WB_AUTHOR_PATTERNS = ["websterbank.com", "webster bank", "jenifer troy",
                          "jennifer troy", "stoliveira", "hsabank"]

    # Similarity threshold above which two documents are considered "the same"
    SIMILARITY_THRESHOLD = 0.70

    def __init__(self, case_id: str):
        self.case_id = case_id
        self.registry = DocumentRegistry(case_id)

    def register_inbound(
        self,
        name: str,
        file_bytes: bytes,
        submitted_by: str,
        channel: DocumentChannel,
        gmail_thread_id: Optional[str] = None,
        gmail_message_id: Optional[str] = None,
        drive_id: Optional[str] = None,
        explicit_provenance: Optional[DocumentProvenance] = None,
    ) -> RegisteredDocument:
        """
        Register a document that arrived from an external party.
        Provenance is inferred from submitter email if not explicitly provided.

        Call this whenever:
        - An email arrives with a DACA document attached
        - A ShareFile activity notification reports an upload
        - A Drive file appears in the case folder from an external party
        """
        provenance = explicit_provenance or self._infer_provenance(submitted_by, name, file_bytes)
        fingerprint = fingerprint_docx_bytes(file_bytes) if file_bytes else None

        doc = RegisteredDocument(
            doc_id=drive_id or (fingerprint.sha256_hex[:16] if fingerprint else name),
            case_id=self.case_id,
            name=name,
            provenance=provenance,
            channel=channel,
            registered_at=datetime.now(timezone.utc),
            submitted_by=submitted_by,
            fingerprint=fingerprint,
            drive_id=drive_id,
            gmail_thread_id=gmail_thread_id,
            gmail_message_id=gmail_message_id,
        )
        self.registry.register(doc)
        return doc

    def check_outbound(
        self,
        name: str,
        file_bytes: bytes,
        sending_to: str,
        channel: DocumentChannel = DocumentChannel.EMAIL_ATTACHMENT,
    ) -> VersionCheckResult:
        """
        Validate a document before it is sent to an external party.

        Raises VersionConflictError on hard blocks.
        Returns VersionCheckResult.approved=True only when all checks pass.

        Checks (in order):
        1. Byte-identical to a client-submitted document → BLOCK
        2. No WB-authored revisions, but a WB-approved version exists → BLOCK
        3. Newer WB-approved version registered after this one → BLOCK
        4. Similarity >= threshold to a client-submitted document → BLOCK
        5. Unknown provenance (not registered) → WARNING
        """
        outbound_fp = fingerprint_docx_bytes(file_bytes)
        if not outbound_fp:
            result = VersionCheckResult(
                approved=False,
                flags=[VersionFlag.UNKNOWN_PROVENANCE],
                explanation=f"Could not parse '{name}' as a DOCX file. Do not send unverified documents.",
                recommended_document=self.registry.get_latest_wb_approved(),
                comparison_details=None,
            )
            raise VersionConflictError(result)

        flags: list[VersionFlag] = []
        comparison_details = {}

        # --- Check 1 & 4: Compare against all client-submitted documents ---
        client_docs = self.registry.get_client_submitted()
        for client_doc in client_docs:
            if not client_doc.fingerprint:
                continue
            if outbound_fp.is_byte_identical(client_doc.fingerprint):
                flags.append(VersionFlag.SENDING_CLIENT_VERSION_BACK)
                comparison_details["matched_client_doc"] = client_doc.name
                comparison_details["match_type"] = "byte_identical"
                break
            elif outbound_fp.is_content_equivalent(client_doc.fingerprint):
                flags.append(VersionFlag.OUTBOUND_MATCHES_CLIENT_SUBMITTED)
                comparison_details["matched_client_doc"] = client_doc.name
                comparison_details["match_type"] = "content_equivalent"
                break
            elif outbound_fp.similarity_score(client_doc.fingerprint) >= self.SIMILARITY_THRESHOLD:
                score = outbound_fp.similarity_score(client_doc.fingerprint)
                flags.append(VersionFlag.OUTBOUND_MATCHES_CLIENT_SUBMITTED)
                comparison_details["matched_client_doc"] = client_doc.name
                comparison_details["match_type"] = f"high_similarity_{score:.0%}"
                break

        # --- Check 2: Outbound has no WB revision authors but WB doc exists ---
        wb_docs = self.registry.get_wb_approved()
        if wb_docs and not self._has_wb_authors(outbound_fp):
            flags.append(VersionFlag.NO_WB_AUTHORS_IN_OUTBOUND)
            comparison_details["wb_docs_available"] = [d.name for d in wb_docs]
            comparison_details["outbound_revision_authors"] = list(outbound_fp.revision_author_set)

        # --- Check 3: Newer WB version registered after this document ---
        if wb_docs:
            latest_wb = max(wb_docs, key=lambda d: d.registered_at)
            outbound_registered = self._find_in_registry(outbound_fp)
            if outbound_registered and outbound_registered.registered_at < latest_wb.registered_at:
                flags.append(VersionFlag.NEWER_WB_VERSION_EXISTS)
                comparison_details["newer_wb_doc"] = latest_wb.name
                comparison_details["newer_wb_registered_at"] = latest_wb.registered_at.isoformat()

        if not flags:
            return VersionCheckResult(
                approved=True,
                flags=[],
                explanation=f"'{name}' passed all version checks. Safe to send.",
                recommended_document=None,
                comparison_details=comparison_details,
            )

        # Build explanation from flags
        explanation = self._build_explanation(name, flags, comparison_details)
        recommended = self.registry.get_latest_wb_approved()

        result = VersionCheckResult(
            approved=False,
            flags=flags,
            explanation=explanation,
            recommended_document=recommended,
            comparison_details=comparison_details,
        )
        raise VersionConflictError(result)

    def scan_and_classify_drive_folder(
        self, drive_files: list[dict]
    ) -> list[RegisteredDocument]:
        """
        Scan a list of Drive file metadata dicts and register any
        unregistered documents with inferred provenance.

        Run this when the case context is first loaded to ensure the
        registry is populated before any outbound check is needed.

        drive_files: list of Drive file metadata dicts from Google Drive API
        """
        registered = []
        known_ids = {d.drive_id for d in self.registry._docs if d.drive_id}

        for file_meta in drive_files:
            drive_id = file_meta.get("id")
            if drive_id in known_ids:
                continue
            name = file_meta.get("name", "")
            modifier = file_meta.get("lastModifyingUser", {}).get("emailAddress", "unknown")
            provenance = self._infer_provenance_from_name(name, modifier)
            doc = RegisteredDocument(
                doc_id=drive_id or name,
                case_id=self.case_id,
                name=name,
                provenance=provenance,
                channel=DocumentChannel.GOOGLE_DRIVE,
                registered_at=datetime.now(timezone.utc),
                submitted_by=modifier,
                fingerprint=None,     # Set when file bytes are available
                drive_id=drive_id,
            )
            self.registry.register(doc)
            registered.append(doc)
        return registered

    def register_wb_sharefile_upload(
        self,
        name: str,
        uploaded_by: str,
        drive_id: Optional[str] = None,
        gmail_thread_id: Optional[str] = None,
        file_bytes: Optional[bytes] = None,
    ) -> RegisteredDocument:
        """
        Convenience method for registering WB documents uploaded via ShareFile.
        Always sets provenance to WB_APPROVED.

        Call this when a ShareFile activity notification email arrives
        showing a WB upload — so the registry knows a WB version exists
        before anyone downloads anything.
        """
        return self.register_inbound(
            name=name,
            file_bytes=file_bytes or b"",
            submitted_by=uploaded_by,
            channel=DocumentChannel.SHAREFILE,
            gmail_thread_id=gmail_thread_id,
            drive_id=drive_id,
            explicit_provenance=DocumentProvenance.WB_APPROVED,
        )

    def _infer_provenance(
        self, submitted_by: str, name: str, file_bytes: bytes
    ) -> DocumentProvenance:
        """
        Infer document provenance from:
        1. Submitter email domain
        2. Document filename conventions
        3. Revision author metadata in the DOCX
        """
        # Check submitter domain first
        submitter_lower = submitted_by.lower()
        if any(p in submitter_lower for p in self.WB_AUTHOR_PATTERNS):
            return DocumentProvenance.WB_APPROVED
        if "rho.co" in submitter_lower:
            return DocumentProvenance.RHO_LEGAL_DRAFT

        # Check filename conventions
        name_lower = name.lower()
        if any(p in name_lower for p in ["wb redline", "wb revision", "webster revision"]):
            return DocumentProvenance.WB_APPROVED
        if "execution" in name_lower or "executed" in name_lower or "signed" in name_lower:
            return DocumentProvenance.EXECUTION_COPY

        # Check revision authors in document
        if file_bytes:
            fp = fingerprint_docx_bytes(file_bytes)
            if fp and self._has_wb_authors(fp):
                return DocumentProvenance.WB_APPROVED

        # Default: assume client-submitted if came from external party
        return DocumentProvenance.CLIENT_SUBMITTED

    def _infer_provenance_from_name(self, name: str, modifier: str) -> DocumentProvenance:
        """Simpler version for Drive scan (no file bytes available)."""
        return self._infer_provenance(modifier, name, b"")

    def _has_wb_authors(self, fp: DocumentFingerprint) -> bool:
        """Returns True if any WB-pattern author appears in revision marks."""
        for author in fp.revision_author_set:
            if any(p in author.lower() for p in self.WB_AUTHOR_PATTERNS):
                return True
        return False

    def _find_in_registry(self, fp: DocumentFingerprint) -> Optional[RegisteredDocument]:
        """Find the registry entry matching this fingerprint."""
        for doc in self.registry._docs:
            if doc.fingerprint and doc.fingerprint.sha256_hex == fp.sha256_hex:
                return doc
        return None

    def _build_explanation(
        self, name: str, flags: list[VersionFlag], details: dict
    ) -> str:
        parts = [f"VERSION CHECK BLOCKED for '{name}':"]

        if VersionFlag.SENDING_CLIENT_VERSION_BACK in flags:
            matched = details.get("matched_client_doc", "a client-submitted document")
            parts.append(
                f"  [CRITICAL] This document is byte-identical to '{matched}', "
                "which was submitted by the client. You are about to send the client "
                "their own version back — not Rho's or Webster's counter-position. "
                "This is the exact failure that caused 2 weeks of delay on the Anonos case."
            )

        if VersionFlag.OUTBOUND_MATCHES_CLIENT_SUBMITTED in flags:
            matched = details.get("matched_client_doc", "a client-submitted document")
            match_type = details.get("match_type", "similar content")
            parts.append(
                f"  [CRITICAL] This document is {match_type} to '{matched}', "
                "which was submitted by the client. Sending this would give the client "
                "their own redline back, not a counter-redline."
            )

        if VersionFlag.NO_WB_AUTHORS_IN_OUTBOUND in flags:
            authors = details.get("outbound_revision_authors", [])
            wb_available = details.get("wb_docs_available", [])
            parts.append(
                f"  [BLOCK] The outbound document has no Webster Bank revision authors "
                f"(found: {authors or 'none'}). "
                f"WB-approved document(s) exist in the registry: {wb_available}. "
                "Send the WB-approved version instead."
            )

        if VersionFlag.NEWER_WB_VERSION_EXISTS in flags:
            newer = details.get("newer_wb_doc", "unknown")
            registered_at = details.get("newer_wb_registered_at", "unknown time")
            parts.append(
                f"  [BLOCK] A newer WB-approved version '{newer}' was registered "
                f"at {registered_at} — after the outbound document. "
                "Send the newer version."
            )

        return "\n".join(parts)
