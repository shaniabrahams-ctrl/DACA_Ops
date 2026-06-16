"""
Document content extraction and comparison for DOCX files.

Provides the fingerprinting logic used by the Document Version Agent.
Works on raw .docx bytes — files retrieved from Gmail attachments,
Google Drive, or ShareFile.

DOCX files are ZIP archives containing XML. The relevant files:
  word/document.xml       — body text, paragraphs, runs
  word/revisions.xml      — tracked changes (if present)
  word/comments.xml       — reviewer comments

Tracked changes in DOCX:
  <w:ins> tags = insertions (author, date, text added)
  <w:del> tags = deletions (author, date, text removed)
  w:author attribute on revision marks identifies who made each change

The Anonos check: the document Shani sent had revision marks authored
by "Joseph Sciascia" (or Anonos counsel) — the same as the client-submitted
version. A WB counter-redline would have revision marks authored by
"Jenifer Troy" or "Webster Bank". Comparing revision author sets is
a strong signal for provenance mismatch.
"""

from __future__ import annotations
import hashlib
import io
import re
import zipfile
from typing import Optional

from src.context.sources.document_registry import DocumentFingerprint


def fingerprint_docx_bytes(file_bytes: bytes) -> Optional[DocumentFingerprint]:
    """
    Compute the full DocumentFingerprint from raw .docx bytes.
    Returns None if the bytes are not a valid DOCX file.
    """
    try:
        sha256 = hashlib.sha256(file_bytes).hexdigest()
        body_text = _extract_body_text(file_bytes)
        normalized_text = _normalize_text(body_text)
        normalized_hash = hashlib.sha256(normalized_text.encode()).hexdigest()
        revision_authors, change_count = _extract_revision_metadata(file_bytes)
        return DocumentFingerprint(
            sha256_hex=sha256,
            normalized_text_hash=normalized_hash,
            revision_author_set=frozenset(revision_authors),
            change_count=change_count,
        )
    except Exception:
        return None


def _extract_body_text(file_bytes: bytes) -> str:
    """Extract plain text from document.xml body, stripping all XML tags."""
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
            if "word/document.xml" not in zf.namelist():
                return ""
            xml_bytes = zf.read("word/document.xml")
        xml_str = xml_bytes.decode("utf-8", errors="replace")
        # Strip all XML tags — what remains is the textual content
        text = re.sub(r"<[^>]+>", " ", xml_str)
        return text
    except Exception:
        return ""


def _normalize_text(text: str) -> str:
    """
    Normalize text for content-equivalence comparison.
    Removes whitespace variation, metadata noise, and formatting artifacts.
    """
    # Collapse all whitespace to single spaces
    text = re.sub(r"\s+", " ", text)
    # Remove common boilerplate that varies between copies
    text = re.sub(r"Banking services provided.*?account\.", "", text, flags=re.DOTALL)
    text = re.sub(r"Sent via Superhuman.*", "", text)
    return text.strip().lower()


def _extract_revision_metadata(file_bytes: bytes) -> tuple[list[str], int]:
    """
    Extract tracked-change author names and total change count from a DOCX.

    Returns (authors, change_count) where:
    - authors: list of unique author names from w:ins and w:del elements
    - change_count: total number of tracked insertions + deletions

    This is the strongest provenance signal:
    - Client-submitted redlines: authors are the client or their counsel
    - WB counter-redlines: authors are Webster Bank staff
    - Sending a document where all revision authors are the client = sending their version back
    """
    authors: list[str] = []
    change_count = 0

    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
            for filename in ["word/document.xml", "word/revisions.xml"]:
                if filename not in zf.namelist():
                    continue
                xml_str = zf.read(filename).decode("utf-8", errors="replace")

                # Find all tracked-change authors
                # DOCX format: <w:ins w:author="Name" ...> or <w:del w:author="Name" ...>
                found_authors = re.findall(
                    r'<w:(?:ins|del)[^>]+w:author="([^"]+)"', xml_str
                )
                authors.extend(found_authors)
                change_count += len(found_authors)

    except Exception:
        pass

    return list(set(authors)), change_count


def compare_documents(
    doc_a_bytes: bytes,
    doc_b_bytes: bytes,
) -> dict:
    """
    Compare two DOCX files and return a structured comparison result.

    Returns:
    {
        "byte_identical": bool,
        "content_equivalent": bool,
        "similarity_score": float,
        "shared_revision_authors": list[str],
        "doc_a_only_authors": list[str],
        "doc_b_only_authors": list[str],
        "doc_a_change_count": int,
        "doc_b_change_count": int,
        "assessment": str  # Human-readable summary
    }
    """
    fp_a = fingerprint_docx_bytes(doc_a_bytes)
    fp_b = fingerprint_docx_bytes(doc_b_bytes)

    if fp_a is None or fp_b is None:
        return {"error": "Could not parse one or both documents as DOCX"}

    shared_authors = list(fp_a.revision_author_set & fp_b.revision_author_set)
    a_only = list(fp_a.revision_author_set - fp_b.revision_author_set)
    b_only = list(fp_b.revision_author_set - fp_a.revision_author_set)
    score = fp_a.similarity_score(fp_b)

    assessment = _assess_comparison(fp_a, fp_b, score, shared_authors, a_only, b_only)

    return {
        "byte_identical": fp_a.is_byte_identical(fp_b),
        "content_equivalent": fp_a.is_content_equivalent(fp_b),
        "similarity_score": round(score, 3),
        "shared_revision_authors": shared_authors,
        "doc_a_only_authors": a_only,
        "doc_b_only_authors": b_only,
        "doc_a_change_count": fp_a.change_count,
        "doc_b_change_count": fp_b.change_count,
        "assessment": assessment,
    }


def _assess_comparison(fp_a, fp_b, score, shared, a_only, b_only) -> str:
    if fp_a.is_byte_identical(fp_b):
        return "IDENTICAL: These are the same file."

    if fp_a.is_content_equivalent(fp_b):
        return (
            "CONTENT EQUIVALENT: Different files but substantively identical text. "
            "Likely the same document saved under a different name or with metadata changes."
        )

    if score >= 0.7:
        if not b_only and shared:
            return (
                f"HIGH SIMILARITY ({score:.0%}): Document B contains no new revision authors beyond "
                f"what Document A already has ({shared}). "
                "Document B may be the same as or derived from Document A — "
                "not an independent counter-redline."
            )
        if b_only:
            return (
                f"HIGH SIMILARITY ({score:.0%}) but Document B has additional revision authors "
                f"({b_only}) not present in Document A. "
                "This is consistent with Document B being a counter-redline on top of Document A."
            )

    if score < 0.3:
        return f"LOW SIMILARITY ({score:.0%}): Documents appear substantially different."

    return f"MODERATE SIMILARITY ({score:.0%}): Manual review recommended."
