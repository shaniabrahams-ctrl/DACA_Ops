"""
Typeform Sync Service — pulls DACA application submissions from Google Sheets
and creates Borrower, Lender, TypeformSubmission, and DacaRequest records.

Intended to be called on a schedule (e.g. every 10 minutes via Celery beat)
or triggered manually from an API endpoint.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.config import settings
from app.db.session import AsyncSessionLocal
from app.integrations.google_sheets import get_typeform_responses_since
from app.models.borrower import Borrower
from app.models.lender import Lender
from app.models.typeform_submission import TypeformSubmission
from app.services import daca_request_service

logger = logging.getLogger(__name__)


def _parse_bool(value: str | None) -> bool | None:
    """Parse a Yes/No/True/False string into a boolean, returning None for empty values."""
    if not value or not value.strip():
        return None
    normalized = value.strip().lower()
    if normalized in ("yes", "true", "1"):
        return True
    if normalized in ("no", "false", "0"):
        return False
    return None


def _safe_int(value: str | None, default: int = 1) -> int:
    """Safely parse a string to int, returning a default for empty/invalid values."""
    if not value or not value.strip():
        return default
    try:
        return int(value.strip())
    except (ValueError, TypeError):
        return default


def _safe_str(value: str | None) -> str | None:
    """Return None for empty/whitespace-only strings."""
    if not value or not value.strip():
        return None
    return value.strip()


def _build_representatives(row: dict) -> list[dict]:
    """
    Build the lender representatives JSONB list from the rep fields.
    Only includes reps that have at least a name or email.
    """
    reps = []
    for i in range(1, 4):
        name = _safe_str(row.get(f"Lender Rep {i} Name"))
        phone = _safe_str(row.get(f"Lender Rep {i} Phone"))
        email = _safe_str(row.get(f"Lender Rep {i} Email"))
        if name or email:
            reps.append({
                "name": name or "",
                "phone": phone or "",
                "email": email or "",
            })
    return reps


def _parse_submitted_at(value: str | None) -> datetime | None:
    """Attempt to parse the Submitted At timestamp."""
    if not value or not value.strip():
        return None
    raw = value.strip()
    # Try ISO 8601 first, then common variants
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y",
    ):
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    logger.warning("Could not parse Submitted At value: %s", raw)
    return None


async def _find_or_create_borrower(db, row: dict) -> Borrower:
    """Find an existing Borrower by primary_contact_email (or legal_name) or create one."""
    email = _safe_str(row.get("Borrower Contact Email"))
    legal_name = _safe_str(row.get("Borrower Legal Name")) or "Unknown Borrower"

    # Try to find by email first
    if email:
        result = await db.execute(
            select(Borrower).where(Borrower.primary_contact_email == email)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

    # Fall back to finding by legal_name if no email or email not found
    result = await db.execute(
        select(Borrower).where(Borrower.legal_name == legal_name)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    # Create new borrower
    address_raw = _safe_str(row.get("Borrower Business Address"))
    borrower = Borrower(
        legal_name=legal_name,
        primary_contact_name=_safe_str(row.get("Borrower Contact Name")),
        primary_contact_email=email,
        has_rho_account=_parse_bool(row.get("Does borrower have a Rho account")) or False,
        address={"raw": address_raw} if address_raw else None,
    )
    db.add(borrower)
    await db.flush()
    logger.info("Created new Borrower: %s (id=%s)", borrower.legal_name, borrower.id)
    return borrower


async def _find_or_create_lender(db, row: dict) -> Lender:
    """Find an existing Lender by institution_name or create one."""
    institution_name = _safe_str(row.get("Lender Legal Name")) or "Unknown Lender"

    result = await db.execute(
        select(Lender).where(Lender.institution_name == institution_name)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    representatives = _build_representatives(row)
    rep_count = _safe_int(row.get("How many lender reps"), default=len(representatives) or 1)

    # Primary contact is the first representative
    primary_email = None
    primary_phone = None
    if representatives:
        primary_email = representatives[0].get("email") or None
        primary_phone = representatives[0].get("phone") or None

    lender = Lender(
        institution_name=institution_name,
        business_address=_safe_str(row.get("Lender Business Address")),
        rep_count=rep_count,
        representatives=representatives if representatives else None,
        primary_contact_email=primary_email,
        primary_contact_phone=primary_phone,
        daca_type="SPRINGING",
    )
    db.add(lender)
    await db.flush()
    logger.info("Created new Lender: %s (id=%s)", lender.institution_name, lender.id)
    return lender


def _build_typeform_submission(row: dict) -> TypeformSubmission:
    """Create a TypeformSubmission model instance from a sheet row dict."""
    return TypeformSubmission(
        token=row["Token"],
        submitted_at=_parse_submitted_at(row.get("Submitted At")),
        # Lender fields
        lender_legal_name=_safe_str(row.get("Lender Legal Name")),
        lender_business_address=_safe_str(row.get("Lender Business Address")),
        lender_rep_count=_safe_str(row.get("How many lender reps")),
        lender_rep_1_name=_safe_str(row.get("Lender Rep 1 Name")),
        lender_rep_1_phone=_safe_str(row.get("Lender Rep 1 Phone")),
        lender_rep_1_email=_safe_str(row.get("Lender Rep 1 Email")),
        lender_rep_2_name=_safe_str(row.get("Lender Rep 2 Name")),
        lender_rep_2_phone=_safe_str(row.get("Lender Rep 2 Phone")),
        lender_rep_2_email=_safe_str(row.get("Lender Rep 2 Email")),
        lender_rep_3_name=_safe_str(row.get("Lender Rep 3 Name")),
        lender_rep_3_phone=_safe_str(row.get("Lender Rep 3 Phone")),
        lender_rep_3_email=_safe_str(row.get("Lender Rep 3 Email")),
        # Borrower fields
        borrower_has_rho_account=_parse_bool(row.get("Does borrower have a Rho account")),
        borrower_legal_name=_safe_str(row.get("Borrower Legal Name")),
        borrower_business_address=_safe_str(row.get("Borrower Business Address")),
        borrower_contact_name=_safe_str(row.get("Borrower Contact Name")),
        borrower_contact_email=_safe_str(row.get("Borrower Contact Email")),
        # Deal details
        loan_agreement_url=_safe_str(row.get("Loan Agreement URL")),
        referral_source=_safe_str(row.get("Referral Source")),
        government_receivables_involved=_parse_bool(row.get("Government receivables involved")),
        multiple_accounts_involved=_parse_bool(row.get("Multiple accounts")),
        preferred_transfer_method=_safe_str(row.get("Preferred transfer method")),
        additional_info=_safe_str(row.get("Additional info")),
        # Not yet processed
        processed=False,
    )


async def _get_last_processed_token(db) -> str | None:
    """Get the token of the most recently processed TypeformSubmission for incremental polling."""
    result = await db.execute(
        select(TypeformSubmission.token)
        .order_by(TypeformSubmission.submitted_at.desc().nulls_last(), TypeformSubmission.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def sync_typeform_submissions() -> int:
    """
    Main sync function: pulls Typeform DACA application submissions from Google Sheets
    and creates Borrower, Lender, TypeformSubmission, and DacaRequest records.

    Returns the number of new submissions processed.
    """
    from app.integrations.google_auth import auth_mode
    if auth_mode() == "none":
        logger.info("Skipping Typeform sync: no Google credentials configured")
        return 0

    async with AsyncSessionLocal() as db:
        try:
            # Determine where we left off
            last_token = await _get_last_processed_token(db)
            logger.info(
                "Starting Typeform sync (last_token=%s)",
                last_token or "None — fetching all",
            )

            # Fetch new rows from Google Sheets
            rows = await get_typeform_responses_since(last_token)
            if not rows:
                logger.info("Typeform sync: no new submissions found")
                return 0

            logger.info("Typeform sync: found %d candidate row(s) to process", len(rows))

            processed_count = 0
            for row in rows:
                token = _safe_str(row.get("Token"))
                if not token:
                    logger.warning("Skipping row with missing Token: %s", row)
                    continue

                # Check if this submission already exists
                existing = await db.execute(
                    select(TypeformSubmission).where(TypeformSubmission.token == token)
                )
                if existing.scalar_one_or_none() is not None:
                    logger.debug("Skipping already-processed token: %s", token)
                    continue

                try:
                    # Find or create Borrower
                    borrower = await _find_or_create_borrower(db, row)

                    # Find or create Lender
                    lender = await _find_or_create_lender(db, row)

                    # Store the TypeformSubmission
                    submission = _build_typeform_submission(row)
                    db.add(submission)
                    await db.flush()

                    # Create DacaRequest via the service
                    daca_request = await daca_request_service.create(
                        db,
                        actor_id="typeform_sync_service",
                        borrower_id=borrower.id,
                        lender_id=lender.id,
                        source_channel="TYPEFORM",
                        source_reference=f"typeform_token:{token}",
                        typeform_token=token,
                        metadata={
                            "referral_source": _safe_str(row.get("Referral Source")),
                            "loan_agreement_url": _safe_str(row.get("Loan Agreement URL")),
                            "government_receivables": _parse_bool(row.get("Government receivables involved")),
                            "multiple_accounts": _parse_bool(row.get("Multiple accounts")),
                            "preferred_transfer_method": _safe_str(row.get("Preferred transfer method")),
                        },
                    )

                    # Mark submission as processed and link to DacaRequest
                    submission.processed = True
                    submission.daca_request_id = daca_request.id
                    await db.flush()

                    processed_count += 1
                    logger.info(
                        "Processed Typeform submission token=%s → DacaRequest %s (borrower=%s, lender=%s)",
                        token,
                        daca_request.external_ref,
                        borrower.legal_name,
                        lender.institution_name,
                    )

                except Exception:
                    logger.exception("Error processing Typeform submission token=%s", token)
                    # Continue processing remaining rows — don't let one bad row block the batch
                    continue

            await db.commit()
            logger.info("Typeform sync complete: %d new submission(s) processed", processed_count)
            return processed_count

        except Exception:
            await db.rollback()
            logger.exception("Typeform sync failed")
            raise
