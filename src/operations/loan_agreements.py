"""
Loan-agreement intake: pull the uploaded loan agreement from a Typeform response
and file it into the case's Google Drive folder.

WHAT / WHY: the DACA application Typeform has a "Please upload your loan agreement"
field. The uploaded file lives behind a private Typeform URL
(`https://api.typeform.com/responses/files/<hash>/<name>`), which is only
retrievable with a Typeform API token. This module follows that link, downloads
the document, and files it into the borrower's client folder in Drive
(`DACAs {year}/{Business ID} - {Business Name}`), leaving a receipt on the case.

DISCIPLINE:
  - No inference (Gumloop lessons; daca-doc-currency / no-infer rule). Only a real
    Typeform file URL is acted on. Every other cell value — "Uploaded", "Skip",
    "n/a", a SendSafely dropzone link, free text, or empty — is SKIPPED with an
    explicit reason, never guessed into a download.
  - View, don't store (daca-data-security skill). Loan agreements are RESTRICTED-tier
    (compliance) content. The bytes are fetched transiently and streamed straight to
    Drive (the system of record); they are NEVER written to git or the register DB,
    and NEVER sent to the model. The register keeps only a sha256 fingerprint + the
    Drive link (the `documents` table), exactly like attachment_scanner's pattern.
  - Idempotent + receipted. Re-running does not re-upload (skips when a file of the
    same name already sits in the folder, and the documents row is unique on sha256)
    and every filing appends a `document_received` event with the Drive link as
    evidence.
  - Human gate. Filing a document is an internal, reversible action, so it is
    automated — but an UNMATCHED response (no register case / no client folder) is
    filed into a holding location and FLAGGED for a human, never silently dropped
    and never used to auto-advance a case's stage.

DECOUPLING (same shape as the register syncs and R12): this module takes already-
fetched response rows and injected `typeform` / `drive` clients. The agent can feed
real data with the live connectors; a Rhollout job feeds the same shape with service
credentials. Only the clients differ — the parse/match/idempotency/receipt logic
lives here.
"""

from __future__ import annotations
import hashlib
import re
from dataclasses import dataclass, field
from typing import Optional, Protocol

from src.register.db import Register, Case
from src.register.lifecycle import LifecycleStage, ControlState
from src.register.sync_salesforce import normalize_name

# A Typeform response-file URL. Only these are downloadable documents.
TYPEFORM_FILE_RE = re.compile(r"https://api\.typeform\.com/responses/files/\S+")

# Header-name fragments (lowercased) used to locate columns across BOTH form
# schemas present in the responses sheet (an older and a newer layout).
_H_BORROWER_NAME = ("legal business name", "legal entity name for the borrower")
_H_BORROWER_EMAIL = ("business contact email", "email for the borrower's contact")
_H_UPLOAD = ("upload your loan agreement", "upload a pdf file of the loan agreement")
_H_TOKEN = ("token",)


# ── Parsing the responses sheet ───────────────────────────────────────────────

def _clean(cell: str) -> str:
    """Undo the markdown escaping the Drive export adds (\\_, \\#, \\&, \\|, \\+)."""
    return re.sub(r"\\([_#&|+])", r"\1", (cell or "").strip())


def _find_col(headers: list[str], fragments: tuple[str, ...]) -> Optional[int]:
    for i, h in enumerate(headers):
        hl = h.lower()
        if any(f in hl for f in fragments):
            return i
    return None


def parse_responses(content: str) -> list[dict]:
    """
    Header-driven parse of the Typeform responses sheet. The sheet contains more
    than one table (different form versions); each has its own header row that we
    detect by the presence of a "Token" column. Columns are located by header NAME,
    not fixed index, so both layouts work.

    Returns one dict per data row with: borrower_name, borrower_email,
    upload_cell (raw), token. Rows with no token are ignored (spacer rows).
    """
    rows: list[dict] = []
    cols: Optional[dict] = None
    for line in content.splitlines():
        if not line.lstrip().startswith("|"):
            cols = None
            continue
        cells = [_clean(c) for c in line.split("|")]
        # markdown tables have leading/trailing empty cells from the outer pipes
        if len(cells) >= 3 and set("".join(cells[1:-1]).replace(":", "").replace("-", "")) == set():
            continue  # alignment row (:-: :-: ...)
        # header row: contains a "Token" column and an upload column
        low = [c.lower() for c in cells]
        is_header = any("token" in c for c in low) and any(
            any(f in c for f in _H_UPLOAD) for c in low)
        if is_header:
            cols = {
                "name": _find_col(cells, _H_BORROWER_NAME),
                "email": _find_col(cells, _H_BORROWER_EMAIL),
                "upload": _find_col(cells, _H_UPLOAD),
                "token": _find_col(cells, _H_TOKEN),
            }
            continue
        if not cols or cols["upload"] is None or cols["token"] is None:
            continue

        def _at(key):
            idx = cols[key]
            return cells[idx] if idx is not None and idx < len(cells) else ""

        token = _at("token")
        if not token:
            continue  # spacer / empty row
        rows.append({
            "borrower_name": _at("name"),
            "borrower_email": _at("email"),
            "upload_cell": _at("upload"),
            "token": token,
        })
    return rows


def extract_file_url(upload_cell: str) -> Optional[str]:
    """Return the Typeform file URL if the cell holds one, else None."""
    m = TYPEFORM_FILE_RE.search(upload_cell or "")
    return m.group(0).rstrip(".,);]") if m else None


def skip_reason(upload_cell: str) -> str:
    """Human-readable reason a non-URL upload cell is not actionable."""
    v = (upload_cell or "").strip()
    if not v:
        return "no upload provided (blank)"
    if "sendsafely" in v.lower():
        return "points to the SendSafely dropzone, not a Typeform file — fetch manually"
    return f"no downloadable file link (cell text: {v[:60]!r})"


# ── Client protocols (injected; concrete impls in src/integrations) ───────────

class TypeformClient(Protocol):
    def download(self, url: str) -> tuple[str, str, bytes]:
        """Return (filename, content_type, data) for a Typeform response-file URL."""
        ...


class DriveWriter(Protocol):
    def find_or_create_client_folder(self, business_id: Optional[str], entity_name: str,
                                     matched: bool, create_missing: bool
                                     ) -> tuple[Optional[str], str, bool]:
        """Return (folder_id, folder_name, created). folder_id is None if the folder
        is absent and create_missing is False."""
        ...

    def list_filenames(self, folder_id: str) -> set[str]:
        ...

    def upload(self, folder_id: str, filename: str, content_type: str, data: bytes) -> str:
        """Upload bytes; return a shareable Drive link."""
        ...


# ── Matching a response to a register case ────────────────────────────────────

def match_case(reg: Register, borrower_name: str) -> Optional[Case]:
    """Match by normalized legal name (same normalization the Salesforce sync uses).
    Returns the case or None — an ambiguous/absent match is treated as unmatched
    (never guessed)."""
    target = normalize_name(borrower_name)
    if not target:
        return None
    hits = [c for c in reg.all_cases() if normalize_name(c.entity_legal_name) == target]
    return hits[0] if len(hits) == 1 else None


def _unmatched_case_id(borrower_name: str) -> str:
    slug = "".join(ch for ch in borrower_name.upper() if ch.isalnum())[:20]
    return f"NEW-{slug}" if slug else "NEW-UNKNOWN"


# ── Result model ──────────────────────────────────────────────────────────────

@dataclass
class FilingResult:
    filed: list[dict] = field(default_factory=list)       # {token, case_id, filename, link, matched}
    skipped: list[dict] = field(default_factory=list)     # {token, borrower, reason}
    already: list[dict] = field(default_factory=list)     # {token, case_id, filename}
    flagged: list[dict] = field(default_factory=list)     # {token, case_id, reason}
    errors: list[dict] = field(default_factory=list)      # {token, borrower, error}

    def summary(self) -> dict:
        return {"filed": len(self.filed), "skipped": len(self.skipped),
                "already_filed": len(self.already), "flagged": len(self.flagged),
                "errors": len(self.errors)}


# ── Core operation ────────────────────────────────────────────────────────────

def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def process_one(reg: Register, resp: dict, typeform: TypeformClient, drive: DriveWriter,
                now_iso: str, create_missing: bool = True,
                result: Optional[FilingResult] = None) -> FilingResult:
    """
    File the loan agreement for a single Typeform response. Safe to call per-submission
    (the going-forward path: intake / R12 webhook) or in a loop (backfill).
    """
    result = result or FilingResult()
    token = resp.get("token", "")
    borrower = resp.get("borrower_name", "")

    url = extract_file_url(resp.get("upload_cell", ""))
    if not url:
        result.skipped.append({"token": token, "borrower": borrower,
                               "reason": skip_reason(resp.get("upload_cell", ""))})
        return result

    case = match_case(reg, borrower)
    matched = case is not None
    business_id = case.business_id if case else None
    entity_name = case.entity_legal_name if case else borrower

    try:
        folder_id, folder_name, created = drive.find_or_create_client_folder(
            business_id, entity_name, matched, create_missing)
    except Exception as e:  # drive resolution failure — surface, don't crash the batch
        result.errors.append({"token": token, "borrower": borrower, "error": f"folder: {e}"})
        return result

    if folder_id is None:
        result.flagged.append({"token": token, "case_id": (case.case_id if case else None),
                               "reason": f"no client folder for {entity_name!r} and create_missing=False"})
        return result

    # Ensure there is a case to attach the receipt to. An unmatched response is a
    # genuine intake we must not drop: create a net-new case (application_received),
    # flagged for human reconciliation. Never auto-advance an existing case's stage.
    if not matched:
        case_id = _unmatched_case_id(borrower)
        existing = reg.get_case(case_id)
        if existing is None:
            reg.upsert_case(Case(case_id=case_id, entity_legal_name=borrower or "(unknown borrower)",
                                 lifecycle_stage=LifecycleStage.APPLICATION_RECEIVED.value,
                                 control_state=ControlState.UNKNOWN.value,
                                 initial_inquiry_date=now_iso[:10], stage_entered_at=now_iso,
                                 last_synced_at=now_iso,
                                 flags=["loan_agreement_unmatched: Typeform response not matched to a "
                                        "known case — verify borrower/lender and link"]),
                            actor="op:loan_agreement", ts=now_iso, evidence_link="typeform:response")
        result.flagged.append({"token": token, "case_id": case_id,
                               "reason": f"unmatched borrower {borrower!r} — created holding case + folder, review"})
    else:
        case_id = case.case_id

    try:
        filename, ctype, data = typeform.download(url)   # transient RESTRICTED bytes
    except Exception as e:
        result.errors.append({"token": token, "borrower": borrower, "error": f"download: {e}"})
        return result

    # Idempotent: don't re-upload a file that is already in the folder.
    try:
        existing_names = drive.list_filenames(folder_id)
    except Exception:
        existing_names = set()
    if filename in existing_names:
        result.already.append({"token": token, "case_id": case_id, "filename": filename})
        # still make sure a receipt exists (idempotent on sha256)
        reg.add_document(case_id, "loan_agmt", _sha256(data), drive_link=None,
                         received_date=now_iso[:10])
        return result

    try:
        link = drive.upload(folder_id, filename, ctype, data)
    except Exception as e:
        result.errors.append({"token": token, "borrower": borrower, "error": f"upload: {e}"})
        return result

    sha = _sha256(data)
    reg.add_document(case_id, "loan_agmt", sha, drive_link=link, received_date=now_iso[:10])
    reg.append_event(case_id, now_iso, "op:loan_agreement", "document_received",
                     field="loan_agreement", new_value=filename, evidence_link=link,
                     idempotency_key=f"loanagmt:{case_id}:{sha[:16]}")
    result.filed.append({"token": token, "case_id": case_id, "filename": filename,
                         "link": link, "matched": matched})
    return result


def process_loan_agreements(reg: Register, responses: list[dict], typeform: TypeformClient,
                            drive: DriveWriter, now_iso: str,
                            create_missing: bool = True) -> FilingResult:
    """Backfill: file loan agreements for a batch of Typeform responses."""
    result = FilingResult()
    for resp in responses:
        process_one(reg, resp, typeform, drive, now_iso,
                    create_missing=create_missing, result=result)
    return result
